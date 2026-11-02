#!/usr/bin/env python3
"""Build a SMALL private visual review pack for Sakurasou PS Vita texture work.

Input: the user's local gxt_audit.csv, extracted DATA.CPK resources and decoded
PNG previews from gxt_batch.py --export. Output: a ZIP with visual contact
sheets + format samples and an inventory. The proprietary files are NEVER sent
to GitHub; user can choose whether to attach the local ZIP privately in chat.

Includes:
  - contact sheets of every supported GXT/GXTTL (with filename captions);
  - original examples for 3 unsupported GXT/GXTTL (under size ceiling);
  - representative CSU, CBG and LOC examples (if present);
  - JSON records of all sampled paths, byte lengths, SHA256 and header hex.
The tool NEVER changes originals and doesn't OCR Japanese text.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import zipfile

MAX_RAW_BYTES = 3 * 1024 * 1024
MAX_TOTAL_RAW_BYTES = 12 * 1024 * 1024
COLUMNS = 5
ROWS = 5
CELL_W = 232
CELL_H = 181
THUMB_W = 216
THUMB_H = 146

CATEGORIES = (".csu", ".cbg", ".loc")


def normalize_path(root: Path, name: str) -> Path:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or not path.parts or any(p in (".", "..") for p in path.parts):
        raise ValueError(f"Unsafe asset path: {name!r}")
    root = root.resolve(strict=True)
    resolved = (root / Path(*path.parts)).resolve(strict=True)
    if not resolved.is_file() or not resolved.is_relative_to(root):
        raise ValueError(f"Invalid or escaped asset file: {name!r}")
    return resolved


def selection(paths: list[Path], per_type: int) -> list[Path]:
    """Sample small, mid and largest manageable file of each container type."""
    candidates = sorted(
        (p for p in paths if p.is_file() and 128 <= p.stat().st_size <= MAX_RAW_BYTES),
        key=lambda p: (p.stat().st_size, p.as_posix())
    )
    if len(candidates) <= per_type:
        return candidates
    if per_type == 1:
        return [candidates[len(candidates)//2]]
    indices = [round(i*(len(candidates)-1)/(per_type-1)) for i in range(per_type)]
    return [candidates[i] for i in sorted(set(indices))]


def header_record(path: Path, root: Path, kind: str) -> dict:
    with path.open("rb") as fp:
        header = fp.read(64)
        h = hashlib.sha256()
        h.update(header)
        for piece in iter(lambda: fp.read(1024*1024), b""):
            h.update(piece)
    return {
        "kind": kind,
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": h.hexdigest(),
        "first64_hex": header.hex(" "),
    }


def image_module():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("Install Pillow: py -3 -m pip install pillow") from exc
    return Image, ImageDraw, ImageFont


def draw_contact_sheet(items: list[tuple[str, Path]]) -> bytes:
    Image, ImageDraw, ImageFont = image_module()
    sheet = Image.new("RGB", (COLUMNS*CELL_W, ROWS*CELL_H), (28, 33, 40))
    painter = ImageDraw.Draw(sheet)
    for n, (filename, path) in enumerate(items):
        x = (n % COLUMNS)*CELL_W
        y = (n // COLUMNS)*CELL_H
        # Light neutral checkerboard makes transparent sprites readable.
        checker = Image.new("RGBA", (THUMB_W, THUMB_H), (222, 222, 222, 255))
        checks = ImageDraw.Draw(checker)
        for cy in range(0, THUMB_H, 18):
            for cx in range(0, THUMB_W, 18):
                if (cx//18+cy//18) % 2:
                    checks.rectangle(
                        (cx, cy, min(THUMB_W-1, cx+17), min(THUMB_H-1, cy+17)),
                        fill=(185,185,185,255)
                    )
        try:
            with Image.open(path) as opened:
                opened.load()
                thumb = opened.convert("RGBA")
                thumb.thumbnail((THUMB_W, THUMB_H))
                start = ((THUMB_W-thumb.width)//2, (THUMB_H-thumb.height)//2)
                checker.alpha_composite(thumb, start)
            sheet.paste(checker.convert("RGB"), (x+8,y+7))
            label = filename
        except (OSError, ValueError) as exc:
            label = f"BROKEN PNG: {filename}"
        painter.text((x+8,y+156),label[:34], fill=(245,245,245),font=ImageFont.load_default())
    output = BytesIO()
    sheet.save(output,format="PNG",optimize=True)
    return output.getvalue()


def make_review_pack(assets: Path, pngs: Path, audit: Path, target: Path,
                     max_samples_per_type=3) -> dict:
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite {target}")
    assets = assets.resolve(strict=True)
    pngs = pngs.resolve(strict=True)
    with audit.open(encoding="utf-8-sig", newline="") as fp:
        all_rows = list(csv.DictReader(fp))
    if not all_rows or not {"path", "status", "extension"}.issubset(all_rows[0]):
        raise ValueError("Invalid GXT audit report")
    supported = []
    unsupported = []
    seen = set()
    for row in all_rows:
        filename = row["path"]
        if filename in seen:
            raise ValueError(f"Duplicate GXT record: {filename}")
        seen.add(filename)
        if row["status"] == "decoded_supported":
            source = normalize_path(assets,filename)
            png = pngs/Path(filename + ".png")
            if not png.is_file():
                raise FileNotFoundError(f"Missing PNG preview: {png}")
            supported.append((filename,png))
        elif row["status"] == "unsupported":
            unsupported.append(normalize_path(assets,filename))
        else:
            raise ValueError(f"Unrecognized scan status: {row['status']!r}")
    samples = []
    for path in unsupported:
        if path.stat().st_size <= MAX_RAW_BYTES:
            samples.append((path,"unsupported_gxt"))
    for ext in CATEGORIES:
        group = [p for p in assets.rglob("*")
                 if p.is_file() and p.suffix.lower() == ext]
        samples.extend((file,f"other_format{ext}") for file in selection(group,max_samples_per_type))
    # Limit raw bytes even if the user has very large textures.
    raw_size = 0
    chosen = []
    for item in samples:
        path, kind = item
        size = path.stat().st_size
        if size + raw_size <= MAX_TOTAL_RAW_BYTES:
            chosen.append(item)
            raw_size += size
    records = [header_record(path,assets,kind) for path,kind in chosen]
    result = {
        "format": "Sakurasou-RU-private-visual-and-format-review-v1",
        "gxt_gxttl_total": len(all_rows),
        "gxt_gxttl_supported": len(supported),
        "gxt_gxttl_unsupported": len(unsupported),
        "contact_sheet_pages": (len(supported)+COLUMNS*ROWS-1)//(COLUMNS*ROWS),
        "raw_sample_count": len(records),
        "raw_sample_bytes": raw_size,
        "sample_records": records,
        "unsupported_gxt_files": [p.relative_to(assets).as_posix() for p in unsupported],
        "notes": (
            "Contact sheets are to visually identify embedded Japanese. "
            "Samples are copies of user-owned game data: share privately, not on public GitHub. "
            "No content has been translated yet."
        ),
    }
    target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.writestr("review_manifest.json",json.dumps(result,indent=2,ensure_ascii=False))
        # Preserve order from gxt audit CSV: page and item indices are stable.
        for i in range(0,len(supported),COLUMNS*ROWS):
            page_num = i//(COLUMNS*ROWS)+1
            page_items = supported[i:i+COLUMNS*ROWS]
            z.writestr(f"contact_sheets/sheet_{page_num:02d}.png",draw_contact_sheet(page_items))
            z.writestr(f"contact_sheets/sheet_{page_num:02d}.txt",
                       "\n".join(f"{j+1:02d} {item[0]}" for j,item in enumerate(page_items))+"\n")
        for path,kind in chosen:
            filename = path.relative_to(assets).as_posix()
            z.write(path,f"format_samples/{kind}/{filename}")
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets",type=Path,default=Path("work/all-assets-scan"))
    parser.add_argument("--pngs",type=Path,default=Path("work/texture-pngs"))
    parser.add_argument("--audit",type=Path,default=Path("work/reports/gxt_audit.csv"))
    parser.add_argument("--out",type=Path,default=Path("work/reports/Sakurasou_Graphics_Review.zip"))
    parser.add_argument("--samples-per-type",type=int,default=3,choices=(1,2,3))
    args=parser.parse_args(argv)
    try:
        result=make_review_pack(args.assets,args.pngs,args.audit,args.out,args.samples_per_type)
    except (OSError,ValueError,RuntimeError,zipfile.BadZipFile) as exc:
        parser.exit(1,f"Texture review pack FAILED: {exc}\n")
    print(f"Reviewed GXT/GXTTL: {result['gxt_gxttl_total']} "
          f"({result['gxt_gxttl_supported']} supported, {result['gxt_gxttl_unsupported']} unsupported)")
    print(f"Visual sheets: {result['contact_sheet_pages']}, format samples: {result['raw_sample_count']}")
    print("Review ZIP:",args.out)
    print("ZIP bytes:",args.out.stat().st_size)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
