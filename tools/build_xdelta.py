#!/usr/bin/env python3
"""Build a version-locked xdelta patch from local original/modified CPKs."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            sha.update(block)
    return sha.hexdigest()

def main(argv=None):
    ap = argparse.ArgumentParser(description='Create a local delta, never distribute a full modified game archive.')
    ap.add_argument('--original', type=Path, required=True)
    ap.add_argument('--modified', type=Path, required=True)
    ap.add_argument('--patch', type=Path, required=True)
    ap.add_argument('--xdelta', default='xdelta3')
    args = ap.parse_args(argv)
    for candidate in (args.original, args.modified):
        if not candidate.is_file():
            ap.error(f'File not found: {candidate}')
        with candidate.open('rb') as fp:
            if fp.read(4) != b'CPK ':
                ap.error(f'Not a recognised CPK header: {candidate}')
    if args.original.resolve() == args.modified.resolve():
        ap.error('Original and modified paths must be different')
    if digest(args.original) == digest(args.modified):
        ap.error('No modifications detected')
    if not shutil.which(args.xdelta):
        ap.error('xdelta3 missing; install it and add it to PATH')
    args.patch.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([args.xdelta, '-e', '-f', '-s', str(args.original), str(args.modified), str(args.patch)], check=True)
    manifest = {
        'format': 'Sakurasou-RU patch manifest v1',
        'title_id': 'PCSG00129',
        'original_sha256': digest(args.original),
        'modified_sha256': digest(args.modified),
        'patch_sha256': digest(args.patch),
        'patch_file': args.patch.name,
        'warning': 'Requires legitimately acquired original; never distribute full modified CPK.',
    }
    manifest_path = args.patch.with_suffix('.manifest.json')
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    print('Patch:', args.patch)
    print('Manifest:', manifest_path)
    return 0

if __name__ == '__main__':
    sys.exit(main())
