import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from localization_audit import audit_root, category_for, make_summary, known_manifests, run


def scene():
    data = bytearray(b"\x02\x00\x00\x00" * 32)
    data.extend(bytes(256-len(data)))
    data.extend(b" START : SCN_MAIN_EXAMPLE.sss\x00")
    while len(data)%4: data.append(0)
    data.extend("会いたいです。▼".encode() + b"\x00")
    return bytes(data)


class CompleteAuditTests(unittest.TestCase):
    def test_format_coverage(self):
        for ext in (".txg",".txgtl",".gxttl",".cbg",".csu",".loc"):
            self.assertEqual(category_for(ext),"texture_or_graphics")
        for ext in (".cmed",".tipd",".tmd",".slpd",".tskd",".tskt"):
            self.assertEqual(category_for(ext),"text_or_configuration")
        self.assertEqual(category_for(".pmf"),"video")
        self.assertEqual(category_for(".lbd"),"models")
        self.assertEqual(category_for(".bin"),"unknown_review_required")
    def test_all_files_in_inventory_and_export_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data = base/"data"
            data.mkdir()
            (data/"SCN_MAIN_EXAMPLE.ssb").write_bytes(scene())
            (data/"SCREEN.loc").write_bytes(b"some image data")
            (data/"OTHER.bin").write_bytes(b"\x00\x01\xff")
            (data/"TXT.tipd").write_bytes("話です".encode())
            export = base/"private"
            result = audit_root(data,"DATA",{},export=export)
            self.assertEqual(len(result),4)
            self.assertEqual(next(x for x in result if x["path"]=="SCN_MAIN_EXAMPLE.ssb")["dialogue_candidates"],1)
            self.assertEqual(next(x for x in result if x["path"]=="SCREEN.loc")["translation_status"],"needs_decode_and_visual_text_review")
            self.assertTrue((export/"DATA"/"SCN_MAIN_EXAMPLE.csv").is_file())
            summary = make_summary(result)
            self.assertEqual(summary["graphics_awaiting_visual_review"],1)
            self.assertEqual(summary["ssb_candidate_dialogues"],1)
    def test_multiple_archive_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for folder in ("data","strm"):
                p=root/folder;p.mkdir()
                (p/"a.bin").write_bytes(b"A")
            args=SimpleNamespace(assets=root/"data",stream_assets=root/"strm",
                game_root=None,manifests=root/"missing",
                report=root/"out"/"report.json",csv=root/"out"/"inventory.csv",
                export_ssb=None)
            summary=run(args)
            self.assertEqual(summary["files_total"],2)
            self.assertEqual(summary["assets_per_archive"],{"DATA":1,"STRM":1})
            with self.assertRaises(FileExistsError):
                run(args)
    def test_nonstory_ssb_exported_but_not_patch_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/"assets"
            source.mkdir()
            data=b"\x00" * 16 + "メニュー日本語▼".encode("utf-8") + b"\x00" * 8
            (source/"script_system_status.ssb").write_bytes(data)
            rows=audit_root(source,"DATA",{},export=root/"translations")
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["translation_status"],"needs_structural_analysis_before_patch")
            self.assertIn("nonstory_ssb_unverified_offsets",rows[0]["notes"])
            self.assertTrue((root/"translations"/"DATA"/"script_system_status.csv").exists())

    def test_known_manifest_hash_matches_only_its_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            src=root/"files";src.mkdir()
            sample=scene()
            (src/"SCN_MAIN_EXAMPLE.ssb").write_bytes(sample)
            import hashlib
            manifest=root/"manifests";manifest.mkdir()
            (manifest/"good.ru.json").write_text(json.dumps({"format":"sakurasou-ssb-ru-manifest-v1",
                "scene":"SCN_MAIN_EXAMPLE.ssb","original_sha256":hashlib.sha256(sample).hexdigest()}),encoding="utf-8")
            rows=audit_root(src,"DATA",known_manifests(manifest),export=None)
            self.assertEqual(rows[0]["localized_manifest"],"good.ru.json")
            self.assertEqual(rows[0]["translation_status"],"translation_manifest_exists_needs_runtime_review")


if __name__=="__main__":
    unittest.main()
