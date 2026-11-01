#!/usr/bin/env python3
"""Read-only metadata inspection of extracted Sakurasou resources.

This is NOT an .ssb decoder: structure is unknown until real Vita samples are studied.
No dialogue, textures, or full resource files are exported into the report.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

TEXT_EXTENSIONS = {'.ssb', '.fnt', '.cmed', '.tipd', '.tmd', '.tskd', '.slpd', '.tskt'}
RESOURCE_EXTENSIONS = TEXT_EXTENSIONS | {'.txg', '.txgtl', '.cbg', '.csu', '.loc'}
MAX_HEADER = 32


def fingerprint(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        header = stream.read(MAX_HEADER)
        digest.update(header)
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'bytes': path.stat().st_size, 'sha256': digest.hexdigest(), 'header_hex': header.hex(' ')}


def inspect_directory(source: Path) -> dict:
    if not source.is_dir():
        raise NotADirectoryError(source)
    paths = sorted(x for x in source.rglob('*') if x.is_file())
    counts = Counter(x.suffix.lower() or '(none)' for x in paths)
    candidates = []
    for path in paths:
        ext = path.suffix.lower()
        if ext in RESOURCE_EXTENSIONS:
            candidates.append({'relative_path': path.relative_to(source).as_posix(), 'extension': ext,
                               'possibly_contains_text': ext in TEXT_EXTENSIONS, **fingerprint(path)})
    return {'format': 'Sakurasou-RU metadata report v1',
            'platform': 'PS Vita PCSG00129 (unverified archive contents)',
            'total_files': len(paths), 'extension_counts': dict(sorted(counts.items())),
            'script_candidates': sum(p['extension'] == '.ssb' for p in candidates),
            'candidate_files': candidates,
            'notice': 'No game dialogue or copyrighted asset data is included (32-byte hex headers only).'}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('directory', type=Path, help='Locally extracted folder (not the CPK itself)')
    ap.add_argument('--report', type=Path, default=Path('work/reports/triage.json'))
    args = ap.parse_args(argv)
    try:
        report = inspect_directory(args.directory)
    except OSError as e:
        ap.error(str(e))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Files: {report['total_files']}; .ssb candidates: {report['script_candidates']}")
    for ext, count in report['extension_counts'].items():
        print(f'  {ext:8} {count}')
    print(f"Report: {args.report}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
