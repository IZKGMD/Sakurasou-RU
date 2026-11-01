import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from ssb_extract import extract, classify


def example():
    b = bytearray(b"\x02\x00\x00\x00" * 8)
    def add(text):
        b.extend(text.encode("utf-8") + b"\x00")
        while len(b) % 4:
            b.append(0)
    add(" START : SCN_TEST.sss\n")
    add("V_X_001.hca")
    add("神田空太")
    add("V_X_001.hca")
    add("なんだ、こ　れは。▼")
    add(" END   : SCN_TEST.sss\n")
    return bytes(b)


class SSBTests(unittest.TestCase):
    def test_story(self):
        data = example()
        rows, stats = extract(data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(stats["complete_voice_speaker_voice_dialogue_quartets"], 1)
        self.assertEqual(rows[0]["speaker_candidate"], "神田空太")
        self.assertEqual(rows[0]["voice_candidate"], "V_X_001.hca")
        self.assertIn("　", rows[0]["source_ja"])
        self.assertNotIn("なんだ", str(stats))
        self.assertEqual(data, example())

    def test_missing_marker_requires_override(self):
        data = bytes(16) + "日本語の文章▼".encode("utf-8") + b"\x00"
        with self.assertRaises(ValueError):
            extract(data)
        rows, stats = extract(data, scope="all")
        self.assertEqual(len(rows), 1)
        self.assertIsNone(stats["story_boundary_hex"])

    def test_classification(self):
        self.assertEqual(classify("V_B05_JIN_0010.hca"), "voice")
        self.assertEqual(classify("三鷹仁"), "speaker_candidate")
        self.assertEqual(classify("はい、がんばります！▼"), "text_candidate")


if __name__ == "__main__":
    unittest.main()
