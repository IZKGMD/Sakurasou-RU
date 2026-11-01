import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from triage_scripts import inspect_directory
from extract_cpk import extract

class TriageTests(unittest.TestCase):
    def test_counts_metadata_only(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / 'chapter.ssb').write_bytes(b'ABCD' + b'X' * 55)
            (base / 'font.fnt').write_bytes(b'FNT!')
            (base / 'audio.adx').write_bytes(b'ADX!')
            r = inspect_directory(base)
            self.assertEqual(r['total_files'], 3)
            self.assertEqual(r['script_candidates'], 1)
            self.assertEqual(len(r['candidate_files']), 2)
            self.assertNotIn('XXXX', str(r))
    def test_rejects_noncpk(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            archive=root/'source.cpk'; archive.write_bytes(b'nope')
            tool=root/'CriPakTool.exe';tool.write_bytes(b'dummy')
            with self.assertRaises(ValueError):
                extract(archive, tool, root/'out')
    def test_extraction_folder_cannot_contain_original(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            archive=root/'source.cpk'; archive.write_bytes(b'CPK '+b'\0'*16)
            tool=root/'CriPakTool.exe';tool.write_bytes(b'dummy')
            with self.assertRaises(ValueError):
                extract(archive,tool,root)

if __name__ == '__main__':
    unittest.main()
