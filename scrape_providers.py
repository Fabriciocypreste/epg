"""Collect public Claro/Vivo schedule metadata into XMLTV, without playback APIs."""
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

CLARO = 'https://programacao.claro.com.br/gatekeeper/'
VIVO = 'https://contentapi-br.cdn.telefonica.com/25/default/pt-BR/'
TZ = ZoneInfo('America/Sao_Paulo')


def get_html(url):
    with urlopen(Request(url, headers={'User-Agent': 'Fabriciocypreste-EPG/1.0'}), timeout=30) as response:
        data = response.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise ValueError('HTML size limit exceeded')
    return data.decode('utf-8')


def parse_meuguia(html, ident, now=None):
    from bs4 import BeautifulSoup
    now = now or datetime.now(TZ)
    soup = BeautifulSoup(html, 'html.parser')
    day, rows = None, []
    for item in soup.select('ul.mw li'):
        if 'subheader' in item.get('class', []):
            match = re.search(r'(\d{1,2})/(\d{1,2})', item.get_text(' ', strip=True))
            if match:
                dates = []
                for year in (now.year - 1, now.year, now.year + 1):
                    try:
                        dates.append(datetime(year, int(match[2]), int(match[1]), tzinfo=TZ))
                    except ValueError:
                        pass
                day = min(dates, key=lambda d: abs((d - now).total_seconds())) if dates else None
            continue
        link, clock = item.find('a'), item.select_one('.time')
        if not day or not link or not clock:
            continue
        title = link.get('title') or (item.find('h2').get_text(' ', strip=True) if item.find('h2') else '')
        match = re.fullmatch(r'(\d{1,2}):(\d{2})', clock.get_text(strip=True))
        if not match or not title:
            continue
        try:
            start = day.replace(hour=int(match[1]), minute=int(match[2]))
        except ValueError:
            continue
        category = item.find('h3')
        rows.append((start, title, category.get_text(' ', strip=True) if category else ''))
    rows = sorted(set(rows))
    programs = []
    for current, following in zip(rows, rows[1:]):
        start, title, category = current
        stop = following[0]
        # End comes from the next programme, not an invented duration.
        if start >= stop or stop <= now - timedelta(hours=12) or start >= now + timedelta(days=7):
            continue
        element = ET.Element('programme', {'channel': ident, 'start': start.strftime('%Y%m%d%H%M%S %z'), 'stop': stop.strftime('%Y%m%d%H%M%S %z')})
        ET.SubElement(element, 'title', {'lang': 'pt'}).text = title
        if category:
            ET.SubElement(element, 'category', {'lang': 'pt'}).text = category
        programs.append(element)
    return programs


def scrape_meuguia(targets):
    from bs4 import BeautifulSoup
    from build_epg import normalize
    soup = BeautifulSoup(get_html('https://meuguia.tv/programacao/categoria/Esportes'), 'html.parser')
    wanted = {normalize(name) for target in targets for name in target['names']}
    root = ET.Element('tv', {'generator-info-name': 'Fabriciocypreste/epg meuguia'})
    catalog = {}
    for link in soup.select('a[href]'):
        href = link.get('href', '')
        if not re.fullmatch(r'/programacao/canal/[A-Za-z0-9_-]+', href):
            continue
        heading = link.select_one('.licontent h2') or link.find('h2')
        if heading:
            name = heading.get_text(' ', strip=True)
            if normalize(name) in wanted:
                catalog[href] = name
    failures = 0
    for href, name in catalog.items():
        ident = 'meuguia-' + href.rsplit('/', 1)[-1]
        try:
            programs = parse_meuguia(get_html('https://meuguia.tv' + href), ident)
            if not programs:
                continue
            channel = ET.SubElement(root, 'channel', {'id': ident})
            ET.SubElement(channel, 'display-name', {'lang': 'pt'}).text = name
            root.extend(programs)
        except Exception:
            failures += 1
        time.sleep(0.3)
    root.set('failed-channel-requests', str(failures))
    return root


def parse_prime(html, targets):
    from build_epg import normalize
    match = re.search(r'<script\b[^>]*\bid="dv-web-page-hydration-data"[^>]*>(.*?)</script>', html, re.S)
    if not match:
        raise ValueError('Prime public schedule data missing')
    data = json.loads(match.group(1))
    containers = data['init']['preparations']['body']['containers']
    wanted = {normalize(name) for target in targets for name in target['names']}
    root = ET.Element('tv', {'generator-info-name': 'Fabriciocypreste/epg prime'})
    seen_channels, seen_programmes = set(), set()
    for container in containers:
        for entity in container.get('entities', []):
            station = entity.get('station', {})
            name, ident = station.get('name', ''), station.get('id')
            if not ident or normalize(name) not in wanted:
                continue
            ident = 'prime-' + ident
            if ident not in seen_channels:
                seen_channels.add(ident)
                channel = ET.SubElement(root, 'channel', {'id': ident})
                ET.SubElement(channel, 'display-name', {'lang': 'pt'}).text = name
            for programme in station.get('schedule', []):
                start, end = programme.get('start'), programme.get('end')
                if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                    continue
                key = (ident, start, end)
                if key in seen_programmes:
                    continue
                metadata = programme.get('metadata', {})
                item = {'Title': metadata.get('title'), 'Description': metadata.get('synopsis'), 'Start': start / 1000, 'End': end / 1000}
                if add_program(root, ident, item, 'vivo'):
                    seen_programmes.add(key)
    return root


def scrape_prime(targets):
    request = Request('https://www.primevideo.com/-/pt/livetv', headers={'User-Agent': 'Fabriciocypreste-EPG/1.0'})
    with urlopen(request, timeout=30) as response:
        data = response.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise ValueError('Prime response size exceeded')
    return parse_prime(data.decode('utf-8'), targets)


def get_json(base, params):
    url = base + '?' + urlencode(params)
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Fabriciocypreste-EPG/1.0', 'Accept': 'application/json'}), timeout=30) as response:
                data = response.read(50 * 1024 * 1024 + 1)
            if len(data) > 50 * 1024 * 1024:
                raise ValueError('Response size exceeded')
            return json.loads(data)
        except Exception as exc:
            code = getattr(exc, 'code', None)
            if code in (401, 403, 404) or attempt == 2:
                raise
            time.sleep(1 + attempt)


def xml_time(value, provider):
    if provider == 'vivo':
        date = datetime.fromtimestamp(float(value), timezone.utc)
    else:
        # Claro represents local wall-clock hours with a literal Z (upstream adapter convention).
        raw = str(value).removesuffix('Z')
        date = datetime.fromisoformat(raw)
        if date.tzinfo is None:
            date = date.replace(tzinfo=TZ)
    return date.strftime('%Y%m%d%H%M%S %z')


def add_program(root, ident, item, provider):
    title = item.get('titulo') if provider == 'claro' else item.get('Title')
    start = item.get('dh_inicio') if provider == 'claro' else item.get('Start')
    stop = item.get('dh_fim') if provider == 'claro' else item.get('End')
    if not title or start is None or stop is None:
        return False
    try:
        start, stop = xml_time(start, provider), xml_time(stop, provider)
        if datetime.strptime(start, '%Y%m%d%H%M%S %z') >= datetime.strptime(stop, '%Y%m%d%H%M%S %z'):
            return False
    except (ValueError, TypeError, OverflowError):
        return False
    element = ET.SubElement(root, 'programme', {'channel': ident, 'start': start, 'stop': stop})
    ET.SubElement(element, 'title', {'lang': 'pt'}).text = str(title)
    description = item.get('sinopse') if provider == 'claro' else item.get('Description')
    if description:
        ET.SubElement(element, 'desc', {'lang': 'pt'}).text = str(description)
    season, episode = item.get('SeasonNumber'), item.get('EpisodeNumber')
    if isinstance(season, int) and isinstance(episode, int) and season > 0 and episode > 0:
        ET.SubElement(element, 'episode-num', {'system': 'xmltv_ns'}).text = f'{season-1}.{episode-1}.'
    return True


def scrape(provider, targets, days=2, city='1'):
    if provider == 'meuguia':
        return scrape_meuguia(targets)
    if provider == 'prime':
        return scrape_prime(targets)
    from build_epg import normalize
    wanted = {normalize(name) for target in targets for name in target['names']}
    if provider == 'claro':
        data = get_json(CLARO + 'canal/select', {'q': f'id_cidade:{city}', 'rows': 1000, 'wt': 'json', 'sort': 'cn_canal asc', 'fl': 'id_canal,id_cidade,nome', 'fq': 'nome:*'})
        catalog = [{'id': str(row['id_canal']), 'name': row['nome']} for row in data['response']['docs']]
    else:
        data = get_json(VIVO + 'contents/all', {'ca_deviceTypes': 401, 'contentTypes': 'LCH', 'ca_active': 'true', 'ca_requiresPin': 'false', 'fields': 'Pid,Name', 'orderBy': 'contentOrder', 'offset': 0, 'limit': 1000})
        catalog = [{'id': str(row['Pid']).lower(), 'name': row['Name']} for row in data['Content']['List']]
    catalog = [row for row in catalog if normalize(row['name']) in wanted]
    root = ET.Element('tv', {'generator-info-name': f'Fabriciocypreste/epg {provider}'})
    for row in catalog:
        channel = ET.SubElement(root, 'channel', {'id': provider + '-' + row['id']})
        ET.SubElement(channel, 'display-name', {'lang': 'pt'}).text = row['name']
    allowed = {row['id'] for row in catalog}
    today = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    for day in range(days):
        date = today + timedelta(days=day)
        if provider == 'claro':
            query = {'q': f'id_cidade:{city}', 'wt': 'json', 'rows': 100000, 'start': 0, 'sort': 'id_canal asc,dh_inicio asc', 'fq': f'dh_inicio:[{date:%Y-%m-%dT00:00:00Z} TO {date:%Y-%m-%dT23:59:59Z}]'}
            data = get_json(CLARO + 'exibicao/select', query)
            rows = data['response']['docs']
            if data['response'].get('numFound', len(rows)) > len(rows):
                raise ValueError('Claro schedule truncated; pagination required')
            for item in rows:
                ident = str(item.get('id_canal', ''))
                if ident in allowed:
                    add_program(root, 'claro-' + ident, item, provider)
            time.sleep(0.3)
        else:
            # Vivo accepts a single channel PID; comma/pipe batches returned empty data.
            from concurrent.futures import ThreadPoolExecutor
            def request_channel(ident):
                query = {'ca_deviceTypes': 'null|401', 'ca_channelmaps': '779|null', 'fields': 'Title,Description,Start,End,LiveChannelPid,SeasonNumber,EpisodeNumber', 'starttime': int(date.timestamp()), 'endtime': int((date + timedelta(days=1)).timestamp()), 'livechannelpids': ident, 'offset': 0, 'limit': 1000, 'orderBy': 'START_TIME:a', 'filteravailability': 'false'}
                try:
                    data = get_json(VIVO + 'schedules', query)
                    rows = data['Content']
                    if not isinstance(rows, list) or len(rows) >= 1000:
                        raise ValueError('Unexpected or truncated Vivo schedule')
                    time.sleep(0.3)
                    return ident, rows, None
                except Exception as exc:
                    return ident, [], type(exc).__name__
            with ThreadPoolExecutor(max_workers=3) as executor:
                failures = int(root.get('failed-channel-requests', '0'))
                for ident, rows, error in executor.map(request_channel, sorted(allowed)):
                    if error:
                        failures += 1
                    for item in rows:
                        if str(item.get('LiveChannelPid', '')).lower() == ident:
                            add_program(root, 'vivo-' + ident, item, provider)
                root.set('failed-channel-requests', str(failures))
    return root


def collect(targets, directory, days=2, city='1'):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    files, report = [], []
    for provider in ('claro', 'vivo', 'prime', 'meuguia'):
        try:
            root = scrape(provider, targets, days, city)
            count = len(root.findall('programme'))
            if not count:
                raise ValueError('Provider returned no valid programmes')
            path = directory / (provider + '.xml')
            path.write_bytes(ET.tostring(root, encoding='utf-8', xml_declaration=True))
            files.append(str(path))
            report.append({'provider': provider, 'status': 'ok', 'channels': len(root.findall('channel')), 'programmes': count, 'failed_channel_requests': int(root.get('failed-channel-requests', '0'))})
            print(f'{provider}: {count} programmes', flush=True)
        except Exception as exc:
            report.append({'provider': provider, 'status': 'error', 'error_type': type(exc).__name__, 'http_status': getattr(exc, 'code', None)})
            print(f'{provider}: {type(exc).__name__}', flush=True)
    priority = {'meuguia': 0, 'vivo': 1, 'claro': 2, 'prime': 3}
    files.sort(key=lambda path: priority.get(Path(path).stem, 4))
    return files, report
