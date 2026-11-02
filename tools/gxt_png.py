#!/usr/bin/env python3
"""Pixel-perfect PS Vita GXT / Sakurasou XTTL tiled-texture PNG bridge.

Only single-image Morton-swizzled BGRA8888 GXT format 0x0C001000, one mip,
no palette, and uniform XTTL grids of these tiles are supported. Fail closed
on every other format. Re-import always requires ORIGINAL binary: opaque
headers and padded XTTL tile pixels are preserved byte-for-byte.

Requires: py -3 -m pip install pillow
Examples:
  py -3 tools/gxt_png.py inspect work/all-assets-scan/title_start.gxt
  py -3 tools/gxt_png.py roundtrip work/all-assets-scan/title_start.gxt
  py -3 tools/gxt_png.py export work/all-assets-scan/title_start.gxt --out work/textures/title_start.png
  py -3 tools/gxt_png.py import work/all-assets-scan/title_start.gxt --png work/textures/title_start_ru.png --out work/patches/title_start.gxt
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import struct

FORMAT = 0x0C001000
MAX_PIXELS = 64_000_000


class UnsupportedTexture(ValueError):
    pass


@dataclass(frozen=True)
class GXT:
    width: int
    height: int
    data_offset: int
    data_size: int


@dataclass(frozen=True)
class XTTL:
    width: int
    height: int
    tile_w: int
    tile_h: int
    columns: int
    rows: int
    tiles_offset: int
    stride: int


def get_image():
    try:
        from PIL import Image
    except ImportError as e:
        raise RuntimeError("Requires Pillow: py -3 -m pip install pillow") from e
    return Image


def gxt_info(data: bytes) -> GXT:
    if len(data) < 64 or data[:4] != b"GXT\x00":
        raise UnsupportedTexture("Invalid GXT header")
    if struct.unpack_from("<I", data, 8)[0] != 1:
        raise UnsupportedTexture("GXT must contain one texture")
    base_offset, base_size = struct.unpack_from("<II", data, 12)
    offset, size = struct.unpack_from("<II", data, 32)
    palette = struct.unpack_from("<I", data, 40)[0]
    texture_type, texture_format = struct.unpack_from("<II", data, 48)
    w, h = struct.unpack_from("<HH", data, 56)
    mip = data[60]
    if (base_offset, base_size) != (offset, size):
        raise UnsupportedTexture("Unexpected data offsets")
    if texture_type != 0 or texture_format != FORMAT or mip != 1:
        raise UnsupportedTexture(
            f"Only Morton BGRA8888 supported; type={texture_type:#x}, "
            f"format={texture_format:#x}, mip={mip}"
        )
    if palette != 0xFFFFFFFF:
        raise UnsupportedTexture("Palette unsupported")
    if not (w and h and w * h <= MAX_PIXELS and
            (w & (w - 1)) == 0 and (h & (h - 1)) == 0):
        raise UnsupportedTexture(f"Unsafe/non-power-of-two texture: {w}x{h}")
    if offset < 64 or size != w*h*4 or offset+size > len(data):
        raise UnsupportedTexture("Invalid or truncated BGRA texture data")
    return GXT(w, h, offset, size)


def morton(x: int, y: int, w: int, h: int) -> int:
    bits = min(w, h).bit_length() - 1
    i = 0
    for b in range(bits):
        i |= ((x >> b) & 1) << (b * 2)
        i |= ((y >> b) & 1) << (b * 2 + 1)
    if w > h:
        i |= (x >> bits) << (bits * 2)
    elif h > w:
        i |= (y >> bits) << (bits * 2)
    return i


def decode_gxt(data: bytes):
    info = gxt_info(data)
    raw = memoryview(data)[info.data_offset:info.data_offset + info.data_size]
    result = bytearray(info.data_size)
    for y in range(info.height):
        for x in range(info.width):
            dest = 4 * (y * info.width + x)
            src = 4 * morton(x, y, info.width, info.height)
            result[dest:dest + 4] = raw[src:src + 4]
    return get_image().frombytes("RGBA", (info.width, info.height), bytes(result), "raw", "BGRA")


def encode_gxt(original: bytes, rgba) -> bytes:
    info = gxt_info(original)
    if rgba.mode != "RGBA" or rgba.size != (info.width, info.height):
        raise ValueError("PNG must be RGBA and exactly match GXT dimensions")
    raw = memoryview(rgba.tobytes("raw", "BGRA"))
    result = bytearray(original)
    for y in range(info.height):
        for x in range(info.width):
            src = 4 * (y * info.width + x)
            dest = info.data_offset + 4 * morton(x, y, info.width, info.height)
            result[dest:dest + 4] = raw[src:src + 4]
    return bytes(result)


def xttl_info(data: bytes) -> XTTL:
    if len(data) < 48 or data[:4] != b"XTTL":
        raise UnsupportedTexture("Invalid XTTL header")
    size, w, h, tw, th, cols, rows, off, stride = struct.unpack_from("<9I", data, 4)
    if size != len(data):
        raise UnsupportedTexture("XTTL total file size mismatch")
    if (min(w, h, tw, th, cols, rows) < 1 or w * h > MAX_PIXELS or
            tw * th > MAX_PIXELS or max(w, h) > 8192):
        raise UnsupportedTexture("Unsafe XTTL dimensions")
    if (tw & (tw-1) or th & (th-1) or
            cols*tw != w or not (rows-1)*th < h <= rows*th):
        raise UnsupportedTexture("Inconsistent XTTL tile grid")
    if off < 48 or stride < 64 or off + cols*rows*stride != len(data):
        raise UnsupportedTexture("Invalid XTTL tile offsets/stride")
    info = XTTL(w, h, tw, th, cols, rows, off, stride)
    for i in range(cols*rows):
        sub = gxt_info(data[off+i*stride:off+(i+1)*stride])
        if (sub.width, sub.height) != (tw, th):
            raise UnsupportedTexture(f"Wrong dimensions in tile {i}")
    return info


def decode_xttl(data: bytes):
    info = xttl_info(data)
    canvas = get_image().new("RGBA", (info.width, info.rows*info.tile_h))
    for i in range(info.columns*info.rows):
        at = info.tiles_offset+i*info.stride
        sub = decode_gxt(data[at:at+info.stride])
        canvas.paste(sub, ((i % info.columns)*info.tile_w, (i//info.columns)*info.tile_h))
    return canvas.crop((0, 0, info.width, info.height))


def encode_xttl(original: bytes, rgba) -> bytes:
    info = xttl_info(original)
    if rgba.mode != "RGBA" or rgba.size != (info.width, info.height):
        raise ValueError("PNG must be RGBA with original XTTL dimensions")
    result = bytearray(original)
    for i in range(info.columns*info.rows):
        at = info.tiles_offset+i*info.stride
        left = (i % info.columns)*info.tile_w
        top = (i//info.columns)*info.tile_h
        original_tile = original[at:at+info.stride]
        # Keep bottom padding of last row and all unknown binary metadata.
        tile = decode_gxt(original_tile)
        part = rgba.crop((left, top, min(left+info.tile_w, info.width),
                          min(top+info.tile_h, info.height)))
        tile.paste(part, (0, 0))
        result[at:at+info.stride] = encode_gxt(original_tile, tile)
    return bytes(result)


def decode(data: bytes):
    if data[:4] == b"GXT\x00":
        return decode_gxt(data)
    if data[:4] == b"XTTL":
        return decode_xttl(data)
    raise UnsupportedTexture("Only GXT/XTTL are supported")


def encode(original: bytes, rgba) -> bytes:
    if original[:4] == b"GXT\x00":
        return encode_gxt(original, rgba)
    if original[:4] == b"XTTL":
        return encode_xttl(original, rgba)
    raise UnsupportedTexture("Only GXT/XTTL are supported")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=("inspect", "export", "import", "roundtrip"))
    ap.add_argument("original", type=Path, help="Original user-extracted GXT/GXTTL")
    ap.add_argument("--png", type=Path, help="Edited RGBA PNG for import")
    ap.add_argument("--out", type=Path, help="Output path, cannot overwrite original")
    args = ap.parse_args(argv)
    try:
        source = args.original.read_bytes()
        info = gxt_info(source) if source[:4] == b"GXT\x00" else xttl_info(source)
        print(f"{args.original.name}: {info.width}x{info.height}, {len(source)} bytes")
        if args.mode == "inspect":
            return 0
        if args.mode == "roundtrip":
            if encode(source, decode(source)) != source:
                raise ValueError("Exact binary roundtrip FAILED")
            print("Exact binary roundtrip: PASS")
            return 0
        if not args.out:
            raise ValueError("--out is required for export/import")
        if args.out.resolve() == args.original.resolve() or args.out.exists():
            raise FileExistsError("Refusing overwrite of an existing file or original")
        if args.mode == "export":
            if args.out.suffix.lower() != ".png":
                raise ValueError("Export must create a PNG")
            picture = decode(source)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            picture.save(args.out)
            print("Exported:", args.out)
        elif args.mode == "import":
            if args.png is None or not args.png.is_file():
                raise ValueError("--png with an edited RGBA PNG is required")
            if args.out.suffix.lower() != args.original.suffix.lower():
                raise ValueError("Output extension must match original")
            with get_image().open(args.png) as picture:
                if picture.mode != "RGBA":
                    raise ValueError("Edited PNG must be RGBA (not indexed or RGB)")
                pixels = picture.tobytes()
                new = encode(source, picture)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(new)
            if decode(new).tobytes() != pixels:
                args.out.unlink(missing_ok=True)
                raise ValueError("Pixel verification after import FAILED")
            print("Imported + pixel-verified:", args.out)
    except (OSError, ValueError, RuntimeError, struct.error) as error:
        ap.exit(1, f"GXT/XTTL FAILED: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
