#!/usr/bin/env python3
"""Restore the unmodified original title_start.gxt inside a previously patched CPK.

Reason: the initial title/press-start graphic is NOT the five circular main-menu
buttons, and an experimental 'НАЧАТЬ' texture was shown widely spaced on
the splash screen. This tool restores ONLY that texture while retaining all
other CPK entries and checking the Russian main scenario byte-for-byte.

No need for the missing clean decrypted DATA.CPK. Source CPK and original
user-extracted GXT remain untouched. Output is a NEW separately verified CPK.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import tempfile

from build_multi_cpk import build as build_multi
from build_test_cpk import extract_one, digest

EXPECTED_ORIGINAL_GXT_SHA256 = "1e8d4644bb9b7f2f92cb9a9c4538a92b65e5d6e0b2cb627e2ab365da64dbf382"
SCENE_TO_PROTECT = "SCN_MAIN_1Y_1112__010.ssb"


def fix(source: Path, original_gxt: Path, tool: Path, dest: Path) -> dict:
    if not source.is_file():
        raise FileNotFoundError(f"Previously patched CPK missing: {source}")
    if not original_gxt.is_file():
        raise FileNotFoundError(f"Original extracted title_start.gxt missing: {original_gxt}")
    if not tool.is_file():
        raise FileNotFoundError(f"CriPakTools.exe missing: {tool}")
    actual = digest(original_gxt)
    if actual.lower() != EXPECTED_ORIGINAL_GXT_SHA256.lower():
        raise ValueError("Source title_start.gxt SHA256 differs from tested original; refusing to overwrite")
    if dest.exists():
        raise FileExistsError(f"Output CPK already exists: {dest}")
    if source.resolve() == dest.resolve():
        raise ValueError("Source and output CPK must be different paths")
    manifest = {
        "format": "sakurasou-multi-cpk-v1",
        "replacements": [
            {
                "entry": "title_start.gxt",
                "file": str(original_gxt.resolve()),
                "sha256": actual,
            }
        ]
    }

    # The shared packer verifies the archive table and extracted texture.
    result = build_multi(source, manifest, tool, dest)
    with tempfile.TemporaryDirectory(prefix="sakurasou-preserve-") as temp:
        root = Path(temp)
        before = extract_one(tool, source, SCENE_TO_PROTECT, root / "source")
        after = extract_one(tool, dest, SCENE_TO_PROTECT, root / "fixed")
        if digest(before) != digest(after):
            # Do not allow an apparently successful repair to be installed.
            raise AssertionError("Russian story scenario differs after title texture restoration!")
    print("Restored original title_start.gxt; Russian SSB unchanged.")
    print("New isolated CPK:", dest)
    print("Verified archive entries:", result["archive_entry_count"])
    print("Original/patched source CPK was not modified.")
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path,
                   default=Path("work/title_test_build/DATA_MAIN_TITLE_RU_TEST.CPK"))
    p.add_argument("--texture", type=Path,
                   default=Path("work/all-assets-scan/title_start.gxt"))
    p.add_argument("--tool", type=Path,
                   default=Path("tools/bin/CriPakTools.exe"))
    p.add_argument("--out", type=Path,
                   default=Path("work/patches/DATA_RU_TITLE_RESTORED.CPK"))
    args = p.parse_args(argv)
    try:
        fix(args.source, args.texture, args.tool, args.out)
    except (OSError, ValueError, RuntimeError, AssertionError) as exc:
        p.exit(1, f"Title texture restoration FAILED: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
