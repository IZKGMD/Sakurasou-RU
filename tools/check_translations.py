#!/usr/bin/env python3
"""Validate locally authored translations without shipping game dialogue."""
from __future__ import annotations
import argparse
import csv
import sys
from pathlib import Path

def validate(path: Path):
    errors = []
    count = 0
    seen = set()
    with path.open('r', encoding='utf-8-sig', newline='') as fp:
        reader = csv.DictReader(fp)
        required = {'id', 'ru'}
        if not required.issubset(reader.fieldnames or []):
            return 0, [f'Expected CSV columns: {sorted(required)}']
        for number, row in enumerate(reader, start=2):
            key = (row.get('id') or '').strip()
            ru = (row.get('ru') or '').strip()
            if not key:
                errors.append(f'Line {number}: empty id')
            if key in seen:
                errors.append(f'Line {number}: duplicate id {key!r}')
            seen.add(key)
            if not ru:
                errors.append(f'Line {number}: empty Russian translation')
            if '\x00' in ru:
                errors.append(f'Line {number}: NUL in text')
            count += 1
    return count, errors

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('csv_path', type=Path)
    args = ap.parse_args(argv)
    try:
        count, errors = validate(args.csv_path)
    except OSError as ex:
        ap.error(str(ex))
    for err in errors:
        print('ERROR:', err, file=sys.stderr)
    if errors:
        return 1
    print(f'OK: {count} translation rows; source text and game files not required')
    return 0

if __name__ == '__main__':
    sys.exit(main())
