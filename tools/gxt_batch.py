#!/usr/bin/env python3
"""Inventory and optionally export ALL local Sakurasou PS Vita GXT/GXTTL images.

Read-only: preserves originals, refuses overwrites, produces an exact listing of
supported/unsupported formats. For full localization also audit .csu/.cbg/.loc,
which are NOT standard GXT and are deliberately not processed by this script.

Requires Pillow only when --export is selected.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from gxt_png import gxt_info, xttl_info, decode


COLUMNS = ("path", "extension", "bytes", "width", "height", "status", "reason", "png")


def inspect(root: Path, *, export: Path | None = None) -> list[dict]:
    if not root.is_dir():
        raise FileNotFoundError(f"Game resource directory missing: {root}")
    rows = []
    candidates = sorted(x for x in root.rglob("*")
                        if x.is_file() and x.suffix.lower() in (".gxt", ".gxttl"))
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
                    xttl_info(data) if data[:4] == b"XTTL" else None)
            if spec is None:
                raise ValueError("Not a supported GXT/XTTL header")
            item["width"], item["height"] = spec.width, spec.height
            item["status"] = "decoded_supported"
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
    args = p.parse_args(argv)
    try:
        if args.out.exists() or args.summary.exists():
            raise FileExistsError("Do not overwrite a previous inventory. Choose fresh output paths.")
        result = inspect(args.assets, export=args.export)
        summary = {
            "format": "Sakurasou-RU GXT/XTTL batch audit v1",
            "images_seen": len(result),
            "supported": sum(r["status"] == "decoded_supported" for r in result),
            "unsupported": sum(r["status"] == "unsupported" for r in result),
            "jpeg_or_png_patching": False,
            "note": (
                "Only compatible swizzled BGRA8888 GXT/XTTL files. "
                "A readable texture may not contain Japanese. "
                "All .csu, .cbg and .loc resources need separate format research. "
                "PNG export does not translate text."
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
    print(f"GXT/GXTTL: {summary['images_seen']} seen, "
          f"{summary['supported']} compatible, {summary['unsupported']} unsupported")
    print("Inventory:", args.out)
    print("Summary:", args.summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
