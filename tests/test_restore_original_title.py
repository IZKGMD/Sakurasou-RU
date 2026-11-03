import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from restore_original_title import fix


class RestoreTitleTests(unittest.TestCase):
    def test_restores_only_title_asset_and_checks_story_scenario(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            source=root/"old"/"DATA.CPK";source.parent.mkdir()
            source.write_bytes(b"original-patched-cpk-untouched")
            texture=root/"title_start.gxt";texture.write_bytes(b"game's original texture")
            tool=root/"CriPakTools.exe";tool.write_bytes(b"fake")
            out=root/"new"/"fixed.CPK"
            out.parent.mkdir()
            def fake_pack(source, manifest, tool, dest):
                self.assertEqual([x["entry"] for x in manifest["replacements"]],
                                 ["title_start.gxt"])
                dest.write_bytes(b"cpk-with-restored-texture")
                return {"archive_entry_count":1681}
            def fake_extract(tool, cpk, entry, folder):
                self.assertEqual(entry,"SCN_MAIN_1Y_1112__010.ssb")
                folder.mkdir()
                file=folder/entry
                file.write_bytes(b"identical-russian-ssb")
                return file
            with patch("restore_original_title.EXPECTED_ORIGINAL_GXT_SHA256",
                       __import__("hashlib").sha256(texture.read_bytes()).hexdigest()), \
                 patch("restore_original_title.build_multi",side_effect=fake_pack), \
                 patch("restore_original_title.extract_one",side_effect=fake_extract):
                result=fix(source,texture,tool,out)
            self.assertEqual(result["archive_entry_count"],1681)
            self.assertEqual(source.read_bytes(),b"original-patched-cpk-untouched")
            self.assertEqual(out.read_bytes(),b"cpk-with-restored-texture")

    def test_rejects_wrong_title_original(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            for name in ("a.CPK","b.gxt","tool.exe"):
                (root/name).write_bytes(b"incorrect")
            with self.assertRaisesRegex(ValueError,"SHA256"):
                fix(root/"a.CPK",root/"b.gxt",root/"tool.exe",root/"out"/"fixed.CPK")


if __name__=="__main__":
    unittest.main()
