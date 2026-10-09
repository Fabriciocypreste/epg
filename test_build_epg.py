import unittest
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET
from build_epg import assemble, import_playlist, normalize


class EPGTests(unittest.TestCase):
    def test_import_excludes_credentials_and_vod(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'input.m3u'
            path.write_text('#EXTM3U\n#EXTINF:-1 tvg-id="a" tvg-name="Sport HD",Sport HD\nhttps://example.com/live/SECRET/password/1.ts\n#EXTINF:-1 tvg-id="v",Movie\nhttps://example.com/movie/SECRET/password/2.mp4\n')
            result = import_playlist(path)
            self.assertEqual(len(result), 1)
            self.assertNotIn('SECRET', str(result))
            self.assertEqual(result[0]['source_id'], 'a')

    def test_fallback_from_stale_source_and_no_ambiguous_match(self):
        stale = ET.fromstring('<tv><channel id="a"><display-name>Sport</display-name></channel><programme channel="a" start="20200101000000 +0000" stop="20200101010000 +0000"><title>Old</title></programme></tv>')
        good = ET.fromstring('<tv><channel id="a"><display-name>Sport</display-name></channel><channel id="b"><display-name>Other HD</display-name></channel><channel id="c"><display-name>Other SD</display-name></channel><programme channel="a" start="20261009100000 +0000" stop="20261009120000 +0000"><title>Live</title></programme></tv>')
        channels = [{'id': 'a', 'source_id': 'a', 'names': ['Sport HD']}, {'id': 'x', 'source_id': '', 'names': ['Other']}]
        with patch('build_epg.fetch_xml', side_effect=[stale, good]):
            xml, report = assemble(channels, ['https://one', 'https://two'], datetime(2026, 10, 9, 10, tzinfo=timezone.utc))
        self.assertEqual(report['mapped_channels'], 1)
        self.assertEqual(report['channels'][0]['source'], 'https://two')
        self.assertEqual(report['channels'][1]['status'], 'ambiguous')
        self.assertNotIn(b'Old', xml)

    def test_empty_programming_fails_without_fake_schedule(self):
        with patch('build_epg.fetch_xml', return_value=ET.fromstring('<tv/>')):
            with self.assertRaises(RuntimeError):
                assemble([{'id': 'a', 'source_id': 'a', 'names': ['Sport']}], ['https://one'])

    def test_regional_names_remain_distinct(self):
        self.assertNotEqual(normalize('Globo RJ HD'), normalize('Globo SP FHD'))


if __name__ == '__main__':
    unittest.main()
