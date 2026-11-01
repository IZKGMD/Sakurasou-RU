import csv
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "tools"))
from episode_ru import prepare, paths, read_csv, translate_dialogue, index_pointers, NAMES


def fixture():
    d=bytearray(b"\x02\x00\x00\x00"*32)
    d.extend(bytes(0x100-len(d)))
    d.extend(b" START : SCN_MAIN_1Y_1112__010.sss\x00")
    while len(d)%4:d.append(0)
    name_offset=len(d)
    d.extend("神田空太".encode()+b"\0")
    while len(d)%4:d.append(0)
    text_offset=len(d)
    d.extend("食の悩みです。\n助けてください。▼".encode()+b"\0")
    while len(d)%4:d.append(0)
    for ptr, off in ((0x14,name_offset),(0x2C,text_offset)):
        struct.pack_into("<I",d,ptr-4,3)
        struct.pack_into("<I",d,ptr,off//4)
    return bytes(d)


class EpisodeTests(unittest.TestCase):
    def test_glossary_and_scene_markers(self):
        self.assertEqual(translate_dialogue("神田空太",lambda _:None),NAMES["神田空太"])
        called=[]
        def translate(value):
            called.append(value)
            return "Это длинный перевод"
        result=translate_dialogue("食の悩みです。\n助けてください。▼",translate)
        self.assertEqual(result,"Это длинный перевод\nЭто длинный перевод▼")
        self.assertEqual(len(called),2)

    def test_machine_punctuation(self):
        result=translate_dialogue("どうして？▼",lambda _: "“Потому — что”")
        self.assertEqual(result,'"Потому - что"▼')

    def test_prepare_catches_unpatchable_and_extracts_speakers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            assets=root/"game"
            assets.mkdir()
            scene=assets/"SCN_MAIN_1Y_1112__010.ssb"
            d=fixture()
            scene.write_bytes(d)
            args=SimpleNamespace(scene="1y",assets=assets,work=root/"work")
            ps=paths(args)
            rows=prepare(args,ps)
            self.assertEqual(len(rows),2)
            self.assertEqual([r["kind"] for r in rows],["speaker","dialogue"])
            self.assertEqual(rows[0]["translation_ru"],NAMES["神田空太"])
            self.assertTrue(all(r["status"]=="ready" for r in rows))
            csv_rows=read_csv(ps["csv"])
            self.assertEqual(len(csv_rows),2)
            self.assertEqual(index_pointers(d)[int(rows[1]["offset_hex"],16)],[0x2c])
            self.assertEqual(json.loads(ps["prep_report"].read_text())["eligible_verified_one_pointer"],2)
            with self.assertRaises(FileExistsError):
                prepare(args,ps)

    def test_marker_is_not_automatically_translated(self):
        self.assertEqual(translate_dialogue("▼▽",lambda x:None),"▼▽")


if __name__=="__main__":
    unittest.main()
