from collections import Counter
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_test_cpk as b


class BuildTest(unittest.TestCase):
    def test_exact_entry_and_unique_count(self):
        c = Counter({"SCN_CJIN_1Y_1112x_010.ssb": 1, "foo/bar.ssb": 1})
        self.assertEqual(b._entry_matches(c, b.ENTRY_NAME), [b.ENTRY_NAME])

    def test_build_with_mocked_CriPakTool(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)
            original = p / "game" / "DATA.CPK"
            original.parent.mkdir()
            original.write_bytes(b"CPK " + b"\x12" * 320)
            tool = p / "bin" / "CriPakTools.exe"
            tool.parent.mkdir()
            tool.write_bytes(b"test")
            patched = p / "patch.ssb"
            patched.write_bytes(b"Patched bytes!")
            control = p / "original_control.ssb"
            control.write_bytes(b"Original sample")
            out = p / "out" / "DATA_test.CPK"

            def fake_run(_tool, *argv, cwd):
                if len(argv) == 1:
                    return "CriPakTools\n" + b.ENTRY_NAME + "\noriginal_control.ssb\n"
                if len(argv) == 4:
                    base, entry, repl, name = argv
                    self.assertEqual(entry, b.ENTRY_NAME)
                    self.assertEqual(name, "REBUILT.CPK")
                    (Path(base).parent / name).write_bytes(Path(base).read_bytes() + b"new")
                    return "Done"
                if len(argv) == 2:
                    path, name = argv
                    target = Path(cwd) / name
                    target.write_bytes(
                        patched.read_bytes() if name == b.ENTRY_NAME
                        else control.read_bytes()
                    )
                    return "Extracted"
                raise AssertionError(argv)

            with patch.object(b, "run", side_effect=fake_run):
                report = b.build(original, patched, tool, out,
                                 control_reference=control)
            self.assertTrue(report["patched_ssb_roundtrip_verified"])
            self.assertEqual(report["file_count"], 2)
            self.assertEqual(report["control_ssb_sha256"], b.digest(control))
            self.assertTrue(out.is_file())
            self.assertEqual(original.read_bytes(), b"CPK " + b"\x12" * 320)

    def test_fails_when_output_exists(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)
            original = p / "game" / "DATA.CPK"
            original.parent.mkdir()
            original.write_bytes(b"CPK " + bytes(320))
            tool = p / "bin" / "CriPakTools.exe"
            tool.parent.mkdir()
            tool.write_bytes(b"test")
            patched = p / "patch.ssb"
            patched.write_bytes(b"a")
            out = p / "out" / "DATA_test.CPK"
            out.parent.mkdir()
            out.write_bytes(b"previous")
            with self.assertRaises(FileExistsError):
                b.build(original, patched, tool, out)
            self.assertEqual(out.read_bytes(), b"previous")


if __name__ == "__main__":
    unittest.main()
