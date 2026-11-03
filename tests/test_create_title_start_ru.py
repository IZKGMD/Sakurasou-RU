import hashlib
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import ImageFont

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from create_title_start_ru import make_label
from gxt_png import decode


def source_gxt():
    w,h=512,64
    header=bytearray(64)
    header[:4]=b"GXT\x00"
    struct.pack_into("<IIII",header,4,0x10000003,1,64,w*h*4)
    struct.pack_into("<II",header,32,64,w*h*4)
    struct.pack_into("<I",header,40,0xFFFFFFFF)
    struct.pack_into("<II",header,48,0,0x0C001000)
    struct.pack_into("<HH",header,56,w,h)
    header[60]=1
    return bytes(header)+bytes(w*h*4)


class TitleStartRuTests(unittest.TestCase):
    def test_generate_exact_texture_format_and_russian_pixels(self):
        source=source_gxt()
        with patch("create_title_start_ru.EXPECTED_SHA256",
                   hashlib.sha256(source).hexdigest()):
            font=ImageFont.load_default(size=38)
            preview,repacked=make_label(source,font=font)
        self.assertEqual(preview.size,(512,64))
        self.assertEqual(len(repacked),len(source))
        self.assertEqual(repacked[:64],source[:64])
        self.assertNotEqual(repacked,source)
        self.assertEqual(decode(repacked).tobytes(),preview.tobytes())
    def test_refuse_wrong_original_version(self):
        with self.assertRaisesRegex(ValueError,"SHA256"):
            make_label(source_gxt(),font=ImageFont.load_default(size=38))


if __name__=="__main__":
    unittest.main()
