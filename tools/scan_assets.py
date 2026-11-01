#!/usr/bin/env python3
"""Inventory locally owned game resources without copying asset content."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

LIKELY_TEXT = {'.txt', '.csv', '.xml', '.json', '.yaml', '.yml', '.lua', '.srt', '.scn', '.scr', '.mes', '.msg', '.dat', '.bin'}
MAX_PREVIEW = 32

def inspect_file(path: Path, base: Path) -> dict:
    sha = hashlib.sha256()
    with path.open('rb') as fp:
        signature = fp.read(MAX_PREVIEW)
        sha.update(signature)
        for block in iter(lambda: fp.read(1024 * 1024), b''):
            sha.update(block)
    suffix = path.suffix.lower()
    return {
        'path': path.relative_to(base).as_posix() if base != path else path.name,
        'size_bytes': path.stat().st_size,
        'sha256': sha.hexdigest(),
        'cpk_magic': signature.startswith(b'CPK '),
        'possible_text_asset': suffix in LIKELY_TEXT,
        'extension': suffix,
    }

def make_report(path: Path) -> dict:
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    files = sorted(p for p in path.rglob('*') if p.is_file()) if path.is_dir() else [path]
    data = [inspect_file(p, path) for p in files]
    return {
        'format': 'Sakurasou-RU asset inventory v1',
        'source_type': 'directory' if path.is_dir() else 'file',
        'file_count': len(data),
        'total_bytes': sum(row['size_bytes'] for row in data),
        'likely_text_files': sum(1 for row in data if row['possible_text_asset']),
        'files': data,
    }

def main(argv=None):
    parser = argparse.ArgumentParser(description='Analyse local CPK or extracted directory without copying game contents.')
    parser.add_argument('path', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args(argv)
    try:
        report = make_report(args.path)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Scanned {report['file_count']} files; total {report['total_bytes']:,} bytes")
    print(f"Potential text containers: {report['likely_text_files']}")
    for f in report['files'][:30]:
        mark = ' [CRI CPK]' if f['cpk_magic'] else ''
        print(f"  {f['path']}  ({f['size_bytes']:,} bytes){mark}")
    if len(report['files']) > 30:
        print(f"  ... and {len(report['files']) - 30} more")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"Report saved: {args.report}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
