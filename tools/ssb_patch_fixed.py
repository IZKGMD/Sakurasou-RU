#!/usr/bin/env python3
"""Experimental fixed-slot UTF-8 patcher for Sakurasou Vita SSB scripts.

Only replaces existing UTF-8 text bytes with no offset/size changes. Requires
an extraction CSV from ssb_extract.py. Does not modify the source file, and
cannot guarantee the PS Vita engine can render Cyrillic glyphs.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path

KNOWN_MARKERS = '▼▽'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def patched_bytes(original: bytes, rows: list[dict], expected_sha: str | None = None) -> tuple[bytes, list[dict]]:
    if expected_sha and sha256(original).lower() != expected_sha.lower():
        raise ValueError('SSB SHA256 differs from expected baseline; refusing to patch')
    result = bytearray(original)
    patches = []
    used_offsets = set()
    if not rows:
        raise ValueError('CSV has no rows')
    for n, row in enumerate(rows, 2):
        try:
            offset = int(row['offset_hex'], 0)
            old_length = int(row['original_bytes'])
            source = row['source_ja']
            translation = row['translation_ru'] or ''
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f'CSV row {n}: missing or invalid columns') from exc
        if offset in used_offsets:
            raise ValueError(f'Duplicate offset 0x{offset:X}')
        used_offsets.add(offset)
        if offset < 0 or old_length < 1 or offset + old_length >= len(original) or offset % 4:
            raise ValueError(f'Row {n}: invalid SSB bounds/alignment')
        original_utf8 = source.encode('utf-8')
        if len(original_utf8) != old_length or original[offset:offset + old_length] != original_utf8:
            raise ValueError(f'Row {n}: source UTF-8 does not match original at 0x{offset:X}')
        if original[offset + old_length] != 0:
            raise ValueError(f'Row {n}: source not NUL-terminated')
        if not translation:
            continue
        if '\x00' in translation or any(ord(ch) < 32 and ch != '\n' for ch in translation):
            raise ValueError(f'Row {n}: invalid control character in translation')
        for marker in KNOWN_MARKERS:
            if translation.count(marker) != source.count(marker):
                raise ValueError(f'Row {n}: missing or extra game marker {marker!r}')
        if source.endswith('▼') and not translation.endswith('▼'):
            raise ValueError(f'Row {n}: translation must end with ▼')
        if translation.count('\n') > source.count('\n'):
            raise ValueError(f'Row {n}: added line breaks are untested')
        encoded = translation.encode('utf-8')
        if len(encoded) > old_length:
            raise ValueError(
                f'Row {n} at 0x{offset:X}: Russian text needs {len(encoded)} bytes, '
                f'only {old_length} available (longer text requires relocation)'
            )
        result[offset:offset+old_length] = encoded + bytes(old_length-len(encoded))
        patches.append({'id': row.get('id',''), 'offset_hex': f'0x{offset:08X}',
                        'original_bytes':old_length,'new_utf8_bytes':len(encoded)})
    if len(result) != len(original):
        raise AssertionError('Patch changed file length')
    return bytes(result), patches


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--ssb', type=Path, required=True)
    ap.add_argument('--csv', type=Path, required=True)
    ap.add_argument('--out', type=Path, default=Path('work/patches/SCN_CJIN_test.ssb'))
    ap.add_argument('--report', type=Path, default=Path('work/reports/ssb_patch.json'))
    ap.add_argument('--expected-sha', default=None, help='Optional SHA256 of original SSB')
    ap.add_argument('--apply', action='store_true', help='Write experimental patched SSB; default is dry-run')
    args = ap.parse_args(argv)
    if not args.ssb.is_file() or args.ssb.suffix.lower() != '.ssb':
        ap.error('Input must be an existing .ssb')
    if not args.csv.is_file():
        ap.error('CSV does not exist')
    if args.out.resolve() in (args.ssb.resolve(), args.csv.resolve()) or args.report.resolve() in (args.ssb.resolve(), args.csv.resolve(), args.out.resolve()):
        ap.error('Inputs and output paths must be distinct')
    try:
        with args.csv.open('r', encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        original = args.ssb.read_bytes()
        candidate, changes = patched_bytes(original, rows, args.expected_sha)
        if not args.apply:
            print(f'DRY RUN: validated {len(rows)} CSV rows, {len(changes)} replacement(s). No output written.')
            return 0
        if not changes:
            print('No translations in translation_ru. No output written.')
            return 0
        args.out.parent.mkdir(parents=True, exist_ok=True)
        if args.out.exists():
            raise ValueError(f'Output already exists: {args.out}; choose another path')
        args.out.write_bytes(candidate)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        report = {
            'format':'Sakurasou-RU fixed-slot patch report v1',
            'source_sha256':sha256(original),
            'patched_sha256':sha256(candidate),
            'original_size':len(original),
            'patched_size':len(candidate),
            'replacements':changes,
            'warning':'Experimental: pointer logic/font coverage not verified in game.'
        }
        args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'Wrote {args.out} ({len(candidate)} bytes, {len(changes)} strings changed)')
        print(f'Report: {args.report}')
    except (OSError, ValueError, UnicodeError) as exc:
        ap.error(str(exc))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
