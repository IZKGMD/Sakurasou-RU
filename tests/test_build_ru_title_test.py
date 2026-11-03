import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from build_ru_title_test import prepare


class TitleTestBuilderTests(unittest.TestCase):
    def test_prepare_writes_separate_gxt_and_png_without_changing_source(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            original=root/"original.gxt";original.write_bytes(b"real-user-game-texture-stands-in")
            new=root/"patches"/"title_start_RU_TEST.gxt"
            png=root/"patches"/"title_start_RU_TEST.png"
            img=Image.new("RGBA",(512,64),(5,20,100,255))
            with patch("build_ru_title_test.make_label",return_value=(img,b"modified-gxt-test")):
                sha=prepare(original,new,png)
            self.assertTrue(new.is_file() and png.is_file())
            self.assertEqual(original.read_bytes(),b"real-user-game-texture-stands-in")
            self.assertEqual(new.read_bytes(),b"modified-gxt-test")
            with self.assertRaises(FileExistsError):
                prepare(original,new,png)


if __name__=="__main__":
    unittest.main()
