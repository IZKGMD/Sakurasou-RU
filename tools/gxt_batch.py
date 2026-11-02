#!/usr/bin/env python3
"""Inventory and optionally export Sakurasou Vita graphics, including wrapped images.

The default preserves legacy GXT/GXTTL-only scanning. Add --all-graphics to
inspect GXT/GXTTL, LOC-wrapped GXT, CSU sprite atlases, and CBG backgrounds.
Read-only: preserves originals, refuses overwrite, and reports unsupported formats.

Requires Pillow only when --export is selected.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from gxt_png import gxt_info, xttl_info, wrapped_xttl_info, decode, encode


COLUMNS = ("path", "extension", "bytes", "width", "height", "status", "reason", "png")


def inspect(root: Path, *, export: Path | None = None,
            all_graphics: bool = False, verify_roundtrip: bool = False) -> list[dict]:
    if not root.is_dir():
        raise FileNotFoundError(f"Game resource directory missing: {root}")
    rows = []
    extensions = (".gxt", ".gxttl", ".loc", ".csu", ".cbg") if all_graphics else (".gxt", ".gxttl")
    candidates = sorted(x for x in root.rglob("*")
                        if x.is_file() and x.suffix.lower() in extensions)
    for index, file in enumerate(candidates, 1):
        rel = file.relative_to(root)
        item = {
            "path": rel.as_posix(), "extension": file.suffix.lower(),
            "bytes": file.stat().st_size, "width": "", "height": "",
            "status": "unsupported", "reason": "", "png": "",
        }
        try:
            data = file.read_bytes()
            spec = (gxt_info(data) if data[:4] == b"GXT\x00" else
                    xttl_info(data) if data[:4] == b"XTTL" else
                    wrapped_xttl_info(data)[2] if data[:4] in (b"CSU\x00", b"CBG\x00") else None)
            if spec is None:
                raise ValueError("Not a supported GXT/XTTL/CSU/CBG header")
            item["width"], item["height"] = spec.width, spec.height
            item["status"] = "decoded_supported"
            if verify_roundtrip and encode(data, decode(data)) != data:
                raise ValueError("Decoded/encoded file differs from original bytes")
            if export is not None:
                target = export / rel.with_suffix(rel.suffix + ".png")
                if target.exists():
                    raise FileExistsError(f"Refuse to overwrite previously exported PNG: {target}")
                target.parent.mkdir(parents=True, exist_ok=True)
                decode(data).save(target)
                item["png"] = target.as_posix()
        except (ValueError, OSError) as e:
            if isinstance(e, FileExistsError):
                raise
            item["reason"] = str(e)[:220]
            item["status"] = "unsupported"
        rows.append(item)
        if index % 25 == 0:
            print(f"Scanned {index}/{len(candidates)} textures", flush=True)
    return rows


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--assets", type=Path, default=Path("work/all-assets-scan"))
    p.add_argument("--out", type=Path, default=Path("work/reports/gxt_audit.csv"))
    p.add_argument("--summary", type=Path, default=Path("work/reports/gxt_audit.json"))
    p.add_argument("--export", type=Path, default=None,
                   help="Optional private folder containing decoded RGBA PNGs")
    p.add_argument("--all-graphics", action="store_true",
                   help="Include CSU/CBG sprite and background containers and LOC textures")
    p.add_argument("--verify-roundtrip", action="store_true",
                   help="Slower: verify every supported file is byte-identical after decode and encode")
    args = p.parse_args(argv)
    try:
        if args.out.exists() or args.summary.exists():
            raise FileExistsError("Do not overwrite a previous inventory. Choose fresh output paths.")
        result = inspect(args.assets, export=args.export,
                         all_graphics=args.all_graphics, verify_roundtrip=args.verify_roundtrip)
        summary = {
            "format": "Sakurasou-RU graphics batch audit v2",
            "images_seen": len(result),
            "supported": sum(r["status"] == "decoded_supported" for r in result),
            "unsupported": sum(r["status"] == "unsupported" for r in result),
            "extensions_scanned": ([".gxt", ".gxttl", ".loc", ".csu", ".cbg"]
                                    if args.all_graphics else [".gxt", ".gxttl"]),
            "byte_exact_roundtrip_checked": args.verify_roundtrip,
            "note": (
                "Supported formats: swizzled BGRA8888/P8 GXT, padded XTTL, "
                "CSU/CBG containers with embedded XTTL, LOC files containing GXT. "
                "Unsupported file variants must be investigated separately. "
                "PNG export does not translate any Japanese lettering."
            ),
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(result)
        args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, ValueError, RuntimeError) as err:
        p.exit(1, f"GXT audit FAILED: {err}\n")
    print(f"Graphics: {summary['images_seen']} seen, "
          f"{summary['supported']} compatible, {summary['unsupported']} unsupported")
    print("Inventory:", args.out)
    print("Summary:", args.summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
