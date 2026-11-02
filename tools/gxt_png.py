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
P8_FORMAT = 0x95001000
MAX_PIXELS = 64_000_000


class UnsupportedTexture(ValueError):
    pass


@dataclass(frozen=True)
class GXT:
    width: int
    height: int
    data_offset: int
    data_size: int
    texture_format: int = FORMAT
    palette_offset: int | None = None


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
    if texture_type != 0 or texture_format not in (FORMAT, P8_FORMAT) or mip != 1:
        raise UnsupportedTexture(
            f"Only Morton BGRA8888 and P8 supported; type={texture_type:#x}, "
            f"format={texture_format:#x}, mip={mip}"
        )
    if not (w and h and w * h <= MAX_PIXELS and
            (w & (w - 1)) == 0 and (h & (h - 1)) == 0):
        raise UnsupportedTexture(f"Unsafe/non-power-of-two texture: {w}x{h}")
    is_p8 = texture_format == P8_FORMAT
    pal_bytes = 1024 if is_p8 else 0
    if palette != (0 if is_p8 else 0xFFFFFFFF):
        raise UnsupportedTexture("Unsupported palette index")
    if (base_offset != offset or base_size != size + pal_bytes or
            offset < 64 or size != w*h*(1 if is_p8 else 4) or
            offset + size + pal_bytes > len(data)):
        raise UnsupportedTexture("Invalid or truncated GXT texture/palette data")
    return GXT(w, h, offset, size, texture_format,
               offset+size if is_p8 else None)


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
    result = bytearray(info.width * info.height * 4)
    if info.texture_format == FORMAT:
        for y in range(info.height):
            for x in range(info.width):
                dest = 4 * (y * info.width + x)
                src = 4 * morton(x, y, info.width, info.height)
                result[dest:dest + 4] = raw[src:src + 4]
        return get_image().frombytes("RGBA", (info.width, info.height), bytes(result), "raw", "BGRA")
    # Vita P8 palette: 256 BGRA8888 colors, indices in Morton order.
    pal = memoryview(data)[info.palette_offset:info.palette_offset+1024]
    for y in range(info.height):
        for x in range(info.width):
            index = raw[morton(x, y, info.width, info.height)]
            b, g, r, a = pal[index*4:index*4+4]
            dest = 4*(y*info.width+x)
            result[dest:dest+4] = bytes((r,g,b,a))
    return get_image().frombytes("RGBA", (info.width, info.height), bytes(result))


def encode_gxt(original: bytes, rgba) -> bytes:
    info = gxt_info(original)
    if rgba.mode != "RGBA" or rgba.size != (info.width, info.height):
        raise ValueError("PNG must be RGBA and exactly match GXT dimensions")
    result = bytearray(original)
    if info.texture_format == FORMAT:
        raw = memoryview(rgba.tobytes("raw", "BGRA"))
        for y in range(info.height):
            for x in range(info.width):
                src = 4 * (y * info.width + x)
                dest = info.data_offset + 4 * morton(x, y, info.width, info.height)
                result[dest:dest + 4] = raw[src:src + 4]
        return bytes(result)
    # Exact P8 re-import: keep the ORIGINAL pixel index for unchanged colors
    # (important when multiple palette indices have identical RGBA values).
    # New colors use only UNUSED palette slots; never recolor active entries.
    palette = []
    for i in range(256):
        at = info.palette_offset + i*4
        b, g, r, a = original[at:at+4]
        palette.append((r,g,b,a))
    old_indices = original[info.data_offset:info.data_offset+info.data_size]
    used = set(old_indices)
    free = iter(i for i in range(256) if i not in used)
    by_color = {}
    for i in list(used) + [i for i in range(256) if i not in used]:
        by_color.setdefault(palette[i], i)
    wanted = memoryview(rgba.tobytes())
    for y in range(info.height):
        for x in range(info.width):
            m = morton(x, y, info.width, info.height)
            offset = info.data_offset + m
            old_index = original[offset]
            pos = 4 * (y*info.width + x)
            color = tuple(wanted[pos:pos+4])
            if color == palette[old_index]:
                continue
            match = by_color.get(color)
            if match is None:
                try:
                    match = next(free)
                except StopIteration:
                    raise UnsupportedTexture("P8 texture has no free palette slots for this edited color")
                # Updating a formerly unused palette entry is lossless for
                # all unchanged visible pixels; header/other entries stay.
                r, g, b, a = color
                result[info.palette_offset+match*4:info.palette_offset+match*4+4] = bytes((b,g,r,a))
                by_color[color] = match
                palette[match] = color
            result[offset] = match
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
            not (cols-1)*tw < w <= cols*tw or
            not (rows-1)*th < h <= rows*th):
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


def wrapped_xttl_info(data: bytes):
    """Locate the embedded XTTL without changing any CSU/CBG metadata.

    CBG: 0x20-byte header followed by a single XTTL.
    CSU: 0x30-byte header, embedded XTTL then animation/sprite metadata.
    """
    magic = data[:4]
    if magic not in (b"CSU\x00", b"CBG\x00"):
        raise UnsupportedTexture("Not a Sakurasou CSU/CBG wrapper")
    required = 0x30 if magic == b"CSU\x00" else 0x20
    version = 0x20 if magic == b"CSU\x00" else 0x10
    if len(data) < required+48 or struct.unpack_from("<I",data,4)[0] != version:
        raise UnsupportedTexture("Unrecognized CSU/CBG version or truncated wrapper")
    offset = struct.unpack_from("<I",data,8)[0]
    if offset != required or data[offset:offset+4] != b"XTTL":
        raise UnsupportedTexture("Unknown CSU/CBG embedded XTTL location")
    n = struct.unpack_from("<I",data,offset+4)[0]
    if n < 48 or offset+n > len(data):
        raise UnsupportedTexture("Truncated embedded XTTL")
    if magic == b"CBG\x00" and offset+n != len(data):
        raise UnsupportedTexture("CBG has unexpected trailing data")
    info = xttl_info(data[offset:offset+n])
    return offset, n, info


def decode(data: bytes):
    if data[:4] == b"GXT\x00":
        return decode_gxt(data)
    if data[:4] == b"XTTL":
        return decode_xttl(data)
    if data[:4] in (b"CSU\x00",b"CBG\x00"):
        off, n, _ = wrapped_xttl_info(data)
        return decode_xttl(data[off:off+n])
    raise UnsupportedTexture("Only GXT/XTTL/CSU/CBG are supported")


def encode(original: bytes, rgba) -> bytes:
    if original[:4] == b"GXT\x00":
        return encode_gxt(original, rgba)
    if original[:4] == b"XTTL":
        return encode_xttl(original, rgba)
    if original[:4] in (b"CSU\x00",b"CBG\x00"):
        off, n, _ = wrapped_xttl_info(original)
        sub = encode_xttl(original[off:off+n], rgba)
        if len(sub) != n:
            raise AssertionError("Embedded XTTL size changed")
        return original[:off] + sub + original[off+n:]
    raise UnsupportedTexture("Only GXT/XTTL/CSU/CBG are supported")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=("inspect", "export", "import", "roundtrip"))
    ap.add_argument("original", type=Path, help="Original user-extracted GXT/GXTTL")
    ap.add_argument("--png", type=Path, help="Edited RGBA PNG for import")
    ap.add_argument("--out", type=Path, help="Output path, cannot overwrite original")
    args = ap.parse_args(argv)
    try:
        source = args.original.read_bytes()
        info = (gxt_info(source) if source[:4] == b"GXT\x00"
                else xttl_info(source) if source[:4] == b"XTTL"
                else wrapped_xttl_info(source)[2])
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
