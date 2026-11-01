#!/usr/bin/env python3
"""Build and VERIFY an isolated test CPK using the third-party CriPakTools.

CriPakTools' REPLACE operation is only safe when provided with an OUT_FILE.
This wrapper stages a copy of the decrypted CPK and checks extraction from the
rebuilt archive before publishing it under work/. Original files are read-only.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ENTRY_NAME = "SCN_CJIN_1Y_1112x_010.ssb"
DEFAULT_OUTPUT = Path("work/patches/DATA_test.CPK")
FILE_LINE = re.compile(r"^[^:\r\n]+\.[A-Za-z0-9]{1,12}$")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run(tool: Path, *arguments: str, cwd: Path) -> str:
    completed = subprocess.run(
        [str(tool), *map(str, arguments)],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        timeout=1800,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"CriPakTools returned code {completed.returncode}:\n"
            + completed.stdout[-2200:]
        )
    return completed.stdout


def inventory(tool: Path, archive: Path, cwd: Path) -> Counter:
    stdout = run(tool, str(archive), cwd=cwd)
    # The tool emits a banner before its entry listing; filter to plausible paths.
    lines = [
        line.strip().replace("\\", "/")
        for line in stdout.splitlines()
        if FILE_LINE.fullmatch(line.strip())
    ]
    if not lines:
        raise ValueError("CriPakTools did not produce a recognizable file listing")
    return Counter(lines)


def _entry_matches(items: Counter, basename: str) -> list[str]:
    return [name for name in items if name.rsplit("/", 1)[-1] == basename]


def extract_one(tool: Path, archive: Path, basename: str, cwd: Path) -> Path:
    # CriPakTools writes to its current working directory.
    cwd.mkdir(parents=True, exist_ok=False)
    output = run(tool, str(archive), basename, cwd=cwd)
    extracted = cwd / basename
    if not extracted.is_file():
        raise ValueError(
            f"CriPakTools failed to extract {basename}:\n" + output[-1000:]
        )
    return extracted


def build(
    archive: Path,
    patched_ssb: Path,
    tool: Path,
    out: Path,
    *,
    entry: str = ENTRY_NAME,
    expected_ssb_sha: str | None = None,
    control_reference: Path | None = None,
) -> dict:
    archive = archive.resolve(strict=True)
    patched_ssb = patched_ssb.resolve(strict=True)
    tool = tool.resolve(strict=True)
    out = out.resolve()

    if not re.fullmatch(r"[A-Za-z0-9_-]+\.ssb", entry):
        raise ValueError("Entry must be one exact SSB basename from the archive")
    if any(not p.is_file() for p in (archive, patched_ssb, tool)):
        raise ValueError("Input paths must be regular files")
    if archive == out or patched_ssb == out or tool == out:
        raise ValueError("Output cannot overwrite any input")
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {out}")
    if out.parent.resolve() == archive.parent:
        raise ValueError("Choose an output folder separate from the decrypted game")
    if archive.read_bytes()[:4] != b"CPK ":
        raise ValueError("Not a decrypted CPK archive (missing CPK magic)")
    if not patched_ssb.stat().st_size or patched_ssb.suffix.lower() != ".ssb":
        raise ValueError("Patched input must be a nonempty SSB file")
    if expected_ssb_sha and digest(patched_ssb).lower() != expected_ssb_sha.lower():
        raise ValueError("Patched SSB SHA256 differs from user's report")
    if control_reference is not None:
        control_reference = control_reference.resolve(strict=True)
        if not control_reference.is_file():
            raise ValueError("Control reference is not a regular file")

    out.parent.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(out.parent).free
    needed = archive.stat().st_size * 2 + 128 * 1024 * 1024
    if free < needed:
        raise OSError(
            f"Not enough free space: need at least {needed:,} bytes "
            f"(staged original and rebuilt CPK), free {free:,}"
        )
    original_sha = digest(archive)
    modified_ssb_sha = digest(patched_ssb)

    with tempfile.TemporaryDirectory(prefix="sakurasou-cpk-", dir=out.parent) as td:
        tmp = Path(td)
        staged_original = tmp / "ORIGINAL.CPK"
        rebuilt = tmp / "REBUILT.CPK"
        shutil.copyfile(archive, staged_original)

        original_list = inventory(tool, staged_original, tmp)
        matched = _entry_matches(original_list, entry)
        if len(matched) != 1 or original_list[matched[0]] != 1:
            raise ValueError(f"Entry must occur exactly once; found: {matched}")
        if control_reference is not None:
            controls = _entry_matches(original_list, control_reference.name)
            if len(controls) != 1:
                raise ValueError(f"Control file missing/ambiguous: {control_reference.name}")

        # Important: CriPakTools appends OUT_FILE to the source CPK directory.
        # Supply a *basename* only. Without OUT_FILE it overwrites source.
        run(tool, str(staged_original), entry, str(patched_ssb), rebuilt.name, cwd=tmp)
        if not rebuilt.is_file():
            raise RuntimeError("Rebuilt CPK not created")
        with rebuilt.open("rb") as fp:
            if fp.read(4) != b"CPK ":
                raise ValueError("Rebuilt archive has no CPK signature")

        new_list = inventory(tool, rebuilt, tmp)
        if new_list != original_list:
            removed = list((original_list - new_list).elements())[:10]
            added = list((new_list - original_list).elements())[:10]
            raise ValueError(f"Archive inventory mismatch; lost={removed} extra={added}")
        extracted = extract_one(tool, rebuilt, entry, tmp / "verify_changed")
        if digest(extracted) != modified_ssb_sha:
            raise ValueError("Extracted SSB differs from source patched SSB")

        control_sha = None
        if control_reference is not None:
            unchanged = extract_one(
                tool, rebuilt, control_reference.name, tmp / "verify_control"
            )
            control_sha = digest(unchanged)
            if control_sha != digest(control_reference):
                raise ValueError("Unchanged control SSB differs from original")

        if digest(archive) != original_sha:
            raise RuntimeError("Original CPK changed unexpectedly")

        report = {
            "format": "Sakurasou-RU verified local CPK test build v1",
            "title_id": "PCSG00129",
            "original_cpk_sha256": original_sha,
            "modified_cpk_sha256": digest(rebuilt),
            "modified_ssb_sha256": modified_ssb_sha,
            "entry": entry,
            "file_count": sum(original_list.values()),
            "original_bytes": archive.stat().st_size,
            "modified_bytes": rebuilt.stat().st_size,
            "patched_ssb_roundtrip_verified": True,
            "all_archive_entry_names_preserved": True,
            "control_ssb_sha256": control_sha,
            "warning": "This validates archive extraction, NOT engine loading or Cyrillic rendering.",
        }
        report_path = out.with_name(out.stem + ".report.json")
        if report_path.exists():
            raise FileExistsError(f"Report already exists: {report_path}")
        staged_report = tmp / "report.json"
        staged_report.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        # Publish only after all checks pass; stage and output share a drive.
        os.replace(rebuilt, out)
        os.replace(staged_report, report_path)

    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cpk", type=Path, required=True)
    p.add_argument("--ssb", type=Path, required=True, help="Locally patched SSB")
    p.add_argument("--tool", type=Path, default=Path("tools/bin/CriPakTools.exe"))
    p.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--entry", default=ENTRY_NAME)
    p.add_argument("--expected-ssb-sha", default=None)
    p.add_argument("--control-ssb", type=Path, help="Optional unchanged original SSB for verification")
    p.add_argument("--build", action="store_true", help="Explicitly create test CPK; otherwise show plan")
    args = p.parse_args(argv)
    if not args.build:
        print(f"DRY RUN: would stage a COPY of {args.cpk}")
        print(f"Replace entry: {args.entry} from {args.ssb}")
        print(f"Produce: {args.out}")
        print("Pass --build to run CriPakTools and verify the new CPK.")
        return 0
    try:
        report = build(
            args.cpk, args.ssb, args.tool, args.out,
            entry=args.entry,
            expected_ssb_sha=args.expected_ssb_sha,
            control_reference=args.control_ssb,
        )
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as e:
        p.exit(1, f"CPK test build FAILED (original left untouched): {e}\n")
    print(f"Verified test CPK: {args.out}")
    print(f"Entries: {report['file_count']}; roundtrip SSB: OK")
    print(f"Report: {args.out.with_name(args.out.stem + '.report.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
