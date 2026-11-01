#!/usr/bin/env python3
"""Read-only FNT Unicode and 4bpp bitmap font inspector (Sakurasou Vita).

Probed with font_s.fnt and font_m.fnt, but no game assets are included.
All images and metadata are generated locally.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import struct
import zlib
from pathlib import Path

MAP_OFFSET = 0x10
BITMAP_OFFSET = 0x20010
RUSSIAN = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя"


class FNTFont:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        if len(self.data) < BITMAP_OFFSET or self.data[:4] != b"FNT\x00":
            raise ValueError(f"{path}: unsupported FNT layout")
        version, side, bits = struct.unpack_from("<III", self.data, 4)
        if (version, bits) != (1, 4) or not 2 <= side <= 256 or side % 2:
            raise ValueError(f"{path}: unsupported version/dimensions/depth")
        self.side, self.bits = side, bits
        self.table = struct.unpack_from("<65536H", self.data, MAP_OFFSET)
        self.record_bytes = side * side // 2
        self.glyph_count = max(self.table) + 1
        if BITMAP_OFFSET + self.glyph_count * self.record_bytes != len(self.data):
            raise ValueError(f"{path}: inconsistent glyph table and file size")

    def glyph_id(self, ch: str) -> int:
        cp = ord(ch)
        return self.table[cp] if cp < 65536 else 0

    def glyph_pixels(self, ch: str) -> bytes | None:
        glyph = self.glyph_id(ch)
        if not glyph:
            return None
        begin = BITMAP_OFFSET + glyph * self.record_bytes
        raw = self.data[begin:begin + self.record_bytes]
        pixels = bytearray(self.side * self.side)
        for i, byte in enumerate(raw):
            pixels[2 * i] = (byte >> 4) * 17
            pixels[2 * i + 1] = (byte & 15) * 17
        return bytes(pixels)

    def missing(self, value: str) -> list[str]:
        return sorted({ch for ch in value if ch not in "\r\n\t" and not self.glyph_id(ch)}, key=ord)

    def report(self, checked_text: str) -> dict:
        return {
            "name": self.path.name,
            "sha256": hashlib.sha256(self.data).hexdigest(),
            "bytes": len(self.data),
            "version": 1,
            "glyph_dimensions": [self.side, self.side],
            "bits_per_pixel": 4,
            "unicode_lookup_offset": "0x10",
            "bitmap_offset": "0x20010",
            "max_glyph_id": self.glyph_count - 1,
            "mapped_codepoints": sum(bool(i) for i in self.table),
            "russian_letters_mapped": sum(bool(self.glyph_id(ch)) for ch in RUSSIAN),
            "russian_letters_with_pixels": sum(bool(self.glyph_pixels(ch) and any(self.glyph_pixels(ch))) for ch in RUSSIAN),
            "missing_in_checked_text": [f"U+{ord(ch):04X} {ch}" for ch in self.missing(checked_text)],
        }


def _pngchunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)


def save_preview(font: FNTFont, out: Path, chars: str = RUSSIAN, columns: int = 11) -> None:
    # Pure-stdlib PNG. Cyrillic glyphs appear in RUSSIAN string order, no labels.
    scale = 2
    cell = font.side * scale + 6
    width = columns * cell
    height = ((len(chars) + columns - 1) // columns) * cell
    image = bytearray([45]) * (width * height)
    for n, char in enumerate(chars):
        glyph = font.glyph_pixels(char)
        if glyph is None:
            continue
        left, top = (n % columns) * cell + 3, (n // columns) * cell + 3
        for y in range(font.side):
            for x in range(font.side):
                intensity = glyph[y * font.side + x]
                for dy in range(scale):
                    start = (top + y * scale + dy) * width + left + x * scale
                    image[start:start + scale] = bytes((intensity,)) * scale
    scanlines = bytearray()
    for y in range(height):
        scanlines.extend(b"\x00" + image[y * width:(y + 1) * width])
    png = (b"\x89PNG\r\n\x1a\n" +
           _pngchunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)) +
           _pngchunk(b"IDAT", zlib.compress(scanlines)) +
           _pngchunk(b"IEND", b""))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(png)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fonts", nargs="+", type=Path)
    ap.add_argument("--text", default="Привет, мир! Ёжик.▼")
    ap.add_argument("--csv", type=Path, help="Optional local CSV with translation_ru column")
    ap.add_argument("--report", type=Path, default=Path("work/reports/font_coverage.json"))
    ap.add_argument("--preview-dir", type=Path, help="Optional local PNG previews")
    args = ap.parse_args(argv)
    try:
        text = args.text
        if args.csv:
            with args.csv.open(encoding="utf-8-sig", newline="") as fp:
                rows = list(csv.DictReader(fp))
                if rows and "translation_ru" not in rows[0]:
                    raise ValueError("CSV lacks translation_ru column")
                text += "\n" + "\n".join(row["translation_ru"] or "" for row in rows)
        fonts = [FNTFont(p) for p in args.fonts]
        report = {
            "format": "Sakurasou-RU FNT coverage v1",
            "preview_glyph_order": RUSSIAN,
            "fonts": [font.report(text) for font in fonts],
            "warning": "Glyph coverage alone does not prove the game renderer works with Cyrillic.",
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Technical report:", args.report)
        for f, r in zip(fonts, report["fonts"]):
            print(f"{f.path.name}: {f.side}x{f.side} 4bpp; Russian {r['russian_letters_mapped']}/66; unsupported: {r['missing_in_checked_text']}")
            if args.preview_dir:
                output = args.preview_dir / (f.path.stem + "_ru.png")
                save_preview(f, output)
                print("Preview:", output)
    except (OSError, ValueError) as error:
        ap.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
