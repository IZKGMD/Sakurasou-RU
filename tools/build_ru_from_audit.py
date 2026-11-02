#!/usr/bin/env python3
"""Apply a Russian-only translation manifest to a user's own extracted SSB.

For every translation, the LOCAL extracted Japanese CSV is checked byte-for-byte
against the LOCAL original game file. Original Japanese is never on GitHub.
The existing opcode-3 relocation patcher refuses ambiguous references.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from ssb_extract import iter_strings, find_story_start, classify
from ssb_patch_relocate import build as relocate
from fnt_inspect import FNTFont
from build_multi_cpk import build as multi_cpk


def translate(data: bytes, audit_csv: Path, manifest: dict, *, fonts: list[Path] | None = None):
    name = manifest.get("scene", "")
    if manifest.get("format") != "sakurasou-ru-audit-manifest-v1":
        raise ValueError("Unrecognized translation manifest")
    if not re.fullmatch(r"SCN_[A-Za-z0-9_]+\.ssb", name):
        raise ValueError("Unsafe or nonstory SSB filename")
    entries = manifest.get("dialogues")
    if not isinstance(entries, dict) or not entries:
        raise ValueError("Missing translated dialogues")
    glossary = manifest.get("glossary", {})
    if not isinstance(glossary, dict):
        raise ValueError("Invalid speaker glossary")
    with audit_csv.open(encoding="utf-8-sig", newline="") as fp:
        original_csv = list(csv.DictReader(fp))
    if len(original_csv) != len(entries):
        raise ValueError(f"Not full episode: {len(entries)} translations for {len(original_csv)} source rows")
    boundary = find_story_start(data)
    if boundary is None or boundary % 4:
        raise ValueError("Unknown SSB layout; do not use this patcher for SCR_ or script_*")
    aligned = {entry["offset"]: entry for entry in iter_strings(data, boundary)}
    prepared = []
    used = set()
    for row in original_csv:
        try:
            offset = int(row["offset_hex"], 16)
            source = row["source_ja"]
            amount = int(row["original_bytes"])
        except (ValueError, KeyError) as e:
            raise ValueError("Invalid original local CSV") from e
        key = f"0x{offset:08X}"
        if key not in entries or key in used:
            raise ValueError(f"Missing or repeated translation at {key}")
        used.add(key)
        item = aligned.get(offset)
        if (item is None or item["source"] != source or
                item["byte_len"] != amount or
                data[offset:offset + amount] != source.encode("utf-8") or
                data[offset + amount:offset + amount + 1] != b"\x00"):
            raise ValueError(f"Original source mismatch at {key}")
        if classify(source) != "text_candidate":
            raise ValueError(f"Not a dialogue at {key}")
        prepared.append(_record(item, entries[key]))
    for item in aligned.values():
        translated = glossary.get(item["source"])
        if translated and classify(item["source"]) == "speaker_candidate":
            prepared.append(_record(item, translated))
    if not prepared:
        raise ValueError("Empty translation set")
    prepared.sort(key=lambda r: int(r["offset_hex"], 16))
    if len(prepared) != len({r["offset_hex"] for r in prepared}):
        raise ValueError("Duplicate source string")
    for font_path in fonts or []:
        font = FNTFont(font_path)
        for row in prepared:
            visible = re.sub(r"†\d+‡|‡", "", row["translation_ru"])
            missing = font.missing(visible)
            if missing:
                raise ValueError(f"{font_path.name}: unsupported glyphs {missing} at {row['offset_hex']}")
    patched, report = relocate(data, prepared)
    if report["modified_pointer_operands"] != len(prepared):
        raise AssertionError("Not all translation pointers were changed")
    report["scene"] = name
    report["source_dialogues_verified"] = len(original_csv)
    report["translated_speaker_labels"] = len(prepared) - len(original_csv)
    report["gameplay_tested"] = False
    return patched, report


def _record(item: dict, translated: str) -> dict:
    if not isinstance(translated, str) or not translated.strip():
        raise ValueError("Translation is empty/non-string")
    source = item["source"]
    if source.count("\n") != translated.count("\n"):
        raise ValueError(f"Linebreaks differ at 0x{item['offset']:X}")
    if any(source.count(m) != translated.count(m) for m in ("▼", "▽")):
        raise ValueError(f"Control markers differ at 0x{item['offset']:X}")
    if any(opener not in translated for opener in re.findall(r"†\d+‡", source)):
        raise ValueError(f"Formatting tag missing at 0x{item['offset']:X}")
    if source.count("‡") != translated.count("‡"):
        raise ValueError(f"Formatting tag closes missing at 0x{item['offset']:X}")
    if any(len(re.sub(r"†\d+‡|‡", "", line)) > 43 for line in translated.rstrip("▼▽").split("\n")):
        raise ValueError(f"Display line too long at 0x{item['offset']:X}")
    return {
        "id": f"ssb_{item['offset']:08x}",
        "offset_hex": f"0x{item['offset']:08X}",
        "original_bytes": item["byte_len"],
        "source_ja": source,
        "translation_ru": translated,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, default=Path("translations/MAIN_1Y_1112__020.ru.json"))
    p.add_argument("--assets", type=Path, default=Path("work/all-assets-scan"))
    p.add_argument("--audit-csv-dir", type=Path, default=Path("work/translations/all-ssb-candidates/DATA"))
    p.add_argument("--out-dir", type=Path, default=Path("work/patches"))
    p.add_argument("--original-cpk", type=Path, help="Original decrypted DATA.CPK")
    p.add_argument("--first-ssb", type=Path, default=Path("work/patches/SCN_MAIN_1Y_1112__010_FULL_RU.ssb"))
    p.add_argument("--build-combined", action="store_true", help="Build ONE CPK containing both translated scenes")
    args = p.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        name = manifest.get("scene", "")
        source_path = args.assets / name
        source = source_path.read_bytes()
        csv_path = args.audit_csv_dir / f"{Path(name).stem}.csv"
        output = args.out_dir / f"{Path(name).stem}_FULL_RU.ssb"
        report_path = output.with_name(output.stem + ".report.json")
        combined = args.out_dir / "DATA_MAIN_1Y_010_020_RU.CPK"
        if any(path.exists() for path in
               ([output, report_path, combined] if args.build_combined else [output, report_path])):
            raise FileExistsError("Output already exists. Refusing overwrite.")
        if output.resolve() == source_path.resolve():
            raise ValueError("Cannot overwrite original SSB")
        if args.build_combined and (not args.original_cpk or not args.first_ssb.is_file()):
            raise ValueError("Combined CPK requires --original-cpk and the already translated 010 SSB")
        fonts = [Path("work/samples/font_m.fnt"), Path("work/samples/font_s.fnt")]
        data, report = translate(source, csv_path, manifest, fonts=fonts)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        if args.build_combined:
            combined_manifest = {
                "format": "sakurasou-multi-cpk-v1",
                "replacements": [
                    {"entry": "SCN_MAIN_1Y_1112__010.ssb", "file": str(args.first_ssb)},
                    {"entry": name, "file": str(output)},
                ],
            }
            combined_report = multi_cpk(args.original_cpk, combined_manifest,
                                        Path("tools/bin/CriPakTools.exe"), combined)
            report["combined_cpk_verified"] = combined_report["every_replacement_verified"]
            report["combined_cpk"] = str(combined)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, ValueError, RuntimeError, KeyError, AssertionError) as error:
        p.exit(1, f"Audit-manifest translation FAILED: {error}\n")
    print(f"Validated + translated: {report['source_dialogues_verified']} dialogue lines and {report['translated_speaker_labels']} names")
    print("Russian SSB:", output)
    if args.build_combined:
        print("Two-scene CPK:", combined)
    print("Report:", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
