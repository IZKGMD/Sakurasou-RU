#!/usr/bin/env python3
"""Build a locally verifiable Sakurasou-RU translated scene from a text-only manifest.

The repo contains ONLY Russian translation data and offsets, not original game
resources. Read the user's own extracted SSB; verify hash, string boundaries,
linebreaks, control markers, unique opcode-3 pointers and font coverage.
Optionally build DATA.CPK through the existing checked CriPakTools wrapper.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from ssb_extract import iter_strings, find_story_start, classify
from ssb_patch_relocate import build as relocate_ssb
from fnt_inspect import FNTFont
from build_test_cpk import build as build_cpk

DEFAULT_MANIFEST = Path("translations/MAIN_1Y_1112__010.ru.json")
DEFAULT_FONTS = [Path("work/samples/font_m.fnt"), Path("work/samples/font_s.fnt")]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_manifest(m: dict) -> None:
    if m.get("format") != "sakurasou-ssb-ru-manifest-v1":
        raise ValueError("Unsupported translation manifest version")
    if m.get("title_id") != "PCSG00129":
        raise ValueError("Wrong game title ID")
    if not re.fullmatch(r"SCN_[a-zA-Z0-9_]+\.ssb", m.get("scene", "")):
        raise ValueError("Invalid scene basename")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", m.get("original_sha256", "")):
        raise ValueError("Manifest requires exact original SSB SHA256")
    if not isinstance(m.get("dialogues"), dict) or not m["dialogues"]:
        raise ValueError("Missing dialogue translations")
    if not isinstance(m.get("speakers"), dict) or not m["speakers"]:
        raise ValueError("Missing speaker translations")
    if m.get("expected_counts") != {"dialogue": 71, "speaker": 36, "unknown": 4}:
        raise ValueError("This release targets exactly the verified first episode")
    if m.get("max_display_chars") != 36:
        raise ValueError("Expected manually checked line-width budget")


def make_rows(original: bytes, manifest: dict) -> tuple[list[dict], Counter]:
    validate_manifest(manifest)
    if sha256(original).lower() != manifest["original_sha256"].lower():
        raise ValueError("Original SSB SHA256 mismatch; do not patch this game version")
    boundary = find_story_start(original)
    if boundary is None or boundary % 4:
        raise ValueError("Unknown/un-aligned SSB scene boundary")
    rows = []
    counts = Counter()
    dialogue_keys = set()
    for item in iter_strings(original, boundary):
        offset, byte_count, source = item["offset"], item["byte_len"], item["source"]
        key = f"0x{offset:08X}"
        if key in manifest["dialogues"]:
            kind = "dialogue"
            translated = manifest["dialogues"][key]
            if classify(source) != "text_candidate":
                raise ValueError(f"Expected Japanese dialogue at {key}")
            dialogue_keys.add(key)
        elif source in manifest["speakers"]:
            kind = "speaker"
            translated = manifest["speakers"][source]
            if classify(source) != "speaker_candidate":
                raise ValueError(f"Expected Japanese speaker label at {key}")
        elif source == "？？？":
            kind = "unknown"
            translated = manifest.get("unknown_speaker")
        else:
            continue

        if not isinstance(translated, str) or not translated:
            raise ValueError(f"Missing translation for {kind} at {key}")
        if "\x00" in translated or any(ord(ch) < 32 and ch != "\n" for ch in translated):
            raise ValueError(f"Invalid control char at {key}")
        if source.count("\n") != translated.count("\n"):
            raise ValueError(f"Changed linebreak count at {key}")
        for marker in ("▼", "▽"):
            if source.count(marker) != translated.count(marker):
                raise ValueError(f"Changed scene marker {marker} at {key}")
        if "†91‡" in source and ("†91‡" not in translated or "‡」" not in translated):
            raise ValueError(f"Colored title formatting at {key} must be retained")
        if any(len(line) > manifest["max_display_chars"]
               for line in translated.rstrip("▼▽").split("\n")):
            raise ValueError(f"Text too wide for reviewed limit at {key}")
        counts[kind] += 1
        rows.append({
            "id": f"ssb_{offset:08x}",
            "offset_hex": key,
            "original_bytes": byte_count,
            "kind": kind,
            "source_ja": source,
            "translation_ru": translated,
        })
    if dialogue_keys != set(manifest["dialogues"]):
        raise ValueError(f"Unmatched dialogue offsets: {sorted(set(manifest['dialogues']) - dialogue_keys)}")
    if dict(counts) != manifest["expected_counts"]:
        raise ValueError(f"Expected 71/36/4 original strings, got {dict(counts)}")
    if len(rows) != len({r["offset_hex"] for r in rows}):
        raise ValueError("Repeated text offsets")
    return rows, counts


def check_fonts(rows: list[dict], fonts: list[Path]) -> None:
    for font_path in fonts:
        font = FNTFont(font_path)
        for row in rows:
            # †91‡ and the matching trailing ‡ are original engine markup.
            visible = re.sub(r"†[0-9]+‡|‡", "", row["translation_ru"])
            unsupported = font.missing(visible)
            if unsupported:
                raise ValueError(
                    f"{font_path.name}: unsupported {unsupported} at {row['offset_hex']}"
                )


def build_translated_scene(original: bytes, manifest: dict, fonts: list[Path] | None = None):
    rows, counts = make_rows(original, manifest)
    check_fonts(rows, fonts or [])
    patched, report = relocate_ssb(
        original, rows, expected_sha=manifest["original_sha256"]
    )
    if report["modified_pointer_operands"] != len(rows):
        raise AssertionError("Not every original opcode-3 pointer was modified")
    report["translation_manifest"] = manifest["scene"]
    report["translation_counts"] = dict(counts)
    report["font_checked"] = [p.name for p in fonts or []]
    report["gameplay_display_verified"] = False
    return patched, rows, report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--assets", type=Path, default=Path("work/all-assets-scan"))
    ap.add_argument("--cpk", type=Path, help="Original decrypted DATA.CPK; for --build-cpk")
    ap.add_argument("--build-cpk", action="store_true", help="Explicitly build and verify translated DATA.CPK")
    ap.add_argument("--tool", type=Path, default=Path("tools/bin/CriPakTools.exe"))
    ap.add_argument("--font", action="append", type=Path, help="Original font, repeat for medium and small")
    ap.add_argument("--skip-font-check", action="store_true")
    ap.add_argument("--out-dir", type=Path, default=Path("work/patches"))
    ap.add_argument("--csv-dir", type=Path, default=Path("work/translations"))
    args = ap.parse_args(argv)

    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        validate_manifest(manifest)
        scene = manifest["scene"]
        source = args.assets / scene
        source_data = source.read_bytes()
        stem = Path(scene).stem
        ssb_out = args.out_dir / f"{stem}_FULL_RU.ssb"
        cpk_out = args.out_dir / "DATA_MAIN_1Y_FULL_RU.CPK"
        csv_out = args.csv_dir / f"{stem}_FULL_RU.csv"
        report_out = args.out_dir / f"{stem}_FULL_RU.report.json"
        outputs = [ssb_out, csv_out, report_out]
        if args.build_cpk:
            outputs += [cpk_out, cpk_out.with_name(cpk_out.stem + ".report.json")]
            if args.cpk is None:
                raise ValueError("--cpk is required for --build-cpk")
        if len({p.resolve() for p in outputs}) != len(outputs) or any(
            p.exists() or p.resolve() in (source.resolve(), args.manifest.resolve())
            for p in outputs
        ):
            raise ValueError("Output exists, is duplicated, or would overwrite an input")
        fonts = [] if args.skip_font_check else (args.font if args.font else DEFAULT_FONTS)
        patched, rows, report = build_translated_scene(source_data, manifest, fonts)
        ssb_out.parent.mkdir(parents=True, exist_ok=True)
        csv_out.parent.mkdir(parents=True, exist_ok=True)
        ssb_out.write_bytes(patched)
        with csv_out.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        if args.build_cpk:
            cpk_report = build_cpk(
                args.cpk, ssb_out, args.tool, cpk_out, entry=scene,
                expected_ssb_sha=report["patched_sha256"]
            )
            report["cpk_roundtrip_verified"] = cpk_report["patched_ssb_roundtrip_verified"]
            report["cpk_sha256"] = cpk_report["modified_cpk_sha256"]
        report_out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    except (ValueError, OSError, KeyError, AssertionError, RuntimeError) as exc:
        ap.exit(1, f"Sakurasou bulk patch failed: {exc}\n")
    print("Localized:", len(rows), "entries (71 dialogue, 36 named, 4 unknown)")
    print("Russian SSB:", ssb_out)
    print("Local source+translation CSV:", csv_out)
    if args.build_cpk:
        print("Verified CPK:", cpk_out)
    print("Report:", report_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
