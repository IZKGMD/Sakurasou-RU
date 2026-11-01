import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from patch_visible_scene import make_translated_ssb, TRANSLATION
from ssb_patch_relocate import references


def example():
    data = bytearray(b"\x02\x00\x00\x00"*24)
    pointer=0x14
    struct.pack_into("<I", data, pointer-4, 3)
    data.extend(bytes(0x100-len(data)))
    data.extend(b" START : SCN_MAIN_1Y_1112__010.sss\x00")
    while len(data)%4: data.append(0)
    offset=len(data)
    japanese="……それでは、見事優勝したこのチームへ、\n大きな拍手と歓声を！！▼"
    data.extend(japanese.encode("utf8") + b"\0")
    while len(data)%4:data.append(0)
    struct.pack_into("<I", data, pointer, offset//4)
    return bytes(data), offset, pointer


class Tests(unittest.TestCase):
    def test_screen_translation_and_pointer(self):
        original,offset,ptr=example()
        updated, report=make_translated_ssb(original,offset)
        self.assertEqual(report["modified_pointer_operands"],1)
        new_off=struct.unpack_from("<I",updated,ptr)[0]*4
        self.assertEqual(new_off,len(original))
        self.assertTrue(updated[new_off:].startswith(TRANSLATION.encode("utf8")))
        self.assertEqual(original[offset:len(original)],updated[offset:len(original)])
        self.assertEqual(references(original,offset,original.find(b" START : SCN_")),[ptr])
    def test_reject_wrong_offset(self):
        original,offset,_=example()
        with self.assertRaises((ValueError,UnicodeError)):
            make_translated_ssb(original,offset+4)
    def test_reject_missing_dialogue(self):
        original,offset,_=example()
        damaged=bytearray(original)
        needle = "見事優勝したこのチームへ".encode("utf-8")
        at = damaged.find(needle, offset)
        self.assertNotEqual(at, -1)
        damaged[at:at+len(needle)] = b"?" * len(needle)
        with self.assertRaises(ValueError):
            make_translated_ssb(bytes(damaged),offset)


if __name__=="__main__":
    unittest.main()
