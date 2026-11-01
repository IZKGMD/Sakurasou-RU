#!/usr/bin/env python3
"""Apply a hash-checked patch locally to an owned original CPK."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from build_xdelta import digest

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--original', required=True, type=Path)
    ap.add_argument('--patch', required=True, type=Path)
    ap.add_argument('--manifest', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--xdelta', default='xdelta3')
    args = ap.parse_args(argv)
    for f in (args.original, args.patch, args.manifest):
        if not f.is_file():
            ap.error(f'File not found: {f}')
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    if manifest.get('title_id') != 'PCSG00129':
        ap.error('Unexpected title ID')
    if digest(args.original) != manifest['original_sha256']:
        ap.error('Original CPK does not match patch version (SHA-256 mismatch)')
    if digest(args.patch) != manifest['patch_sha256']:
        ap.error('Patch file changed or corrupted (SHA-256 mismatch)')
    if args.output.resolve() == args.original.resolve():
        ap.error('Output must not overwrite the original')
    if not shutil.which(args.xdelta):
        ap.error('xdelta3 missing; install it before applying')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([args.xdelta, '-d', '-f', '-s', str(args.original), str(args.patch), str(args.output)], check=True)
    if digest(args.output) != manifest['modified_sha256']:
        args.output.unlink(missing_ok=True)
        ap.error('Patched file failed SHA-256 verification')
    with args.output.open('rb') as f:
        if f.read(4) != b'CPK ':
            args.output.unlink(missing_ok=True)
            ap.error('Patched file is not a CPK')
    print('Verified modified archive:', args.output)
    return 0

if __name__ == '__main__':
    sys.exit(main())
