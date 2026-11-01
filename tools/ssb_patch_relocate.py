#!/usr/bin/env python3
"""Experimental SSB UTF-8 relocation patcher for Sakurasou PS Vita (PCSG00129).

Proven on one real SSB: opcode 3 followed by a little-endian 32-bit
absolute FILE offset measured in 4-byte units points to a UTF-8 string.
Append translated strings to the file end and redirect only those pointers.

This preserves every old string and all original bytes except explicitly
verified pointer operands. It does NOT prove that the game runtime accepts
longer SSB files or draws the changed text correctly.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct


MARKERS = "▼▽"
DEFAULT_OUTPUT = Path("work/patches/SCN_CJIN_relocated.ssb")
DEFAULT_REPORT = Path("work/reports/ssb_relocate.json")
MAX_TRANSLATION_BYTES = 16384


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def references(data: bytes, offset: int, scan_end: int) -> list[int]:
    """Find aligned opcode-3 operands containing target offset/4."""
    if offset % 4:
        raise ValueError(f"Unaligned source offset: 0x{offset:X}")
    key = offset // 4
    return [
        pos
        for pos in range(4, scan_end - 3, 4)
        if struct.unpack_from("<I", data, pos - 4)[0] == 3
        and struct.unpack_from("<I", data, pos)[0] == key
    ]


def build(data: bytes, rows: list[dict], *, expected_sha: str | None = None,
          fonts: list[object] | None = None) -> tuple[bytes, dict]:
    if expected_sha and sha256(data).lower() != expected_sha.lower():
        raise ValueError("Original SSB SHA256 mismatch")
    if len(data) % 4:
        raise ValueError("Original SSB is not 4-byte aligned")
    if not rows:
        raise ValueError("CSV contains no source rows")
    boundary = data.find(b" START : SCN_")
    if boundary < 0:
        raise ValueError("No scene boundary; this SSB requires separate structural analysis")
    if boundary % 4:
        raise ValueError("Scene boundary is unaligned; unexpected SSB variant")
    edited = bytearray(data)
    visited = set()
    changed_operands = []
    changes = []
    for line, row in enumerate(rows, 2):
        try:
            offset = int(row["offset_hex"], 0)
            count = int(row["original_bytes"])
            japanese = row["source_ja"]
            russian = (row["translation_ru"] or "").strip()
        except (ValueError, KeyError, TypeError) as err:
            raise ValueError(f"CSV row {line}: invalid source columns") from err
        if offset in visited:
            raise ValueError(f"CSV row {line}: duplicate offset")
        visited.add(offset)
        if offset < 0 or offset % 4 or count < 1 or offset + count >= len(data):
            raise ValueError(f"CSV row {line}: invalid source bounds")
        old_raw = japanese.encode("utf-8")
        if len(old_raw) != count or data[offset:offset + count] != old_raw:
            raise ValueError(f"CSV row {line}: original data mismatch at 0x{offset:X}")
        if data[offset + count] != 0:
            raise ValueError(f"CSV row {line}: original text not terminated")
        if not russian:
            continue

        if "\x00" in russian or any(ord(c) < 32 and c != "\n" for c in russian):
            raise ValueError(f"CSV row {line}: invalid control character")
        for marker in MARKERS:
            if japanese.count(marker) != russian.count(marker):
                raise ValueError(f"CSV row {line}: scene marker {marker!r} must be preserved")
        if japanese.endswith("▼") and not russian.endswith("▼"):
            raise ValueError(f"CSV row {line}: must end with ▼")
        if russian.count("\n") > japanese.count("\n"):
            raise ValueError(f"CSV row {line}: additional line breaks not validated")
        replacement = russian.encode("utf-8")
        if len(replacement) > MAX_TRANSLATION_BYTES:
            raise ValueError(f"CSV row {line}: translation exceeds safe test size")
        if fonts:
            for font in fonts:
                missing = font.missing(russian)
                if missing:
                    codepoints = ", ".join(f"U+{ord(c):04X}" for c in missing)
                    raise ValueError(f"CSV row {line}: {font.path.name} lacks {codepoints}")

        locations = references(data, offset, boundary)
        if len(locations) != 1:
            raise ValueError(
                f"CSV row {line}: expected 1 verified opcode-3 reference "
                f"to 0x{offset:X}, got {len(locations)}; refusing relocation"
            )
        ptr = locations[0]
        if ptr in changed_operands:
            raise ValueError(f"CSV row {line}: duplicate pointer")

        new_offset = len(edited)
        if new_offset % 4:
            raise AssertionError("New UTF-8 string would be unaligned")
        new_index = new_offset // 4
        if new_index >= 2**32:
            raise ValueError("File address exceeds 32-bit word index")
        encoded_pointer = struct.pack("<I", new_index)
        edited[ptr:ptr + 4] = encoded_pointer
        edited.extend(replacement + b"\x00")
        edited.extend(bytes((-len(edited)) % 4))
        changed_operands.append(ptr)
        changes.append({
            "id": row.get("id", ""),
            "original_offset_hex": f"0x{offset:08X}",
            "pointer_operand_hex": f"0x{ptr:08X}",
            "old_word_index_hex": f"0x{offset // 4:08X}",
            "new_offset_hex": f"0x{new_offset:08X}",
            "new_word_index_hex": f"0x{new_index:08X}",
            "source_utf8_bytes": count,
            "translation_utf8_bytes": len(replacement),
        })
        if edited[new_offset:new_offset + len(replacement)] != replacement:
            raise AssertionError("Relocated string verification failed")
        if struct.unpack_from("<I", edited, ptr)[0] * 4 != new_offset:
            raise AssertionError("Pointer verification failed")

    # Reconstruct original from modified pointer operands; all remaining bytes
    # through the original EOF MUST match exactly.
    reverted = bytearray(edited[:len(data)])
    for record in changes:
        pos = int(record["pointer_operand_hex"], 16)
        idx = int(record["old_word_index_hex"], 16)
        struct.pack_into("<I", reverted, pos, idx)
    if reverted != data:
        raise AssertionError("Unexpected mutation outside pointer operands")

    report = {
        "format": "Sakurasou-RU SSB relocation experiment v1",
        "original_sha256": sha256(data),
        "patched_sha256": sha256(edited),
        "source_bytes": len(data),
        "patched_bytes": len(edited),
        "scene_boundary_hex": f"0x{boundary:X}",
        "modified_pointer_operands": len(changes),
        "appended_utf8_strings": len(changes),
        "old_bytes_preserved_except_pointer_operands": True,
        "new_pointers_validated": True,
        "changes": changes,
        "warning": "OFFLINE STRUCTURAL TEST ONLY: game-engine compatibility unverified.",
    }
    return bytes(edited), report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ssb", type=Path, required=True)
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--font", type=Path, action="append", default=[])
    ap.add_argument("--expected-sha", default=None)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    ap.add_argument("--apply", action="store_true", help="Write output; otherwise dry-run")
    args = ap.parse_args(argv)
    inputs = [args.ssb.resolve(), args.csv.resolve(), *[p.resolve() for p in args.font]]
    outputs = [args.out.resolve(), args.report.resolve()]
    if len(set(outputs)) != len(outputs) or any(path in inputs for path in outputs):
        ap.error("Output paths must be different from each other and all inputs")
    try:
        if args.ssb.suffix.lower() != ".ssb":
            raise ValueError("Input must be .ssb")
        with args.csv.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        if args.font:
            from fnt_inspect import FNTFont
            font_objects = [FNTFont(f) for f in args.font]
        else:
            font_objects = []
        new_data, report = build(
            args.ssb.read_bytes(), rows, expected_sha=args.expected_sha,
            fonts=font_objects,
        )
        if not args.apply:
            print(
                f"DRY RUN: {report['modified_pointer_operands']} pointer(s), "
                f"{report['source_bytes']} -> {report['patched_bytes']} bytes; no files written"
            )
            return 0
        if not report["modified_pointer_operands"]:
            print("No translated rows; no output written")
            return 0
        if args.out.exists() or args.report.exists():
            raise FileExistsError("Refusing to overwrite existing output/report")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(new_data)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    except (OSError, ValueError, AssertionError) as error:
        ap.error(str(error))
    print(f"EXPERIMENTAL SSB: {args.out}")
    print(f"Metadata-only report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
