#!/usr/bin/env python3
"""Build XMLTV from public sources; never read or publish stream credentials."""
import argparse
import copy
import gzip
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from defusedxml.ElementTree import fromstring

MAX_BYTES = 100 * 1024 * 1024


def normalize(name):
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    name = re.sub(r'\b(?:hd|fhd|sd|uhd|4k|1080p|720p)\b', '', name)
    return re.sub(r'[^a-z0-9]', '', name)


def import_playlist(path):
    channels = {}
    metadata = None
    for line in Path(path).read_text(encoding='utf-8-sig', errors='replace').splitlines():
        if line.startswith('#EXTINF:'):
            metadata = line
        elif line and not line.startswith('#'):
            if metadata and line.split('?', 1)[0].lower().endswith('.ts'):
                attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', metadata))
                name = attrs.get('tvg-name') or metadata.rsplit(',', 1)[-1].strip()
                source_id = attrs.get('tvg-id', '').strip()
                ident = source_id or 'm3u-' + hashlib.sha256(name.encode()).hexdigest()[:16]
                # URLs, groups and logos are deliberately excluded from public config.
                if ident not in channels:
                    channels[ident] = {'id': ident, 'names': [], 'source_id': source_id}
                if name not in channels[ident]['names']:
                    channels[ident]['names'].append(name)
            metadata = None
    return list(channels.values())


def timestamp(value):
    match = re.fullmatch(r'(\d{14})\s*([+-]\d{4})', value or '')
    if not match:
        raise ValueError('XMLTV timestamp must include seconds and timezone')
    return datetime.strptime(' '.join(match.groups()), '%Y%m%d%H%M%S %z').astimezone(timezone.utc)


def fetch_xml(url):
    if not url.startswith('https://'):
        raise ValueError('HTTPS required')
    with urlopen(Request(url, headers={'User-Agent': 'Fabriciocypreste-EPG/1.0'}), timeout=60) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('Source exceeds size limit')
    if data[:2] == b'\x1f\x8b':
        import io
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError('Expanded source exceeds size limit')
    root = fromstring(data)
    if root.tag != 'tv':
        raise ValueError('Source is not XMLTV')
    return root


def assemble(channels, sources, now=None):
    now = now or datetime.now(timezone.utc)
    root = ET.Element('tv', {'generator-info-name': 'Fabriciocypreste/epg'})
    report = {'generated_at': now.isoformat(), 'channels': [], 'sources': []}
    loaded = []
    for url in sources:
        try:
            xml = fetch_xml(url)
            catalog = {}
            names = defaultdict(set)
            for channel in xml.findall('channel'):
                ident = channel.get('id')
                if not ident:
                    continue
                catalog[ident] = channel
                for name in channel.findall('display-name'):
                    key = normalize(name.text or '')
                    if key:
                        names[key].add(ident)
            programs = defaultdict(list)
            for program in xml.findall('programme'):
                try:
                    start = timestamp(program.get('start'))
                    stop = timestamp(program.get('stop'))
                except ValueError:
                    continue
                if start < stop and stop > now - timedelta(hours=12) and start < now + timedelta(days=7):
                    programs[program.get('channel')].append(program)
            loaded.append((url, catalog, names, programs))
            report['sources'].append({'url': url, 'status': 'ok', 'usable_programmes': sum(map(len, programs.values()))})
        except Exception as exc:
            report['sources'].append({'url': url, 'status': 'error', 'error_type': type(exc).__name__})
    total = 0
    for target in channels:
        selected = None
        ambiguous = False
        for url, catalog, names, programs in loaded:
            ident = target.get('source_id')
            if ident not in catalog:
                matches = set()
                for name in target['names']:
                    matches.update(names.get(normalize(name), set()))
                if len(matches) != 1:
                    ambiguous |= len(matches) > 1
                    continue
                ident = next(iter(matches))
            if programs.get(ident):
                selected = (url, ident, programs[ident])
                break
        channel = ET.SubElement(root, 'channel', {'id': target['id']})
        for name in target['names']:
            ET.SubElement(channel, 'display-name', {'lang': 'pt'}).text = name
        status = {'id': target['id'], 'names': target['names'], 'status': 'ambiguous' if ambiguous else 'no_programming', 'programmes': 0}
        if selected:
            url, ident, programs = selected
            seen = set()
            for program in sorted(programs, key=lambda p: timestamp(p.get('start'))):
                key = (timestamp(program.get('start')), timestamp(program.get('stop')))
                if key in seen:
                    continue
                seen.add(key)
                item = copy.deepcopy(program)
                item.set('channel', target['id'])
                # Keep only programme metadata, excluding external URLs/icons.
                for child in list(item):
                    if child.tag not in {'title', 'sub-title', 'desc', 'category', 'episode-num', 'rating', 'length'}:
                        item.remove(child)
                root.append(item)
                total += 1
            status.update(status='mapped', source=url, source_id=ident, programmes=len(seen))
        report['channels'].append(status)
    if total == 0:
        raise RuntimeError('No usable programming: previous EPG must be preserved. Source diagnostics: ' + json.dumps(report['sources']))
    report['programmes'] = total
    report['mapped_channels'] = sum(c['status'] == 'mapped' for c in report['channels'])
    return ET.tostring(root, encoding='utf-8', xml_declaration=True), report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--import-m3u', type=Path)
    parser.add_argument('--channels', type=Path, default=Path('channels.json'))
    parser.add_argument('--sources', type=Path, default=Path('sources.txt'))
    parser.add_argument('--output', type=Path, default=Path('output'))
    args = parser.parse_args()
    if args.import_m3u:
        channels = import_playlist(args.import_m3u)
        args.channels.write_text(json.dumps(channels, ensure_ascii=False, indent=2) + '\n')
        print(f'Imported {len(channels)} channel IDs without stream URLs')
        return
    channels = json.loads(args.channels.read_text())
    sources = [line.strip() for line in args.sources.read_text().splitlines() if line.strip() and not line.startswith('#')]
    xml, report = assemble(channels, sources)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'epg.xml').write_bytes(xml)
    (args.output / 'epg.xml.gz').write_bytes(gzip.compress(xml, mtime=0))
    (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f"Mapped {report['mapped_channels']}/{len(channels)} channels; {report['programmes']} programmes")


if __name__ == '__main__':
    main()
