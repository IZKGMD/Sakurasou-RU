#!/usr/bin/env python3
"""Safe-ish wrapper around the third-party CriPakTool: never alter the input archive.

CriPakTool itself is experimental. We run it in a separate empty folder, not
alongside your original game files. Examine its extraction code before use.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess


def extract(cpk: Path, executable: Path, destination: Path, *, list_only=False):
    cpk = cpk.resolve(strict=True)
    executable = executable.resolve(strict=True)
    destination = destination.resolve()
    if not cpk.is_file() or not executable.is_file():
        raise ValueError('Expected archive and executable files')
    with cpk.open('rb') as f:
        if f.read(4) != b'CPK ':
            raise ValueError('Not a standard CPK at byte 0. This file may be encrypted (PS Vita PFS) or use another format. Run tools/diagnose_cpk.py and recopy through VitaShell Open decrypted + FTP. Original not modified.')
    if destination == cpk.parent or cpk.is_relative_to(destination):
        raise ValueError('Output folder must be separate from archive folder')
    if not list_only:
        if destination.exists() and any(destination.iterdir()):
            raise FileExistsError(f'Extraction folder must be empty: {destination}')
        destination.mkdir(parents=True, exist_ok=True)
    elif not destination.exists():
        destination.mkdir(parents=True, exist_ok=True)
    args = [str(executable), str(cpk)] + ([] if list_only else ['ALL'])
    return subprocess.run(args, cwd=destination, check=True).returncode


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive', type=Path)
    ap.add_argument('--tool', type=Path, required=True, help='Your CriPakTool.exe path')
    ap.add_argument('--output', type=Path, default=Path('work/unpacked'))
    ap.add_argument('--list-only', action='store_true', help='List only; no game assets extracted')
    a = ap.parse_args(argv)
    try:
        return extract(a.archive, a.tool, a.output, list_only=a.list_only)
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        ap.exit(1, f'Extraction failed: {e}\n')


if __name__ == '__main__':
    raise SystemExit(main())
