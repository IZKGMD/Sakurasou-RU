import csv
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
import sys
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from texture_review_pack import make_review_pack,normalize_path,selection


class TexturePackTests(unittest.TestCase):
    def test_small_pack_contains_sheets_samples_and_metadata(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            assets=root/"assets";assets.mkdir()
            pngs=root/"pngs";pngs.mkdir()
            for ext in (".csu",".cbg",".loc"):
                (assets/("test"+ext)).write_bytes(bytes([42])*1024)
            (assets/"unknown.gxt").write_bytes(b"OTHER" * 300)
            (assets/"image.gxt").write_bytes(b"GXT data placeholder")
            Image.new("RGBA",(64,48),(20,40,60,120)).save(pngs/"image.gxt.png")
            audit=root/"audit.csv"
            with audit.open("w",encoding="utf-8",newline="") as f:
                writer=csv.DictWriter(f,fieldnames=["path","extension","status"])
                writer.writeheader()
                writer.writerow({"path":"image.gxt","extension":".gxt","status":"decoded_supported"})
                writer.writerow({"path":"unknown.gxt","extension":".gxt","status":"unsupported"})
            out=root/"report.zip"
            report=make_review_pack(assets,pngs,audit,out)
            self.assertEqual(report["gxt_gxttl_total"],2)
            self.assertEqual(report["gxt_gxttl_supported"],1)
            self.assertEqual(report["gxt_gxttl_unsupported"],1)
            self.assertEqual(report["raw_sample_count"],4)
            with zipfile.ZipFile(out) as archive:
                members=archive.namelist()
                self.assertIn("contact_sheets/sheet_01.png",members)
                self.assertIn("format_samples/unsupported_gxt/unknown.gxt",members)
                self.assertIn("format_samples/other_format.csu/test.csu",members)
                meta=json.loads(archive.read("review_manifest.json"))
                self.assertEqual(meta["gxt_gxttl_unsupported"],1)
            with self.assertRaises(FileExistsError):
                make_review_pack(assets,pngs,audit,out)

    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/"ok.gxt").write_bytes(b"A")
            with self.assertRaises(ValueError):
                normalize_path(root,"../outside.gxt")

if __name__=="__main__":
    unittest.main()
