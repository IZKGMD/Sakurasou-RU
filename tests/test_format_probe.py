import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from analyze_sakurasou_samples import inspect


class ProbeTests(unittest.TestCase):
    def test_cmed_utf8_heuristic(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sample.cmed"
            p.write_bytes(b"CMED" + bytes(8) + "こんにちは世界".encode("utf-8"))
            result = inspect(p)
            self.assertEqual(result["possible_signature"], "CMED")
            self.assertGreater(result["japanese_text_heuristics"]["utf-8"]["run_count"], 0)
            self.assertNotIn("こんにちは", str(result))

    def test_ssb_repeated_header(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "test.ssb"
            p.write_bytes((2).to_bytes(4, "little") + bytes(4))
            p.write_bytes(p.read_bytes() * 4)
            result = inspect(p)
            self.assertTrue(result["first_32_bytes_repeated_eightbyte_block"])
            self.assertEqual(result["first_16_dwords_le"][:4], [2, 0, 2, 0])

    def test_fnt_recognition(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "font.fnt"
            p.write_bytes(b"FNT\x00" + bytes(28))
            self.assertEqual(inspect(p)["possible_signature"], "FNT")


if __name__ == "__main__":
    unittest.main()
