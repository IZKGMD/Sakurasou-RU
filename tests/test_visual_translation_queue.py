import csv
import json
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from visual_translation_queue import load_queue, priority, produce


def minimal_gxt(w=8,h=4):
    data=bytearray(64+w*h*4)
    data[:4]=b"GXT\x00"
    struct.pack_into("<IIII",data,4,0x10000003,1,64,w*h*4)
    struct.pack_into("<II",data,32,64,w*h*4)
    struct.pack_into("<I",data,40,0xFFFFFFFF)
    struct.pack_into("<II",data,48,0,0x0C001000)
    struct.pack_into("<HH",data,56,w,h)
    data[60]=1
    return bytes(data)


class VisualReviewTests(unittest.TestCase):
    def test_queue_order_and_batch_coverage(self):
        self.assertLess(priority("option_text.gxt"),priority("random_char.csu"))
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            root=base/"assets";root.mkdir()
            for name in ("title_start.gxt","background.cbg","character.csu","tips_title.loc"):
                (root/name).write_bytes(minimal_gxt())
            audit=base/"all_graphics_v2.csv"
            with audit.open("w",encoding="utf-8-sig",newline="") as f:
                writer=csv.DictWriter(f,fieldnames=["path","extension","status","width","height"])
                writer.writeheader()
                for name in ("character.csu","background.cbg","title_start.gxt","tips_title.loc"):
                    writer.writerow({"path":name,"extension":Path(name).suffix,
                                     "status":"decoded_supported","width":8,"height":4})
            queue=load_queue(audit)
            self.assertEqual(len(queue),4)
            self.assertEqual(queue[0]["path"],"title_start.gxt")
            a=base/"a.zip";b=base/"b.zip"
            r1=produce(root,audit,a,batch=1,batch_size=2,full_size=1)
            r2=produce(root,audit,b,batch=2,batch_size=2,full_size=1)
            self.assertEqual(r1["range_inclusive"],[1,2])
            self.assertEqual(r2["range_inclusive"],[3,4])
            self.assertEqual(r2["next_batch"],None)
            with zipfile.ZipFile(a) as z:
                self.assertIn("review.csv",z.namelist())
                self.assertIn("sheets/part_01_sheet_01.png",z.namelist())
                data=json.loads(z.read("index.json"))
                self.assertEqual(data["total_graphics"],4)
                self.assertEqual(data["decode_failures"],[])
                self.assertNotIn("title_start.gxt",z.namelist()) # No game binaries
            with self.assertRaises(FileExistsError):
                produce(root,audit,a,batch=1,batch_size=2)
    def test_reject_unresolved_format_and_batch_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            source=base/"bad.csv"
            source.write_text("path,status,extension,width,height\nbad.gxt,unsupported,.gxt,8,4\n")
            with self.assertRaisesRegex(ValueError,"Unresolved"):
                load_queue(source)
            source.write_text("path,status,extension,width,height\nok.gxt,decoded_supported,.gxt,8,4\n")
            assets=base/"assets";assets.mkdir()
            (assets/"ok.gxt").write_bytes(minimal_gxt())
            with self.assertRaisesRegex(ValueError,"outside total"):
                produce(assets,source,base/"skip.zip",batch=2,batch_size=1)

if __name__=="__main__":
    unittest.main()
