#!/usr/bin/env python3
"""One command: experimental Russian title-start graphic + preserved story CPK.

Runs only on the user's machine using:
  * original decrypted DATA.CPK
  * original extracted title_start.gxt
  * previously translated SCN_MAIN_1Y_1112__010_FULL_RU.ssb
  * optionally translated SCN_MAIN_1Y_1112__020_FULL_RU.ssb

Builds new, separate CPK including ALL listed changes, verifies the CPK.
NEVER modifies Vita3K installation or the original decrypted DATA.CPK.
Review the experimental Russian image fit in the game before treating it
as a release asset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from create_title_start_ru import make_label
from build_multi_cpk import build as build_combined

FIRST_SCENE = "SCN_MAIN_1Y_1112__010.ssb"
SECOND_SCENE = "SCN_MAIN_1Y_1112__020.ssb"


def prepare(source_texture: Path, patched_texture: Path, preview: Path):
    if patched_texture.exists() or preview.exists():
        raise FileExistsError("Experimental GXT/PNG output already exists; refuse overwrite")
    original = source_texture.read_bytes()
    png, modified = make_label(original)
    patched_texture.parent.mkdir(parents=True, exist_ok=True)
    preview.parent.mkdir(parents=True, exist_ok=True)
    patched_texture.write_bytes(modified)
    png.save(preview)
    return hashlib.sha256(modified).hexdigest()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original",type=Path,required=True,
                   help="ORIGINAL decrypted Sakurasou DATA.CPK")
    p.add_argument("--assets",type=Path,default=Path("work/all-assets-scan"))
    p.add_argument("--patches",type=Path,default=Path("work/patches"))
    p.add_argument("--tool",type=Path,default=Path("tools/bin/CriPakTools.exe"))
    p.add_argument("--with-second-scene",action="store_true",
                   help="Include already built translated MAIN_1Y_020.ssb")
    args=p.parse_args(argv)
    gxt_original=args.assets/"title_start.gxt"
    ru_scene=args.patches/"SCN_MAIN_1Y_1112__010_FULL_RU.ssb"
    ru_second=args.patches/"SCN_MAIN_1Y_1112__020_FULL_RU.ssb"
    ru_gxt=args.patches/"title_start_RU_TEST.gxt"
    png=args.patches/"title_start_RU_TEST.png"
    cpk=args.patches/"DATA_MAIN_TITLE_RU_TEST.CPK"
    report=args.patches/"DATA_MAIN_TITLE_RU_TEST.meta.json"
    try:
        if not args.original.is_file() or not args.tool.is_file():
            raise FileNotFoundError("Missing original decrypted DATA.CPK or CriPakTools.exe")
        if not gxt_original.is_file() or not ru_scene.is_file():
            raise FileNotFoundError("Need original title_start.gxt AND translated MAIN_1Y_010 SSB")
        if args.with_second_scene and not ru_second.is_file():
            raise FileNotFoundError("Requested translated MAIN_1Y_020 SSB is not built yet")
        if any(path.exists() for path in
               (ru_gxt,png,cpk,report,cpk.with_name(cpk.stem+".report.json"))):
            raise FileExistsError("Test outputs already exist. Preserve or move them before rebuilding.")
        sha=prepare(gxt_original,ru_gxt,png)
        items=[
            {"entry":FIRST_SCENE,"file":str(ru_scene)},
            {"entry":"title_start.gxt","file":str(ru_gxt),"sha256":sha}
        ]
        if args.with_second_scene:
            items.insert(1,{"entry":SECOND_SCENE,"file":str(ru_second)})
        combined=build_combined(
            args.original,{"format":"sakurasou-multi-cpk-v1","replacements":items},
            args.tool,cpk
        )
        meta={
            "format":"sakurasou-RU-title-image-test-v1",
            "cpk":str(cpk),
            "replacements":[r["entry"] for r in items],
            "verified":combined["every_replacement_verified"],
            "experimental_russian_title_graphic":True,
            "gameplay_verified":False
        }
        report.write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding="utf-8")
    except (OSError,ValueError,RuntimeError,AssertionError) as exc:
        p.exit(1,f"Russian title test build FAILED: {exc}\n")
    print("Verified test CPK:",cpk)
    print("Modified files:",", ".join(r["entry"] for r in items))
    print("Test PNG:",png)
    print("Local gameplay verification still required; the original DATA.CPK was NOT changed.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
