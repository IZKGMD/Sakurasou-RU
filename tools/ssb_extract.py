#!/usr/bin/env python3
"""Heuristic, read-only extractor for Sakurasou PCSG00129 SSB UTF-8 strings.

Outputs CSV LOCALLY from the user's own game file. NOT a bytecode parser or
repacker; source offset references and variable length replacement are not safe.
Never commit generated CSV or original game scripts to a public repository.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import unicodedata

MARKER = b" START : SCN_"
VOICE_RE = re.compile(r"^(?:[A-Z0-9_-]+/)?V_[A-Z0-9_-]+\.hca$", re.I)
JP_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
MAX_STRING_BYTES = 4096


def find_story_start(data: bytes) -> int | None:
    at = data.find(MARKER)
    if at < 0:
        return None
    return at


def iter_strings(data: bytes, start: int = 0):
    """Yield aligned, null-terminated UTF-8 strings, without byte edits."""
    for i in range((start + 3) & ~3, len(data), 4):
        if i and data[i - 1] != 0:
            continue
        end = data.find(b"\x00", i, min(len(data), i + MAX_STRING_BYTES + 1))
        if end < 0 or end == i:
            continue
        raw = data[i:end]
        try:
            value = raw.decode("utf-8", "strict")
        except UnicodeDecodeError:
            continue
        if not value or not all(ch in "\n\t\r" or not unicodedata.category(ch).startswith("C") for ch in value):
            continue
        align_end = (end + 4) & ~3
        if any(data[end:align_end]):
            continue
        yield {"offset": i, "byte_len": len(raw), "source": value}


def classify(value: str) -> str:
    if VOICE_RE.fullmatch(value):
        return "voice"
    if (2 <= len(value) <= 12 and JP_RE.search(value)
            and not any(c in value for c in ("\n", "\r", "▼", "。", "！", "？", "、", "!", "?", ":"))
            and all(c.isalnum() or JP_RE.fullmatch(c) or c in "・　 " for c in value)):
        return "speaker_candidate"
    if JP_RE.search(value) or "▼" in value:
        return "text_candidate"
    return "other"


def extract(data: bytes, *, scope: str = "story") -> tuple[list[dict], dict]:
    boundary = find_story_start(data)
    if scope == "story" and boundary is None:
        raise ValueError("No ' START : SCN_' boundary found; inspect manually, or use --scope all")
    starts = boundary if scope == "story" else 0
    found = list(iter_strings(data, starts))
    by_kind = {"voice": 0, "speaker_candidate": 0, "text_candidate": 0, "other": 0}
    classified = [(entry, classify(entry["source"])) for entry in found]
    matching_quartets = sum(
        [classified[j + k][1] for k in range(4)]
        == ["voice", "speaker_candidate", "voice", "text_candidate"]
        and classified[j][0]["source"] == classified[j + 2][0]["source"]
        for j in range(max(0, len(classified) - 3))
    )
    records = []
    last_speaker = ""
    last_voice = ""
    for s, kind in classified:
        by_kind[kind] += 1
        if kind == "speaker_candidate":
            last_speaker = s["source"]
        elif kind == "voice":
            last_voice = s["source"]
        elif kind == "text_candidate":
            records.append({
                "id": f"ssb_{s['offset']:08x}",
                "offset_hex": f"0x{s['offset']:08X}",
                "original_bytes": s["byte_len"],
                "speaker_candidate": last_speaker,
                "voice_candidate": last_voice,
                "source_ja": s["source"],
                "translation_ru": "",
                "notes": "",
            })
    stats = {
        "format": "Sakurasou-RU SSB UTF-8 candidate extraction v1",
        "file_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "scope": scope,
        "story_boundary_hex": f"0x{boundary:X}" if boundary is not None else None,
        "aligned_utf8_strings_seen": len(found),
        "strings_by_heuristic_kind": by_kind,
        "exported_text_candidates": len(records),
        "complete_voice_speaker_voice_dialogue_quartets": matching_quartets,
        "note": "Metadata only. Text CSV stays in local work directory; script pointers are not decoded; DO NOT reinsert translations yet.",
    }
    return records, stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ssb", type=Path, help="A privately extracted SSB from your own Vita game")
    ap.add_argument("--scope", choices=("story", "all"), default="story")
    ap.add_argument("--csv", type=Path, default=Path("work/translations/ssb_candidates.csv"))
    ap.add_argument("--report", type=Path, default=Path("work/reports/ssb_extract.json"))
    args = ap.parse_args(argv)
    if not args.ssb.is_file() or args.ssb.suffix.lower() != ".ssb":
        ap.error("Provide an existing .ssb file")
    if args.csv.resolve() == args.ssb.resolve() or args.report.resolve() == args.ssb.resolve():
        ap.error("Output paths must not overwrite the input")
    if args.csv.resolve() == args.report.resolve():
        ap.error("CSV and report must have separate paths")
    try:
        rows, stats = extract(args.ssb.read_bytes(), scope=args.scope)
    except (OSError, ValueError) as exc:
        ap.error(str(exc))
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "offset_hex", "original_bytes", "speaker_candidate", "voice_candidate", "source_ja", "translation_ru", "notes"])
        writer.writeheader()
        writer.writerows(rows)
    args.report.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Found {stats['exported_text_candidates']} candidate Japanese strings")
    print(f"Local CSV (do not publish): {args.csv}")
    print(f"Shareable metadata: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
