#!/usr/bin/env python3
"""Read only the first 4096 bytes of a CPK candidate and explain the result.

The tool NEVER decrypts or alters the source. The report contains only a tiny
hex prefix, a file size and the position of the CPK signature if detected.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

MAGIC = b"CPK "
SCAN_BYTES = 4096
PREVIEW_BYTES = 32


def inspect_header(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("rb") as handle:
        head = handle.read(SCAN_BYTES)
    offset = head.find(MAGIC)
    status = (
        "standard_cpk" if offset == 0
        else "cpk_signature_at_nonzero_offset" if offset >= 0
        else "unknown_header_possibly_encrypted"
    )
    return {
        "format": "Sakurasou-RU CPK header diagnostic v1",
        "file_name": path.name,
        "size_bytes": path.stat().st_size,
        "first_32_bytes_hex": head[:PREVIEW_BYTES].hex(" "),
        "cpk_signature_offset_first_4096": offset if offset >= 0 else None,
        "status": status,
        "note": (
            "This only recognises a header signature, not whether the archive is extractable. "
            "A missing signature may indicate PFS encryption, another format, or an "
            "unusual wrapper; confirm how the game file was copied."
        ),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive", type=Path)
    ap.add_argument("--report", type=Path, default=Path("work/reports/header.json"))
    args = ap.parse_args(argv)
    try:
        result = inspect_header(args.archive)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        ap.error(str(exc))
    print("File:", result["file_name"])
    print("Size:", result["size_bytes"], "bytes")
    print("First 32 bytes:", result["first_32_bytes_hex"] or "(empty)")
    print("Status:", result["status"])
    print("Report:", args.report)
    if result["status"] != "standard_cpk":
        print("\nThe archive is not a standard CPK at offset 0.")
        print("On PS Vita, copy the game files via VitaShell 'Open decrypted' while")
        print("the decrypted view is active, preferably over VitaShell FTP.")
        print("Do NOT rename, hex-edit, or overwrite the original archive.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
