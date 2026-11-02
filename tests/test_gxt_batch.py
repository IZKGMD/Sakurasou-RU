import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from gxt_batch import inspect


def fake_gxt(w,h):
    data=bytearray(64+w*h*4)
    data[:4]=b"GXT\x00"
    struct.pack_into("<IIII",data,4,0x10000003,1,64,w*h*4)
    struct.pack_into("<II",data,32,64,w*h*4)
    struct.pack_into("<I",data,40,0xFFFFFFFF)
    struct.pack_into("<II",data,48,0,0x0C001000)
    struct.pack_into("<HH",data,56,w,h)
    data[60]=1
    return bytes(data)


class BatchTests(unittest.TestCase):
    def test_reports_supported_unsupported_and_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            src=root/"assets"
            src.mkdir()
            (src/"ok.gxt").write_bytes(fake_gxt(8,4))
            (src/"unsupported.gxt").write_bytes(b"WRONG HEADER")
            (src/"other.loc").write_bytes(b"Japanese on a proprietary image")
            out=root/"png"
            rows=inspect(src,export=out)
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[0]["status"],"decoded_supported")
            self.assertEqual(rows[1]["status"],"unsupported")
            self.assertTrue((out/"ok.gxt.png").is_file())
            with self.assertRaises(FileExistsError):
                inspect(src,export=out)

    def test_all_graphics_flag_includes_loc_and_nested_containers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/"assets";source.mkdir()
            loc=source/"japanese.loc"
            loc.write_bytes(fake_gxt(8,4))
            # Unknown wrapper: included but marked unsupported, not silently skipped.
            (source/"sample.csu").write_bytes(b"BAD WRAPPER")
            (source/"sample.cbg").write_bytes(b"BAD BG")
            expanded=inspect(source,all_graphics=True)
            self.assertEqual(len(expanded),3)
            self.assertEqual(sum(x["status"]=="decoded_supported" for x in expanded),1)
            self.assertEqual(sum(x["status"]=="unsupported" for x in expanded),2)
            legacy=inspect(source,all_graphics=False)
            self.assertEqual(legacy,[])

    def test_no_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                inspect(Path(tmp)/"nope")

if __name__=="__main__":
    unittest.main()
