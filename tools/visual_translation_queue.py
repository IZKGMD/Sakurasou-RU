#!/usr/bin/env python3
"""Sakurasou-RU: review actual Japanese lettering in ALL supported game graphics.

Read the existing graphics audit (1210/1210 format-compatible), prioritize
menus/UI, build compact contact sheets plus selected full-size PNGs. Each
batch includes a complete, stable index. Re-run with --batch 2/3/... so no
asset is silently skipped. This is a VISUAL triage tool; it does not detect
Japanese with OCR or claim any graphics are already translated.

No original GXT/CSU/CBG/LOC binaries leave the user's disk.
Requires Pillow installed (py -3 -m pip install pillow).
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from io import BytesIO, StringIO
import json
from pathlib import Path
import re
import zipfile

from gxt_png import decode
from texture_review_pack import normalize_path, image_module

SHEET_COLUMNS = 4
SHEET_ROWS = 5
ITEMS_PER_SHEET = SHEET_COLUMNS * SHEET_ROWS
CELL_W, CELL_H = 278, 209
PREVIEW_W, PREVIEW_H = 254, 171

UI_WORDS = (
    "title", "menu", "option", "config", "help", "button", "common",
    "system", "guide", "dialog", "conversation", "caption", "text",
    "message", "save", "load", "name", "select", "choice", "logo",
    "task", "tips", "team", "notice", "warning", "tutorial", "result",
    "progress", "start", "staff", "credit", "scene", "map", "status"
)
ALLOWED_EXT = {".gxt", ".gxttl", ".loc", ".cbg", ".csu"}
COLUMNS = (
    "review_id", "file", "extension", "priority", "width", "height",
    "has_japanese", "action", "translation_ru", "notes"
)


def priority(path: str) -> tuple[int, int, str]:
    """Sort important on-screen UI ahead of character sprites, without exclusion."""
    p = Path(path)
    name = p.stem.lower()
    hits = sum(bool(re.search(r"(^|[_\W])"+re.escape(word), name))
               for word in UI_WORDS)
    # Favor likely text-rich UI; still include EVERY asset in the order.
    extension_weight = {
        ".gxt": 0, ".gxttl": 1, ".loc": 2, ".cbg": 3, ".csu": 4
    }.get(p.suffix.lower(), 5)
    return (-hits, extension_weight, path.casefold())


def load_queue(csv_path: Path) -> list[dict]:
    with csv_path.open(encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        if not {"path", "status", "extension", "width", "height"}.issubset(reader.fieldnames or ()):
            raise ValueError("Not a gxt_batch --all-graphics CSV")
        rows = list(reader)
    if not rows:
        raise ValueError("Empty graphics audit")
    seen = set()
    for r in rows:
        filename = r["path"].replace("\\", "/")
        ext = Path(filename).suffix.lower()
        if not filename or filename in seen or ext not in ALLOWED_EXT:
            raise ValueError(f"Duplicate or invalid graphics item: {filename!r}")
        if r["status"] != "decoded_supported":
            raise ValueError(f"Unresolved asset: {filename} ({r['status']}); fix decoder first")
        if not (r["width"].isdigit() and r["height"].isdigit()):
            raise ValueError(f"Missing image dimensions: {filename}")
        seen.add(filename)
        r["path"] = filename
    return sorted(rows, key=lambda r: priority(r["path"]))


def buffer_png(img) -> bytes:
    dst = BytesIO()
    img.save(dst, format="PNG", optimize=True)
    return dst.getvalue()


def make_sheet(thumbnails: list[tuple[int, str, object]]) -> bytes:
    Image, ImageDraw, ImageFont = image_module()
    # Thumbnails are RGBA PIL Image instances.
    canvas = Image.new("RGB", (CELL_W*SHEET_COLUMNS, CELL_H*SHEET_ROWS), (26, 32, 40))
    paint = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for n, (rank, name, thumb) in enumerate(thumbnails):
        x = (n % SHEET_COLUMNS)*CELL_W
        y = (n // SHEET_COLUMNS)*CELL_H
        bg = Image.new("RGBA", (PREVIEW_W, PREVIEW_H), (232, 232, 232, 255))
        checker = ImageDraw.Draw(bg)
        for yy in range(0,PREVIEW_H,16):
            for xx in range(0,PREVIEW_W,16):
                if (xx//16 + yy//16) % 2:
                    checker.rectangle((xx, yy, xx+15, yy+15), fill=(190,190,190,255))
        thumb.thumbnail((PREVIEW_W, PREVIEW_H))
        bg.alpha_composite(thumb, ((PREVIEW_W-thumb.width)//2,
                                   (PREVIEW_H-thumb.height)//2))
        canvas.paste(bg.convert("RGB"), (x+12,y+6))
        paint.text((x+12,y+181),f"{rank:04d} {name[:36]}",fill=(255,255,255),font=font)
    return buffer_png(canvas)


def produce(root: Path, audit: Path, out: Path, *,
            batch: int = 1, batch_size: int = 80, full_size: int = 8) -> dict:
    if batch < 1 or not (1 <= batch_size <= 150) or not (0 <= full_size <= 20):
        raise ValueError("Invalid batch/count. Batch >= 1, count 1..150, full-size 0..20")
    if out.exists():
        raise FileExistsError(f"Refusing overwrite of existing ZIP: {out}")
    queue = load_queue(audit)
    start = (batch-1)*batch_size
    selected = queue[start:start+batch_size]
    if not selected:
        raise ValueError(f"Batch {batch} outside total of {len(queue)} assets")
    end = start+len(selected)
    Image, _, _ = image_module()
    review = []
    failed = []
    by_extension = Counter()
    sheets = []
    sheet_items = []
    original_path = str(root.resolve())
    out.parent.mkdir(parents=True, exist_ok=True)
    # Never include original proprietary binaries; only reduced PNGs and
    # opt-in limited full-res PNGs needed for accurate text translation.
    with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for idx, r in enumerate(selected, start=start+1):
            filename = r["path"]
            source = normalize_path(root,filename)
            by_extension[r["extension"]] += 1
            local = {
                "review_id": f"{idx:04d}",
                "file": filename,
                "extension":r["extension"],
                "priority": "UI" if priority(filename)[0] < 0 else "general",
                "width":r["width"],"height":r["height"],
                "has_japanese": "", "action": "inspect",
                "translation_ru": "", "notes": ""
            }
            review.append(local)
            try:
                picture = decode(source.read_bytes())
                if picture.size != (int(r["width"]),int(r["height"])):
                    raise ValueError("Decoded size differs from audit")
                if idx-start <= full_size:
                    z.writestr(f"full_png/{idx:04d}_{Path(filename).name}.png",
                               buffer_png(picture))
                sheet_items.append((idx,filename,picture.copy()))
            except (OSError,ValueError,RuntimeError,MemoryError) as exc:
                failed.append({"review_id":idx,"file":filename,"error":str(exc)})
                sheet_items.append((idx,filename+" [ERROR]",Image.new("RGBA",(64,64),(200,20,20,255))))
            if len(sheet_items) == ITEMS_PER_SHEET or idx == end:
                number = len(sheets)+1
                sheet_name = f"sheets/part_{batch:02d}_sheet_{number:02d}.png"
                z.writestr(sheet_name, make_sheet(sheet_items))
                sheets.append(sheet_name)
                sheet_items.clear()
        output=StringIO()
        writer=csv.DictWriter(output,fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(review)
        z.writestr("review.csv",output.getvalue().encode("utf-8-sig"))
        manifest={
            "format":"sakurasou-graphics-Japanese-review-batch-v1",
            "archive_source":"DATA.CPK extracted locally",
            "audit_source":audit.name,
            "total_graphics":len(queue),
            "batch":batch,"batch_size":batch_size,
            "range_inclusive":[start+1,end],
            "sheets":sheets,
            "full_png_count":min(full_size,len(selected)),
            "by_extension":dict(sorted(by_extension.items())),
            "decode_failures":failed,
            "coverage_note":"Only format-compatible assets. No OCR or visual translation conclusions are automated.",
            "next_batch": batch+1 if end<len(queue) else None
        }
        z.writestr("index.json",json.dumps(manifest,ensure_ascii=False,indent=2))
    return manifest


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--assets",type=Path,default=Path("work/all-assets-scan"))
    p.add_argument("--audit",type=Path,default=Path("work/reports/all_graphics_v2.csv"))
    p.add_argument("--batch",type=int,default=1)
    p.add_argument("--batch-size",type=int,default=80)
    p.add_argument("--full-size",type=int,default=8)
    p.add_argument("--out",type=Path)
    args=p.parse_args(argv)
    result_path=args.out or Path(f"work/reports/Sakurasou_Textures_Review_{args.batch:02d}.zip")
    try:
        result=produce(args.assets,args.audit,result_path,
                       batch=args.batch,batch_size=args.batch_size,full_size=args.full_size)
    except (OSError,ValueError,RuntimeError,zipfile.BadZipFile) as err:
        p.exit(1,f"Visual queue FAILED: {err}\n")
    print("Graphic resources:",result["total_graphics"])
    print("Batch:",result["batch"],"range:",result["range_inclusive"])
    print("Contact sheets:",len(result["sheets"]),"errors:",len(result["decode_failures"]))
    print("Archive:",result_path)
    print("Archive bytes:",result_path.stat().st_size)
    if result["next_batch"]:
        print("Continue with --batch",result["next_batch"])
    return 0


if __name__=="__main__":
    raise SystemExit(main())
