#!/usr/bin/env python3
"""Read-only, non-textual probes for Sakurasou Vita SSB/FNT/CMED files.

This does not decode or export game dialogue. All Japanese encoding candidates
are heuristic; only a file-specific parser can identify command boundaries.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]{3,}")
LIMIT = 25_000_000


def _jp_candidates(data: bytes, encoding: str) -> dict:
    # The 'ignore' mode intentionally explores possibilities; it is not
    # a reliable proof of a file's original encoding.
    decoded = data.decode(encoding, errors="ignore")
    lengths = [len(m.group()) for m in JAPANESE.finditer(decoded)]
    return {
        "run_count": len(lengths),
        "max_run_chars": max(lengths, default=0),
        "total_run_chars": sum(lengths),
    }


def inspect(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size > LIMIT:
        raise ValueError(f"{path.name}: sample exceeds {LIMIT:,} byte probe limit")
    data = path.read_bytes()
    freq = Counter(data)
    total = len(data)
    entropy = (
        -sum((n / total) * math.log2(n / total) for n in freq.values())
        if total else 0.0
    )
    dwords = [
        int.from_bytes(data[i:i+4], "little")
        for i in range(0, min(len(data), 64) - 3, 4)
    ]
    result = {
        "filename": path.name,
        "size_bytes": total,
        "sha256": hashlib.sha256(data).hexdigest(),
        "header_hex": data[:32].hex(" "),
        "possible_signature": (
            "CMED" if data.startswith(b"CMED")
            else "FNT" if data.startswith(b"FNT\\x00")
            else "unknown"
        ),
        "zero_byte_percent": round(freq[0] * 100 / total, 2) if total else 0.0,
        "shannon_entropy_bits_per_byte": round(entropy, 4),
        "first_16_dwords_le": dwords,
        "first_32_bytes_repeated_eightbyte_block": (
            len(data) >= 32 and data[:8] * 4 == data[:32]
        ),
        "japanese_text_heuristics": {
            enc: _jp_candidates(data, enc)
            for enc in ("utf-8", "cp932", "utf-16-le")
        },
    }
    # Text content never enters the JSON result.
    return result


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("inputs", nargs="+", type=Path)
    p.add_argument("--report", type=Path, default=Path("work/reports/format_probe.json"))
    args = p.parse_args(argv)
    try:
        report = {
            "format": "Sakurasou-RU format probe v1",
            "note": "Encoding scores are guesses, not evidence of a decoded script.",
            "files": [inspect(path) for path in args.inputs],
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except (OSError, ValueError) as error:
        p.error(str(error))
    for item in report["files"]:
        print(
            f"{item['filename']}: {item['size_bytes']:,} bytes; "
            f"signature={item['possible_signature']}"
        )
    print(f"Saved metadata-only report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
