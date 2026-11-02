import csv
import hashlib
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_ru_from_audit import translate


def scene_and_csv(root: Path):
    buf = bytearray(b"\x02\x00\x00\x00" * 128)
    buf.extend(b" START : SCN_MAIN_DEMO_010.sss\x00")
    while len(buf) % 4: buf.append(0)
    offset = len(buf)
    original = "こんにちは。\n助けてください。▼"
    buf.extend(original.encode("utf-8") + b"\x00")
    while len(buf) % 4: buf.append(0)
    ptr = 0x14
    struct.pack_into("<I", buf, ptr - 4, 3)
    struct.pack_into("<I", buf, ptr, offset // 4)
    key = f"0x{offset:08X}"
    table = root / "SCN_MAIN_DEMO_010.csv"
    with table.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "offset_hex", "original_bytes", "source_ja",
            "speaker_candidate", "voice_candidate", "translation_ru", "notes"
        ])
        writer.writeheader()
        writer.writerow({
            "id": "test", "offset_hex": key,
            "original_bytes": len(original.encode("utf-8")),
            "source_ja": original
        })
    manifest = {
        "format": "sakurasou-ru-audit-manifest-v1",
        "scene": "SCN_MAIN_DEMO_010.ssb",
        "dialogues": {key: "Привет.\nПомогите, пожалуйста!▼"},
        "glossary": {}
    }
    return bytes(buf), table, manifest, ptr


class AuditRussianTests(unittest.TestCase):
    def test_patch_source_and_pointer_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            old, csv_file, manifest, ptr = scene_and_csv(Path(tmp))
            new, report = translate(old, csv_file, manifest)
            self.assertEqual(report["source_dialogues_verified"], 1)
            self.assertEqual(report["modified_pointer_operands"], 1)
            self.assertEqual(struct.unpack_from("<I", new, ptr)[0] * 4, len(old))
            reverted = bytearray(new[:len(old)])
            reverted[ptr:ptr + 4] = old[ptr:ptr + 4]
            self.assertEqual(reverted, old)
    def test_invalid_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            old, csv_file, manifest, ptr = scene_and_csv(Path(tmp))
            damaged = bytearray(old)
            damaged[-5] = ord("X")
            with self.assertRaisesRegex(ValueError, "source mismatch"):
                translate(bytes(damaged), csv_file, manifest)
    def test_missing_line_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            old, csv_file, manifest, ptr = scene_and_csv(Path(tmp))
            manifest["dialogues"] = {}
            with self.assertRaisesRegex(ValueError, "Missing translated"):
                translate(old, csv_file, manifest)
    def test_added_newline_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            old, csv_file, manifest, ptr = scene_and_csv(Path(tmp))
            key = next(iter(manifest["dialogues"]))
            manifest["dialogues"][key] = "А\nБ\nВ▼"
            with self.assertRaisesRegex(ValueError, "Linebreaks differ"):
                translate(old, csv_file, manifest)


if __name__ == "__main__":
    unittest.main()
