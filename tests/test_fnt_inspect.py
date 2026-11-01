import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from fnt_inspect import FNTFont, save_preview, MAP_OFFSET, BITMAP_OFFSET

def sample(path):
    side=20; rec=side*side//2
    out=bytearray(BITMAP_OFFSET+rec*3)
    out[:16]=b"FNT\x00"+(1).to_bytes(4,"little")+side.to_bytes(4,"little")+(4).to_bytes(4,"little")
    for ch,n in (("А",1),("Б",2)):
        i=MAP_OFFSET+ord(ch)*2;out[i:i+2]=n.to_bytes(2,"little")
    out[BITMAP_OFFSET+rec:BITMAP_OFFSET+2*rec]=b"\xf0"*rec
    path.write_bytes(out)

class Tests(unittest.TestCase):
    def test_synthetic_font_map(self):
        with TemporaryDirectory() as d:
            path=Path(d)/"font.fnt";sample(path)
            font=FNTFont(path)
            self.assertEqual(font.glyph_count,3)
            self.assertEqual(font.glyph_id("А"),1)
            self.assertEqual(font.glyph_id("я"),0)
            self.assertEqual(font.missing("Ая▼"),["я","▼"])
            self.assertEqual(font.glyph_pixels("А")[:4],bytes([255,0,255,0]))
            p=Path(d)/"preview.png";save_preview(font,p,chars="АБя")
            self.assertTrue(p.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))

    def test_reject_truncation(self):
        with TemporaryDirectory() as d:
            path=Path(d)/"bad.fnt";sample(path)
            path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaises(ValueError):
                FNTFont(path)

if __name__=="__main__":
    unittest.main()
