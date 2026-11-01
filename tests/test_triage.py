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


from diagnose_cpk import inspect_header

class CpkHeaderTests(unittest.TestCase):
    def test_standard_cpk(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'DATA.CPK'
            path.write_bytes(b'CPK '+b'\x00'*100)
            report=inspect_header(path)
            self.assertEqual(report['status'], 'standard_cpk')
            self.assertEqual(report['cpk_signature_offset_first_4096'], 0)

    def test_nonstandard_header(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'DATA.CPK'
            path.write_bytes(bytes(range(32))+b'\x7f'*200)
            report=inspect_header(path)
            self.assertEqual(report['status'], 'unknown_header_possibly_encrypted')
            self.assertIsNone(report['cpk_signature_offset_first_4096'])
            self.assertEqual(len(report['first_32_bytes_hex'].split()), 32)

    def test_prefixed_cpk(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'DATA.CPK'
            path.write_bytes(b'XXXX'*4+b'CPK '+b'\x00'*30)
            report=inspect_header(path)
            self.assertEqual(report['cpk_signature_offset_first_4096'],16)
            self.assertEqual(report['status'], 'cpk_signature_at_nonzero_offset')
