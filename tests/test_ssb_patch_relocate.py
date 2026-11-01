import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from ssb_patch_relocate import build, references, sha256


def synthetic():
    data = bytearray(b"\x02\x00\x00\x00" * 32)
    ptr = 0x14
    struct.pack_into("<I", data, ptr - 4, 3)
    text_offset = 0x80
    struct.pack_into("<I", data, ptr, text_offset // 4)
    data.extend(b"\x00" * (0x100 - len(data)))
    data.extend(b" START : SCN_DEMO_001.sss\n\x00")
    while len(data) % 4:
        data.append(0)
    # Keep required scene marker before the dialogue string.
    text_offset = len(data)
    original = "食の悩みです。▼".encode("utf-8")
    data.extend(original + b"\x00")
    while len(data) % 4:
        data.append(0)
    struct.pack_into("<I", data, ptr, text_offset // 4)
    row = {
        "id": "synthetic",
        "offset_hex": f"0x{text_offset:X}",
        "original_bytes": str(len(original)),
        "source_ja": "食の悩みです。▼",
        "translation_ru": "У меня сегодня очень много вопросов про еду.▼",
    }
    return bytes(data), row, ptr


class RelocationTests(unittest.TestCase):
    def test_longer_russian_and_original_preservation(self):
        old, row, ptr = synthetic()
        self.assertEqual(references(old, int(row["offset_hex"], 0), old.find(b" START : SCN_")), [ptr])
        updated, report = build(old, [row], expected_sha=sha256(old))
        new_off = struct.unpack_from("<I", updated, ptr)[0] * 4
        self.assertEqual(new_off, len(old))
        self.assertGreater(len(updated), len(old))
        self.assertEqual(updated[new_off:new_off + len(row["translation_ru"].encode())],
                         row["translation_ru"].encode())
        self.assertEqual(old[int(row["offset_hex"], 0):int(row["offset_hex"], 0) + 24],
                         updated[int(row["offset_hex"], 0):int(row["offset_hex"], 0) + 24])
        reverted = bytearray(updated[:len(old)])
        reverted[ptr:ptr + 4] = old[ptr:ptr + 4]
        self.assertEqual(reverted, old)
        self.assertEqual(report["modified_pointer_operands"], 1)

    def test_bad_sha(self):
        old, row, _ = synthetic()
        with self.assertRaisesRegex(ValueError, "SHA256"):
            build(old, [row], expected_sha="0" * 64)

    def test_wrong_source(self):
        old, row, _ = synthetic()
        row["source_ja"] = "incorrect"
        with self.assertRaisesRegex(ValueError, "original data"):
            build(old, [row])

    def test_missing_marker(self):
        old, row, _ = synthetic()
        row["translation_ru"] = "Привет"
        with self.assertRaises(ValueError):
            build(old, [row])

    def test_missing_reference(self):
        old, row, ptr = synthetic()
        damaged = bytearray(old)
        struct.pack_into("<I", damaged, ptr - 4, 1)
        with self.assertRaisesRegex(ValueError, "expected 1"):
            build(bytes(damaged), [row])

    def test_no_change(self):
        old, row, _ = synthetic()
        row["translation_ru"] = ""
        got, report = build(old, [row])
        self.assertEqual(got, old)
        self.assertEqual(report["modified_pointer_operands"], 0)


if __name__ == "__main__":
    unittest.main()
