#!/usr/bin/env python3
# DEPRECATED: confirmed wrong title asset by Vita3K screenshots (2026-11-03).
# title_start.gxt is an INTRO/splash asset, not the five main-menu buttons.
# Generating this experimental "НАЧАТЬ" image produces broken spaced text.
# Use restore_original_title.py instead and inspect title_parts.gxt/title_obj.gxttl.
"""Generate the FIRST EXPERIMENTAL Russian title-start texture locally.

This file contains no commercial game assets or fonts.
Reads user's own original title_start.gxt, draws vertical Russian 'НАЧАТЬ'
with a small outline/shadow resembling the original UI, creates PNG, then
re-encodes the Vita GXT. Assumes the texture is displayed as a rotated label:
gameplay UV/layout remains UNVERIFIED. Always backup current CPK and check in
Vita3K. Does not automatically install or modify the game or original asset.

Requires Pillow and tools/gxt_png.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from gxt_png import decode, encode, gxt_info, FORMAT

EXPECTED_SHA256 = "1e8d4644bb9b7f2f92cb9a9c4538a92b65e5d6e0b2cb627e2ab365da64dbf382"


def get_font():
    from PIL import ImageFont
    choices = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("C:/Windows/Fonts/seguisb.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansDisplay-Black.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    ]
    for file in choices:
        if file.is_file():
            return ImageFont.truetype(str(file), 38)
    raise FileNotFoundError(
        "No Cyrillic-capable font found. This script does not ship font files."
    )


def make_label(source: bytes, font=None):
    from PIL import Image, ImageDraw

    if hashlib.sha256(source).hexdigest() != EXPECTED_SHA256:
        raise ValueError(
            "Unknown original title_start.gxt SHA256. "
            "Do not generate a test from the wrong game version."
        )
    g = gxt_info(source)
    if (g.width, g.height, g.texture_format) != (512,64,FORMAT):
        raise ValueError("Expected original single-image 512x64 BGRA GXT")
    # This atlas stores a vertical Japanese label as 90-degree rotated glyphs.
    # Keep pixel positions within the original 512x64 image.
    font = font or get_font()
    sheet = Image.new("RGBA", (64,512), (255,255,255,0))
    draw = ImageDraw.Draw(sheet)
    for index, character in enumerate("НАЧАТЬ"):
        x, y = 29, 30 + 59*index
        draw.text((x+4,y+5), character, font=font,
                  fill=(78,84,95,140), stroke_width=5,
                  stroke_fill=(40,45,57,90), anchor="mm")
        draw.text((x,y), character, font=font,
                  fill=(12,63,126,255), stroke_width=4,
                  stroke_fill=(255,255,255,255), anchor="mm")
    image = sheet.rotate(90,expand=True)
    new_data = encode(source,image)
    if len(new_data) != len(source) or new_data[:64] != source[:64]:
        raise AssertionError("Header/file size changed")
    if decode(new_data).tobytes() != image.tobytes():
        raise AssertionError("Pixels mismatch after encoding")
    if encode(source,decode(source)) != source:
        raise AssertionError("Original GXT does not exactly roundtrip")
    return image, new_data


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,default=Path("work/all-assets-scan/title_start.gxt"))
    p.add_argument("--out",type=Path,default=Path("work/patches/title_start_RU_TEST.gxt"))
    p.add_argument("--png",type=Path,default=Path("work/patches/title_start_RU_TEST.png"))
    p.add_argument("--report",type=Path,default=Path("work/reports/title_start_RU_TEST.json"))
    args=p.parse_args(argv)
    try:
        paths=[args.source.resolve(),args.out.resolve(),args.png.resolve(),args.report.resolve()]
        if len(set(paths))!=4 or any(p.exists() for p in (args.out,args.png,args.report)):
            raise ValueError("Output path conflicts or already exists; preserve original!")
        original=args.source.read_bytes()
        image,data=make_label(original)
        for dest in (args.out,args.png,args.report):
            dest.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_bytes(data)
        image.save(args.png)
        args.report.write_text(json.dumps({
            "format":"Sakurasou-RU experimental title button v1",
            "source":"title_start.gxt","russian_label":"НАЧАТЬ",
            "original_sha256":hashlib.sha256(original).hexdigest(),
            "patched_sha256":hashlib.sha256(data).hexdigest(),
            "source_bytes":len(original),"patched_bytes":len(data),
            "exact_pixels_verified":True,
            "runtime_verified":False,
            "caution":"Sprite atlas layout and visual fit must be tested in Vita3K."
        },indent=2,ensure_ascii=False),encoding="utf-8")
    except (OSError,ValueError,RuntimeError,AssertionError) as exc:
        p.exit(1,f"Title graphics test FAILED: {exc}\n")
    print("Experimental Russian texture:",args.out)
    print("Preview:",args.png)
    print("Offline pixels: PASS; gameplay rendering: NOT TESTED")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
