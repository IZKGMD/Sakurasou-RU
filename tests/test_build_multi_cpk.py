import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
import json
from collections import Counter

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from build_multi_cpk import validate_manifest,build


def make_manifest(paths):
    return {"format":"sakurasou-multi-cpk-v1","replacements":[
       {"entry":n,"file":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
       for n,p in paths.items()
    ]}


class MultiCpkTests(unittest.TestCase):
    def test_duplicate_and_path_traversal_guard(self):
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            validate_manifest({"format":"sakurasou-multi-cpk-v1","replacements":[
                {"entry":"X.ssb","file":"a"},{"entry":"x.ssb","file":"b"}]})
        with self.assertRaisesRegex(ValueError,"Invalid entry"):
            validate_manifest({"format":"sakurasou-multi-cpk-v1","replacements":[
                {"entry":"../bad.ssb","file":"a"}]})

    def test_two_entries_preserved_verified_and_original_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            original=root/"orig"/"DATA.CPK";original.parent.mkdir()
            original.write_bytes(b"CPK "+b"\x00"*64)
            replacements=root/"changes";replacements.mkdir()
            a=replacements/"A.ssb";b=replacements/"B.ssb"
            a.write_bytes(b"NEW_A");b.write_bytes(b"NEW_B")
            tool=root/"CriPakTools.exe";tool.write_bytes(b"fake tool")
            out=root/"out"/"DATA_MULTI_RU.CPK"
            source_before=original.read_bytes()
            states={str(original.resolve()):{}}
            expected=Counter({"A.ssb":1,"B.ssb":1,"C.ssb":1})
            def fake_run(toolpath,*args,cwd):
                self.assertEqual(len(args),4)
                inp, entry, replacement, name=args
                stage=Path(cwd)/name
                self.assertEqual(Path(name).name,name)
                state=dict(states.get(str(Path(inp).resolve()), {}))
                state[entry]=Path(replacement).read_bytes()
                stage.write_bytes(b"CPK "+b"\x00"*64)
                states[str(stage.resolve())]=state
            def fake_inventory(toolpath,cpk,cwd):
                return expected.copy()
            def fake_extract(toolpath,cpk,entry,cwd):
                Path(cwd).mkdir()
                target=Path(cwd)/entry
                target.write_bytes(states[str(cpk.resolve())].get(entry,b"ORIGINAL"))
                return target
            with patch("build_multi_cpk.run",side_effect=fake_run), \
                 patch("build_multi_cpk.inventory",side_effect=fake_inventory), \
                 patch("build_multi_cpk.extract_one",side_effect=fake_extract):
                report=build(original,make_manifest({"A.ssb":a,"B.ssb":b}),tool,out)
            self.assertEqual(original.read_bytes(),source_before)
            self.assertTrue(out.is_file())
            self.assertEqual(report["replacement_count"],2)
            self.assertTrue(report["every_replacement_verified"])
            self.assertTrue((out.parent/"DATA_MULTI_RU.report.json").exists())


if __name__=="__main__":
    unittest.main()
