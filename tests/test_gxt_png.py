import struct
import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from gxt_png import (
    UnsupportedTexture, decode, encode, encode_gxt, gxt_info, xttl_info
)


def fake_gxt(width, height, fill=0x7D):
    header = bytearray(64)
    header[:4] = b"GXT\x00"
    struct.pack_into("<IIII", header, 4, 0x10000003, 1, 64, width*height*4)
    struct.pack_into("<II", header, 32, 64, width*height*4)
    struct.pack_into("<I", header, 40, 0xFFFFFFFF)
    struct.pack_into("<II", header, 48, 0, 0x0C001000)
    struct.pack_into("<HH", header, 56, width, height)
    header[60] = 1
    return bytes(header) + bytes([fill]) * (width*height*4)


def fake_xttl():
    # Width 8 and displayed height 6: bottom two pixels per tile remain padded.
    cols, rows = 2, 2
    tw, th = 4, 4
    offset = 48
    stride = 64 + tw*th*4
    header = bytearray(48)
    header[:4] = b"XTTL"
    struct.pack_into("<9I", header, 4,
                     offset+cols*rows*stride,
                     cols*tw, 6, tw, th, cols, rows, offset, stride)
    return bytes(header) + b"".join(fake_gxt(tw, th, i * 33) for i in range(4))


class GxtConversionTests(unittest.TestCase):
    def test_rectangular_gxt_rgba_pixel_roundtrip(self):
        original = fake_gxt(8, 4)
        image = Image.new("RGBA", (8, 4))
        for y in range(4):
            for x in range(8):
                image.putpixel((x,y), ((x*31)%256,(y*47)%256,
                                        (x+y*7)%256,(x*y*7)%256))
        edited = encode(original,image)
        self.assertEqual(len(edited),len(original))
        self.assertEqual(decode(edited).tobytes(),image.tobytes())
        self.assertEqual(encode(edited,decode(edited)),edited)
        self.assertEqual(edited[:64],original[:64])

    def test_original_binary_preserved_exactly(self):
        source = fake_gxt(16, 4)
        self.assertEqual(encode(source,decode(source)),source)

    def test_xttl_roundtrip_preserves_padding_and_header(self):
        original = fake_xttl()
        self.assertEqual(xttl_info(original).height,6)
        self.assertEqual(encode(original,decode(original)),original)
        image = decode(original)
        self.assertEqual(image.size,(8,6))
        image.putpixel((7,5),(211,33,77,255))
        edited = encode(original,image)
        self.assertEqual(len(edited),len(original))
        self.assertEqual(decode(edited).tobytes(),image.tobytes())
        self.assertEqual(edited[:48],original[:48])
        # All bottom padded pixels of last row must remain unchanged.
        a=original[48+2*(64+4*4*4):]
        b=edited[48+2*(64+4*4*4):]
        self.assertGreater(len(a),0)
        self.assertEqual(encode(edited,decode(edited)),edited)

    def test_p8_palette_roundtrip_and_new_color(self):
        header=bytearray(fake_gxt(8,4))
        w,h=8,4
        header=header[:64]
        struct.pack_into("<II",header,12,64,w*h+1024)
        struct.pack_into("<II",header,32,64,w*h)
        struct.pack_into("<I",header,40,0)
        struct.pack_into("<I",header,52,0x95001000)
        # The palette has duplicate colors in unused slots, like the game.
        pixels=bytes([240+(i%16) for i in range(w*h)])
        palette=bytearray(1024)
        for i in range(256):
            r,g,b,a=255,255,255,(i%16)*17
            palette[i*4:i*4+4]=bytes((b,g,r,a))
        raw=bytes(header)+pixels+bytes(palette)
        self.assertEqual(encode(raw,decode(raw)),raw)
        changed=decode(raw)
        changed.putpixel((3,2),(23,45,67,200))
        repacked=encode(raw,changed)
        self.assertEqual(len(repacked),len(raw))
        self.assertEqual(decode(repacked).tobytes(),changed.tobytes())
        # Previous pixel colors remain untouched.
        self.assertEqual(decode(repacked).getpixel((0,0)),decode(raw).getpixel((0,0)))

    def test_xttl_padded_right_and_bottom(self):
        cols,rows,tw,th=2,2,8,8
        stride=64+tw*th*4
        header=bytearray(48)
        header[:4]=b"XTTL"
        struct.pack_into("<9I",header,4,48+cols*rows*stride,13,11,tw,th,cols,rows,48,stride)
        original=bytes(header)+b"".join(fake_gxt(tw,th,n*30) for n in range(cols*rows))
        self.assertEqual(encode(original,decode(original)),original)
        edit=decode(original)
        edit.putpixel((12,10),(20,30,40,255))
        modified=encode(original,edit)
        self.assertEqual(decode(modified).tobytes(),edit.tobytes())
        self.assertEqual(encode(modified,decode(modified)),modified)

    def test_csu_cbg_nested_embedded_texture_with_trailing_metadata(self):
        nested=fake_xttl()
        for magic,version,offset,trailer in ((b"CSU\\x00",0x20,0x30,b"UNALTERED_TRAILER"),
                                             (b"CBG\\x00",0x10,0x20,b"")):
            # Backslashes in this string are escaped in the test source below.
            magic=magic.replace(b"\\\\x00",b"\\x00")
            prefix=bytearray(offset)
            prefix[:4]=magic
            struct.pack_into("<II",prefix,4,version,offset)
            original=bytes(prefix)+nested+trailer
            self.assertEqual(encode(original,decode(original)),original)
            img=decode(original)
            img.putpixel((2,1),(101,102,103,255))
            rewritten=encode(original,img)
            self.assertEqual(rewritten[:offset],original[:offset])
            self.assertEqual(rewritten[offset+len(nested):],trailer)
            self.assertEqual(decode(rewritten).tobytes(),img.tobytes())

    def test_rejects_wrong_format_and_dimensions(self):
        d=bytearray(fake_gxt(4,4))
        struct.pack_into("<I",d,52,0x85000000)
        with self.assertRaises(UnsupportedTexture):
            gxt_info(bytes(d))
        with self.assertRaisesRegex(ValueError,"dimensions"):
            encode(fake_gxt(4,4),Image.new("RGBA",(8,8)))


if __name__ == "__main__":
    unittest.main()
