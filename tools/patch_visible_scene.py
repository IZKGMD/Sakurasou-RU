#!/usr/bin/env python3
"""Make a verified experimental Russian patch for the on-screen MAIN scene.

Targets the exact text shown in the user's Vita3K screenshot. Scans an already
extracted original SSB, verifies the expected Japanese phrase and the opcode-3
pointer, appends a translated UTF-8 string, and optionally builds a local CPK.
Only proprietary *local* work/ output; never edits original game assets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from fnt_inspect import FNTFont
from ssb_patch_relocate import build as relocate_ssb
from build_test_cpk import build as rebuild_cpk

SCENES = {
    "1y": ("SCN_MAIN_1Y_1112__010.ssb", 0x2BF74),
    "2y": ("SCN_MAIN_2Y_0214__010.ssb", 0x31DC8),
}
NEEDLES = ("見事優勝したこのチームへ", "大きな拍手と歓声を")
TRANSLATION = "Итак, встречайте победителей!\nАплодисменты и громкие овации!!▼"


def make_translated_ssb(data: bytes, source_offset: int, fonts: list[FNTFont] | None = None) -> tuple[bytes, dict]:
    if source_offset % 4 or not 0 <= source_offset < len(data):
        raise ValueError(f"Invalid aligned source offset: {source_offset}")
    end = data.find(b"\x00", source_offset, min(len(data), source_offset + 4096))
    if end <= source_offset:
        raise ValueError("No NUL-terminated source at expected offset")
    source = data[source_offset:end].decode("utf-8", "strict")
    if not all(term in source for term in NEEDLES) or not source.endswith("▼"):
        raise ValueError(
            f"The screen dialogue is not located at 0x{source_offset:X} in this SSB. "
            "Stop rather than patch another string."
        )
    row = {
        "id": f"ssb_{source_offset:08x}",
        "offset_hex": f"0x{source_offset:08X}",
        "original_bytes": str(len(data[source_offset:end])),
        "source_ja": source,
        "translation_ru": TRANSLATION,
    }
    candidate, report = relocate_ssb(data, [row], fonts=fonts)
    if len(report["changes"]) != 1:
        raise ValueError("Expected precisely one relocated dialogue")
    return candidate, report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--assets", type=Path, default=Path("work/all-assets-scan"))
    ap.add_argument("--scene", choices=tuple(SCENES), default="1y")
    ap.add_argument("--cpk", type=Path, help="Original decrypted DATA.CPK, required for --build-cpk")
    ap.add_argument("--tool", type=Path, default=Path("tools/bin/CriPakTools.exe"))
    ap.add_argument("--font", action="append", type=Path, default=[], help="Optional original FNT, repeat to check both fonts")
    ap.add_argument("--out-dir", type=Path, default=Path("work/patches"))
    ap.add_argument("--report-dir", type=Path, default=Path("work/reports"))
    ap.add_argument("--build-cpk", action="store_true", help="Also rebuild and verify new isolated CPK")
    args = ap.parse_args(argv)

    scene, offset = SCENES[args.scene]
    original_ssb = args.assets / scene
    if not original_ssb.is_file():
        ap.error(f"Scene is missing: {original_ssb} (check local extraction folder)")
    if args.build_cpk and args.cpk is None:
        ap.error("--build-cpk requires --cpk pointing to ORIGINAL decrypted DATA.CPK")

    output_ssb = args.out_dir / (Path(scene).stem + "_RU_TEST.ssb")
    output_cpk = args.out_dir / ("DATA_VISIBLE_RU_TEST_" + args.scene.upper() + ".CPK")
    report_path = args.report_dir / ("visible_ru_test_" + args.scene.lower() + ".json")
    if any(path.exists() for path in (output_ssb, report_path, output_cpk)):
        ap.error("A test output already exists. Do not overwrite; move or rename it first.")
    if original_ssb.resolve() == output_ssb.resolve():
        ap.error("Never overwrite the original extracted SSB")

    try:
        fonts = [FNTFont(p) for p in args.font]
        new_data, report = make_translated_ssb(original_ssb.read_bytes(), offset, fonts)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        args.report_dir.mkdir(parents=True, exist_ok=True)
        output_ssb.write_bytes(new_data)
        report["scene_filename"] = scene
        report["original_scene_sha256"] = hashlib.sha256(original_ssb.read_bytes()).hexdigest()
        if args.build_cpk:
            cpk_report = rebuild_cpk(
                args.cpk,
                output_ssb,
                args.tool,
                output_cpk,
                entry=scene,
                expected_ssb_sha=report["patched_sha256"],
            )
            report["cpk_verified"] = True
            report["cpk_output"] = str(output_cpk)
            report["cpk_sha256"] = cpk_report["modified_cpk_sha256"]
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"EXPERIMENTAL SSB: {output_ssb}")
        if args.build_cpk:
            print(f"VERIFIED TEST CPK: {output_cpk}")
        print(f"Report: {report_path}")
        print("Only ONE dialogue translated; gameplay display remains to be tested.")
    except (OSError, ValueError, RuntimeError, AssertionError) as exc:
        ap.exit(1, f"Visible-scene patch FAILED: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
