import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from extract_samples import validate_name, extract_samples


class TestSamples(unittest.TestCase):
    def test_allowed_name(self):
        self.assertEqual(validate_name("SCN_CJIN_1Y_1112x_010.ssb"), "SCN_CJIN_1Y_1112x_010.ssb")

    def test_reject_escape_or_mass_extraction(self):
        for bad in ("ALL", "../other.ssb", "/absolute.ssb", "C:/game/data.cpk", "a/../../b.ssb"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    validate_name(bad)

    def test_extract_and_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "input" / "DATA.CPK"
            source.parent.mkdir()
            source.write_bytes(b"CPK " + bytes(96))
            exe = root / "bin" / "CriPakTools.exe"
            exe.parent.mkdir()
            exe.write_bytes(b"test executable")
            output = root / "samples"

            def write_sample(*args, **kwargs):
                Path(kwargs["cwd"], "font_m.fnt").write_bytes(b"FNT0")
                return Mock(returncode=0, stdout="Extracting: font_m.fnt", stderr="")

            with patch("extract_samples.subprocess.run", side_effect=write_sample) as p:
                result = extract_samples(source, exe, output, ["font_m.fnt"])
                self.assertEqual(p.call_args.args[0][-1], "font_m.fnt")
            self.assertEqual(len(result["samples"]), 1)
            self.assertEqual(result["samples"][0]["bytes"], 4)

    def test_refuse_non_cpk_and_existing_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "DATA.CPK"
            source.write_bytes(b"XXXX")
            exe = root / "CriPakTools.exe"
            exe.write_bytes(b"dummy")
            with self.assertRaises(ValueError):
                extract_samples(source, exe, root / "samples", ["font_m.fnt"])
            source.write_bytes(b"CPK " + bytes(12))
            out = root / "samples"
            out.mkdir()
            (out / "already.txt").write_text("existing")
            with self.assertRaises(ValueError):
                extract_samples(source, exe, out, ["font_m.fnt"])


if __name__ == "__main__":
    unittest.main()
