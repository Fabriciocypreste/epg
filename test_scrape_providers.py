import unittest
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
import xml.etree.ElementTree as ET
from scrape_providers import xml_time, add_program, scrape, parse_prime, parse_meuguia


class ScraperTests(unittest.TestCase):
    def test_meuguia_date_rollover_next_start_and_last_item(self):
        html = '<ul class="mw"><li class="subheader">quinta-feira, 31/12</li><li><a title="Match"><span class="time">23:00</span><h3>Futebol</h3></a></li><li class="subheader">sexta-feira, 1/1</li><li><a title="News"><span class="time">01:00</span></a></li></ul>'
        now = datetime(2026, 12, 31, 22, tzinfo=ZoneInfo('America/Sao_Paulo'))
        items = parse_meuguia(html, 'SPO', now)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].get('stop'), '20270101010000 -0300')
        self.assertEqual(items[0].find('category').text, 'Futebol')

    def test_prime_epoch_milliseconds_and_deduplication(self):
        entity = {'station': {'id': 'a', 'name': 'CazéTV', 'schedule': [{'start': 1791532800000, 'end': 1791536400000, 'metadata': {'title': 'Match', 'synopsis': 'Football'}}]}}
        data = {'init': {'preparations': {'body': {'containers': [{'entities': [entity, entity]}]}}}}
        html = '<script id="dv-web-page-hydration-data" type="application/json">' + json.dumps(data) + '</script>'
        root = parse_prime(html, [{'names': ['CazéTV HD']}])
        self.assertEqual(len(root.findall('programme')), 1)
        self.assertEqual(root.find('programme').get('start'), '20261009080000 +0000')
        self.assertEqual(root.find('programme/desc').text, 'Football')

    def test_claro_wall_clock_and_vivo_epoch(self):
        self.assertEqual(xml_time('2026-10-09T00:31Z', 'claro'), '20261009003100 -0300')
        self.assertEqual(xml_time(1791532800, 'vivo'), '20261009080000 +0000')

    def test_bad_interval_is_excluded(self):
        root = ET.Element('tv')
        self.assertFalse(add_program(root, 'x', {'Title': 'Bad', 'Start': 100, 'End': 99}, 'vivo'))
        self.assertEqual(len(root), 0)

    def test_vivo_single_channel_and_description(self):
        catalog = {'Content': {'List': [{'Pid': 'LCH216', 'Name': 'sportv'}]}}
        schedule = {'Content': [{'LiveChannelPid': 'LCH216', 'Title': 'Match', 'Description': 'Football', 'Start': 1791532800, 'End': 1791536400}]}
        with patch('scrape_providers.get_json', side_effect=[catalog, schedule]) as request, patch('scrape_providers.time.sleep'):
            root = scrape('vivo', [{'names': ['sportv HD']}], days=1)
        self.assertEqual(request.call_args.args[1]['livechannelpids'], 'lch216')
        self.assertEqual(root.find('programme/desc').text, 'Football')

    def test_claro_channel_filter_and_real_dates(self):
        catalog = {'response': {'docs': [{'id_canal': 1, 'nome': 'Sport HD'}, {'id_canal': 2, 'nome': 'Other'}]}}
        schedules = {'response': {'docs': [{'id_canal': 1, 'titulo': 'Match', 'dh_inicio': '2026-10-09T10:00Z', 'dh_fim': '2026-10-09T12:00Z'}, {'id_canal': 2, 'titulo': 'Other', 'dh_inicio': '2026-10-09T10:00Z', 'dh_fim': '2026-10-09T12:00Z'}]}}
        with patch('scrape_providers.get_json', side_effect=[catalog, schedules]), patch('scrape_providers.time.sleep'):
            root = scrape('claro', [{'names': ['Sport FHD']}], days=1)
        self.assertEqual(len(root.findall('programme')), 1)
        self.assertEqual(root.find('programme').get('channel'), 'claro-1')


if __name__ == '__main__':
    unittest.main()
