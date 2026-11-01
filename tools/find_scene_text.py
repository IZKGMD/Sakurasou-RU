#!/usr/bin/env python3
"""Find a visible Japanese dialogue phrase in locally extracted Sakurasou game assets.

Read-only: scans extracted .ssb and .cmed resources. The JSON report remains
under work/ and may include snippets of original copyrighted in-game dialogue.
Neither game resources nor report should be committed to a public repository.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

EXTENSIONS = {".ssb", ".cmed"}
MAX_FILE_BYTES = 40_000_000
MAX_HITS = 40


def nearest_nul_string(data: bytes, hit: int, needle_len: int) -> tuple[int, str]:
    """Return likely NUL-terminated UTF-8 string and its initial byte position."""
    prior = data.rfind(b"\x00", max(0, hit - 16384), hit)
    start = prior + 1
    end = data.find(b"\x00", hit + needle_len, min(len(data), hit + 16384))
    if end < 0:
        end = min(len(data), hit + 16384)
    text = data[start:end].decode("utf-8", errors="replace")
    return start, text


def scan(directory: Path, needles: list[str], *, limit: int = MAX_HITS) -> dict:
    if not directory.is_dir():
        raise ValueError(f"Extracted game directory not found: {directory}")
    terms = [(term, term.encode("utf-8")) for term in needles if term.strip()]
    if not terms:
        raise ValueError("Provide at least one non-empty Japanese phrase")
    paths = sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS)
    matches = []
    scanned = 0
    total_bytes = 0
    for path in paths:
        n = path.stat().st_size
        if n > MAX_FILE_BYTES:
            continue
        data = path.read_bytes()
        scanned += 1
        total_bytes += len(data)
        for term, raw in terms:
            cursor = 0
            while len(matches) < limit:
                index = data.find(raw, cursor)
                if index < 0:
                    break
                text_offset, text = nearest_nul_string(data, index, len(raw))
                matches.append({
                    "relative_file": path.relative_to(directory).as_posix(),
                    "needle": term,
                    "hit_offset_hex": f"0x{index:X}",
                    "possible_string_offset_hex": f"0x{text_offset:X}",
                    "string_start_is_word_aligned": text_offset % 4 == 0,
                    "context_utf8": text[:240],
                })
                cursor = index + len(raw)
        if len(matches) >= limit:
            break
    return {
        "format": "Sakurasou-RU in-game Japanese text locator v1",
        "root": str(directory.resolve()),
        "files_scanned": scanned,
        "bytes_scanned": total_bytes,
        "needle_count": len(terms),
        "matches": matches,
        "note": "Matching a phrase identifies a resource; it does not prove its exact gameplay position.",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path, help="Local extracted game assets folder")
    p.add_argument("--needle", action="append", required=True, help="Japanese phrase (may be repeated)")
    p.add_argument("--report", type=Path, default=Path("work/reports/find_current_scene.json"))
    a = p.parse_args(argv)
    try:
        results = scan(a.directory, a.needle)
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    except (OSError, ValueError) as exc:
        p.error(str(exc))
    print(f"Scanned {results['files_scanned']} assets; matched {len(results['matches'])} time(s)")
    for match in results["matches"]:
        print(f"{match['relative_file']} @ {match['possible_string_offset_hex']} "
              f"(hit {match['hit_offset_hex']}): {match['context_utf8'][:140]}")
    print("Report:", a.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
