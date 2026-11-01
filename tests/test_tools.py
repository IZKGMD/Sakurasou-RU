import csv
from pathlib import Path
import tempfile
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from scan_assets import make_report
from check_translations import validate
from build_xdelta import digest

class ToolsTests(unittest.TestCase):
    def test_scan_synthetic_cpk(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'demo.cpk'
            p.write_bytes(b'CPK ' + b'\x00' * 16)
            result = make_report(p)
            self.assertEqual(result['file_count'], 1)
            self.assertTrue(result['files'][0]['cpk_magic'])
            self.assertEqual(len(result['files'][0]['sha256']), 64)

    def test_directory_reports_text(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / 'example.msg').write_text('test', encoding='utf-8')
            (p / 'image.dds').write_bytes(b'123')
            report = make_report(p)
            self.assertEqual(report['file_count'], 2)
            self.assertEqual(report['likely_text_files'], 1)

    def test_duplicate_ids_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'strings.csv'
            with p.open('w', encoding='utf-8', newline='') as f:
                w = csv.writer(f)
                w.writerows([['id','ru'], ['start','Играть'], ['start','Начать']])
            count, errors = validate(p)
            self.assertEqual(count, 2)
            self.assertTrue(any('duplicate' in e for e in errors))

    def test_hash(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'test.bin'
            p.write_bytes(b'test')
            self.assertEqual(digest(p), '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08')

if __name__ == '__main__':
    unittest.main()
