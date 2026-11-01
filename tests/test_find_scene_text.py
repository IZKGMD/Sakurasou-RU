import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from find_scene_text import scan


class SceneTextLocatorTests(unittest.TestCase):
    def test_finds_screenshot_phrase_in_aligned_nul_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SCN_DEMO.ssb").write_bytes(
                b"\x02\x00\x00\x00" * 8 +
                "……それでは、見事優勝したこのチームへ、大きな拍手と歓声を！！▼".encode("utf-8")
                + b"\x00\x00\x00"
            )
            results = scan(root, ["見事優勝したこのチーム"])
            self.assertEqual(len(results["matches"]), 1)
            found = results["matches"][0]
            self.assertEqual(found["relative_file"], "SCN_DEMO.ssb")
            self.assertTrue(found["string_start_is_word_aligned"])
            self.assertIn("大きな拍手", found["context_utf8"])

    def test_no_matches_and_ignore_non_text_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "foo.txg").write_bytes("見事優勝".encode("utf-8"))
            (root / "a.ssb").write_bytes(b"START")
            results = scan(root, ["見事優勝"])
            self.assertEqual(results["files_scanned"], 1)
            self.assertEqual(results["matches"], [])

    def test_missing_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                scan(Path(tmp)/"missing", ["日本語"])


if __name__ == "__main__":
    unittest.main()
