import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from export_text_tables import candidates, scan


class TableExportTests(unittest.TestCase):
    def test_utf8_null_separated_table_and_offsets(self):
        data=b"\xff\xfe\x00" + "おはよう".encode() + b"\x00" + "世界\nです".encode()
        items=candidates(data)
        self.assertEqual([i["source_ja"] for i in items],["おはよう","世界","です"])
        self.assertEqual(items[0]["offset_hex"],"0x00000003")
        self.assertTrue(all(i["translation_ru"]=="" for i in items))

    def test_scans_only_known_files_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/"source";source.mkdir()
            (source/"table.cmed").write_bytes("日本語".encode())
            (source/"a.ssb").write_bytes("日本語".encode())
            stats=scan(source,root/"out")
            self.assertEqual(stats["scanned"],1)
            self.assertEqual(stats["files_with_candidates"],1)
            self.assertEqual(stats["candidate_fragments"],1)
            self.assertTrue((root/"out"/"table.csv").exists())
            with self.assertRaises(FileExistsError):
                scan(source,root/"out")

if __name__=="__main__":
    unittest.main()
