#!/usr/bin/env python3
"""Read-only Japanese text candidate export from Sakurasou binary tables.

Targets .cmed .tipd .tmd .slpd .tskd .tskt, whose offset and pointer formats
are NOT yet fully understood. Does not change, patch or repack game assets.
Only exports user-local CSVs under work/. Japanese may be stored in encodings
or compressed containers that this simple UTF-8 heuristic cannot recover.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import re

EXTENSIONS = {".cmed", ".tipd", ".tmd", ".slpd", ".tskd", ".tskt"}
JP = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
MAX_CANDIDATE_BYTES = 16 * 1024


def candidates(data: bytes) -> list[dict]:
    found = []
    # Split on NUL because these tables often hold C-style text. We retain
    # file offsets for later structural analysis, NOT for safe replacement.
    offset = 0
    for fragment in data.split(b"\x00"):
        end_offset = offset + len(fragment)
        if fragment and len(fragment) <= MAX_CANDIDATE_BYTES:
            # Lines inside one NUL-delimited chunk need their own offsets
            # when we show them to local translators.
            inside = 0
            for line in fragment.splitlines(keepends=True):
                stripped = line.rstrip(b"\r\n")
                if stripped:
                    try:
                        text = stripped.decode("utf-8", "strict")
                    except UnicodeDecodeError:
                        text = ""
                    if text and JP.search(text):
                        found.append({
                            "offset_hex": f"0x{offset + inside:08X}",
                            "bytes": len(stripped),
                            "source_ja": text,
                            "translation_ru": "",
                            "confidence": "utf8_candidate_only",
                            "notes": "UNVERIFIED: pointer/reinsertion layout unknown",
                        })
                inside += len(line)
        offset = end_offset + 1
    return found


def scan(root: Path, output: Path) -> dict:
    if not root.is_dir():
        raise FileNotFoundError(f"Not an extracted game directory: {root}")
    totals = {"scanned": 0, "files_with_candidates": 0, "candidate_fragments": 0}
    for file in sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS):
        totals["scanned"] += 1
        if file.stat().st_size > 32 * 1024 * 1024:
            continue
        entries = candidates(file.read_bytes())
        if not entries:
            continue
        dst = output / file.relative_to(root).with_suffix(".csv")
        if dst.exists():
            raise FileExistsError(f"Refusing to overwrite existing local translation: {dst}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        with dst.open("w", encoding="utf-8-sig", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=list(entries[0]))
            writer.writeheader()
            writer.writerows(entries)
        totals["files_with_candidates"] += 1
        totals["candidate_fragments"] += len(entries)
    return totals


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--assets", type=Path, default=Path("work/all-assets-scan"))
    p.add_argument("--out", type=Path, default=Path("work/translations/table-candidates"))
    args = p.parse_args(argv)
    try:
        stats = scan(args.assets, args.out)
    except (OSError, ValueError) as e:
        p.exit(1, f"Table extraction failed: {e}\n")
    print(f"Text tables scanned: {stats['scanned']}")
    print(f"Files containing UTF-8 candidates: {stats['files_with_candidates']}")
    print(f"Candidate fragments: {stats['candidate_fragments']}")
    print("Local candidates:", args.out)
    print("These are NOT validated offsets for reinsertion or full text coverage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
