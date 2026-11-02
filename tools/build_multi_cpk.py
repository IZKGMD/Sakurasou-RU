#!/usr/bin/env python3
"""Verified multi-file CPK replacer for Sakurasou-RU PCSG00129.

CriPakTools replaces one CPK entry per invocation. Build a TEMPORARY chain of
individual CPKs in one directory, always writing a NEW output filename.
Verify every changed file can be extracted again from the final CPK, and check
full archive inventory preservation. The user's original DATA.CPK is NEVER
modified. This is slower than a native multi-entry CPK writer, but safe.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from build_test_cpk import digest, run, inventory, extract_one, _entry_matches


def validate_manifest(data: dict) -> list[dict]:
    if data.get("format") != "sakurasou-multi-cpk-v1":
        raise ValueError("Unknown multi-CPK manifest format")
    rows = data.get("replacements")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Manifest has no replacements")
    entries = set()
    validated = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f"Replacement {index} is not an object")
        entry = row.get("entry", "")
        candidate = row.get("file", "")
        expected = row.get("sha256")
        if not isinstance(entry, str) or not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9]{2,12}", entry):
            raise ValueError(f"Invalid entry name at replacement {index}")
        if not isinstance(candidate, str) or not candidate.strip():
            raise ValueError(f"Missing local filename at replacement {index}")
        if expected is not None and (not isinstance(expected, str) or
                                     not re.fullmatch("[0-9A-Fa-f]{64}", expected)):
            raise ValueError(f"Invalid SHA256 at replacement {index}")
        if entry.lower() in entries:
            raise ValueError(f"Duplicate CPK entry: {entry}")
        entries.add(entry.lower())
        validated.append({"entry": entry, "file": Path(candidate), "sha256": expected})
    return validated


def build(original: Path, manifest: dict, tool: Path, out: Path) -> dict:
    original = original.resolve(strict=True)
    tool = tool.resolve(strict=True)
    out = out.resolve()
    rows = validate_manifest(manifest)
    if not original.is_file() or not tool.is_file():
        raise ValueError("CPK and CriPakTools must be existing files")
    if out.exists():
        raise FileExistsError(f"Refusing overwrite: {out}")
    if out == original or out == tool or out.parent == original.parent:
        raise ValueError("Output must be outside the decrypted original game directory")
    if original.open("rb").read(4) != b"CPK ":
        raise ValueError("Source is not a decrypted CPK")
    resolved = []
    for row in rows:
        path = row["file"].resolve(strict=True)
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Missing or empty replacement: {path}")
        if path in (original, tool, out):
            raise ValueError("Replacement source cannot overwrite game/tool/output")
        expected = row["sha256"]
        calculated = digest(path)
        if expected and calculated.lower() != expected.lower():
            raise ValueError(f"Replacement SHA256 mismatch for {row['entry']}")
        resolved.append({**row, "path": path, "sha256": calculated})
    out.parent.mkdir(parents=True, exist_ok=True)
    needed = original.stat().st_size * 3 + 128 * 1024 * 1024
    if shutil.disk_usage(out.parent).free < needed:
        raise OSError(f"Insufficient free disk space: recommend at least {needed:,} bytes")
    source_hash = digest(original)

    with tempfile.TemporaryDirectory(prefix="sakurasou-multi-", dir=out.parent) as temp:
        tempdir = Path(temp)
        current = tempdir / "STAGE_SOURCE.CPK"
        shutil.copyfile(original, current)
        original_listing = inventory(tool, current, tempdir)
        for row in resolved:
            matches = _entry_matches(original_listing, row["entry"])
            if len(matches) != 1 or original_listing[matches[0]] != 1:
                raise ValueError(f"CPK entry missing or ambiguous: {row['entry']}")
        for index, row in enumerate(resolved, 1):
            next_file = tempdir / f"STAGE_{index:05}.CPK"
            # Passing an absolute output path is unsafe with CriPakTools: it
            # prepends the source directory. Pass only a basename.
            run(tool, str(current), row["entry"], str(row["path"]),
                next_file.name, cwd=tempdir)
            if not next_file.is_file():
                raise RuntimeError(f"Stage {index}: output CPK not created")
            with next_file.open("rb") as f:
                if f.read(4) != b"CPK ":
                    raise ValueError(f"Stage {index}: not a CPK")
            current.unlink()
            current = next_file
            print(f"[{index}/{len(resolved)}] inserted {row['entry']}", flush=True)

        final_listing = inventory(tool, current, tempdir)
        if final_listing != original_listing:
            raise ValueError("Final CPK entry inventory changed")
        for index, row in enumerate(resolved, 1):
            check_dir = tempdir / f"verify_{index:05}"
            extracted = extract_one(tool, current, row["entry"], check_dir)
            if digest(extracted) != row["sha256"]:
                raise ValueError(f"Final CPK roundtrip differs for {row['entry']}")
            print(f"[{index}/{len(resolved)}] verified {row['entry']}", flush=True)
        if digest(original) != source_hash:
            raise RuntimeError("Original CPK changed during repack!")
        result = {
            "format": "sakurasou-multi-CPK-verified-v1",
            "original_cpk_sha256": source_hash,
            "modified_cpk_sha256": digest(current),
            "original_size": original.stat().st_size,
            "modified_size": current.stat().st_size,
            "replacement_count": len(resolved),
            "archive_entry_count": sum(final_listing.values()),
            "same_inventory": True,
            "every_replacement_verified": True,
            "entries": [{"entry": r["entry"], "sha256": r["sha256"]} for r in resolved],
            "warning": "Offline CPK structural verification only. Gameplay, UI and graphics must be tested in Vita3K.",
        }
        report_path = out.with_name(out.stem + ".report.json")
        if report_path.exists():
            raise FileExistsError(f"Report already exists: {report_path}")
        staging_report = tempdir / "report.json"
        staging_report.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(current, out)
        os.replace(staging_report, report_path)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--original", type=Path, required=True, help="Original DECRYPTED DATA.CPK")
    ap.add_argument("--manifest", type=Path, required=True, help="Local list of replacement files")
    ap.add_argument("--tool", type=Path, default=Path("tools/bin/CriPakTools.exe"))
    ap.add_argument("--out", type=Path, default=Path("work/patches/DATA_MULTI_RU.CPK"))
    ap.add_argument("--build", action="store_true", help="Actually repack; otherwise dry-run")
    args = ap.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        changes = validate_manifest(manifest)
        if not args.build:
            print(f"DRY RUN: {len(changes)} replacements into NEW {args.out}")
            for r in changes[:20]:
                print(f"  {r['entry']} <= {r['file']}")
            if len(changes) > 20:
                print(f"  ... and {len(changes) - 20} more")
            return 0
        report = build(args.original, manifest, args.tool, args.out)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        ap.exit(1, f"Multi-file CPK build FAILED: {exc}\n")
    print("Verified Russian CPK:", args.out)
    print(f"Entries: {report['archive_entry_count']}; replacements verified: {report['replacement_count']}")
    print("Report:", args.out.with_name(args.out.stem + ".report.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
