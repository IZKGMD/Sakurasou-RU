#!/usr/bin/env python3
"""Selectively extract sample game assets to an isolated local directory.

Uses an external CriPakTools.exe, never modifies the source CPK, and writes only
file metadata into a report. Extracted proprietary samples stay under work/.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Iterable
from triage_scripts import fingerprint

DEFAULT_SAMPLES = (
    "SCN_CJIN_1Y_1112x_010.ssb",
    "SCN_CMSK_1Y_1112x_010.ssb",
    "font_m.fnt",
    "font_s.fnt",
    "comment_list.cmed",
)


def validate_name(name: str) -> str:
    """Reject path escape and unintended mass extraction."""
    name = name.replace("\\", "/").strip()
    segments = PurePosixPath(name).parts
    if not name or name.upper() == "ALL" or not segments:
        raise ValueError("Invalid sample name")
    if name.startswith("/") or any(x in (".", "..") for x in segments) or ":" in name:
        raise ValueError("Unsafe relative filename")
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", name):
        raise ValueError("Unsupported filename characters")
    return name


def extract_samples(cpk: Path, tool: Path, output: Path, names: Iterable[str]) -> dict:
    cpk = cpk.resolve(strict=True)
    tool = tool.resolve(strict=True)
    output = output.resolve()
    if not cpk.is_file() or not tool.is_file():
        raise ValueError("Expected regular files")
    with cpk.open("rb") as handle:
        if handle.read(4) != b"CPK ":
            raise ValueError("Source is not a standard CRI CPK")
    if output == cpk.parent or cpk.is_relative_to(output) or output.is_relative_to(cpk.parent):
        raise ValueError("Output must be separated from the original archive directory")
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Output must be empty to avoid overwriting samples: {output}")
    output.mkdir(parents=True, exist_ok=True)

    samples = []
    for requested in names:
        name = validate_name(requested)
        completed = subprocess.run(
            [str(tool), str(cpk), name],
            cwd=output, capture_output=True, text=True, errors="replace", check=False
        )
        expected = output.joinpath(*name.split("/")).resolve()
        if not expected.is_relative_to(output) or not expected.is_file():
            raise RuntimeError(f"Failed to extract {name}: {completed.stdout[-1000:]} {completed.stderr[-1000:]}")
        samples.append({"path": name, **fingerprint(expected)})
        print(f"Extracted: {name} ({samples[-1]['bytes']:,} bytes)")
    return {
        "format": "Sakurasou-RU selected metadata v1",
        "samples": samples,
        "notice": "No extracted game file contents are embedded in this report.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpk", type=Path, required=True)
    parser.add_argument("--tool", type=Path, default=Path("tools/bin/CriPakTools.exe"))
    parser.add_argument("--out", type=Path, default=Path("work/samples"))
    parser.add_argument("--report", type=Path, default=Path("work/reports/samples.json"))
    parser.add_argument("--name", action="append", help="Exact path inside CPK; repeat to select files")
    args = parser.parse_args(argv)
    try:
        report = extract_samples(args.cpk, args.tool, args.out, args.name or DEFAULT_SAMPLES)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(f"Metadata report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
