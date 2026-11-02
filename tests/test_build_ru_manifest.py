import hashlib
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_ru_manifest import build_translated_scene, make_rows, validate_manifest


def synthetic_full_episode():
    names = ["神田空太"] * 20 + ["青山七海"] * 8 + ["椎名ましろ"] * 8
    labels = ["？？？"] * 4
    contents = [(f"あ{i}▼", f"Тест {i}▼", "dialogue") for i in range(71)]
    contents.extend((name, {"神田空太": "Сората Канда", "青山七海": "Нанами Аояма",
                             "椎名ましろ": "Масиро Сиина"}[name], "speaker") for name in names)
    contents.extend((label, "???", "unknown") for label in labels)
    first_pointer = 0x14
    data = bytearray(bytes([2, 0, 0, 0]) * 300)
    data.extend(b" START : SCN_MAIN_1Y_1112__010.sss\x00")
    while len(data) % 4:
        data.append(0)
    translations = {}
    ptrs = []
    for idx, (japanese, russian, kind) in enumerate(contents):
        pos = len(data)
        raw = japanese.encode("utf-8")
        data.extend(raw + b"\x00")
        while len(data) % 4:
            data.append(0)
        pointer = first_pointer + idx * 8
        struct.pack_into("<I", data, pointer - 4, 3)
        struct.pack_into("<I", data, pointer, pos // 4)
        ptrs.append((pointer, pos))
        if kind == "dialogue":
            translations[f"0x{pos:08X}"] = russian
    manifest = {
        "format": "sakurasou-ssb-ru-manifest-v1",
        "title_id": "PCSG00129",
        "scene": "SCN_MAIN_1Y_1112__010.ssb",
        "original_sha256": hashlib.sha256(data).hexdigest(),
        "dialogues": translations,
        "speakers": {"神田空太": "Сората Канда", "青山七海": "Нанами Аояма",
                     "椎名ましろ": "Масиро Сиина"},
        "unknown_speaker": "???",
        "expected_counts": {"dialogue": 71, "speaker": 36, "unknown": 4},
        "max_display_chars": 36,
    }
    return bytes(data), manifest, ptrs


class BulkManifestTests(unittest.TestCase):
    def test_all_111_original_pointers_relocated(self):
        original, manifest, ptrs = synthetic_full_episode()
        patched, rows, report = build_translated_scene(original, manifest)
        self.assertEqual(len(rows), 111)
        self.assertEqual(report["modified_pointer_operands"], 111)
        self.assertEqual(report["translation_counts"], {"dialogue": 71, "speaker": 36, "unknown": 4})
        self.assertGreater(len(patched), len(original))
        reverted = bytearray(patched[:len(original)])
        for pointer, original_string in ptrs:
            updated_string = struct.unpack_from("<I", patched, pointer)[0] * 4
            self.assertGreaterEqual(updated_string, len(original))
            struct.pack_into("<I", reverted, pointer, original_string // 4)
        self.assertEqual(reverted, original)

    def test_wrong_hash_fails_closed(self):
        original, manifest, _ = synthetic_full_episode()
        manifest["original_sha256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "SHA256"):
            make_rows(original, manifest)

    def test_missing_dialogue_prevent_partial_episode(self):
        original, manifest, _ = synthetic_full_episode()
        manifest["dialogues"].pop(next(iter(manifest["dialogues"])))
        with self.assertRaisesRegex(ValueError, "71/36/4"):
            make_rows(original, manifest)

    def test_unknown_scene_rejected(self):
        _, manifest, _ = synthetic_full_episode()
        manifest["scene"] = "../../malicious.ssb"
        with self.assertRaisesRegex(ValueError, "scene basename"):
            validate_manifest(manifest)

    def test_new_linebreak_rejected(self):
        original, manifest, _ = synthetic_full_episode()
        k = next(iter(manifest["dialogues"]))
        manifest["dialogues"][k] = "A\nB▼"
        with self.assertRaisesRegex(ValueError, "linebreak"):
            make_rows(original, manifest)


if __name__ == "__main__":
    unittest.main()
