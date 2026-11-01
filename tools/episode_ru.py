#!/usr/bin/env python3
"""Sakurasou-RU: prepare, machine-draft, validate, and build ONE complete SSB scene.

All copyrighted source files, extracted dialogue, translation cache and built
game archives remain on the USER'S PC under work/. Nothing is uploaded to GitHub.
The explicit --online flag sends Japanese dialogue to Google Translate through
deep-translator; review the draft for accuracy and text-box overflow.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import tempfile
import time

from ssb_extract import extract, iter_strings, classify, find_story_start, JP_RE
from ssb_patch_relocate import build as build_ssb
from fnt_inspect import FNTFont
from build_test_cpk import build as build_cpk

SCENES = {
    "1y": "SCN_MAIN_1Y_1112__010.ssb",
    "2y": "SCN_MAIN_2Y_0214__010.ssb",
}
NAMES = {
    "神田空太": "Сората Канда",
    "椎名ましろ": "Масиро Сиина",
    "青山七海": "Нанами Аояма",
    "上井草美咲": "Мисаки Камиигуса",
    "三鷹仁": "Дзин Митака",
    "赤坂龍之介": "Рюносукэ Акасака",
    "千石千尋": "Тихиро Сэнгоку",
}
COLUMNS = [
    "id", "offset_hex", "original_bytes", "kind", "speaker_candidate",
    "voice_candidate", "source_ja", "translation_ru", "pointer_count",
    "status", "notes",
]
DASHES = str.maketrans({
    "—": "-", "–": "-", "−": "-", "‑": "-", "―": "-",
    "“": '"', "”": '"', "„": '"', "’": "'", "‘": "'",
    "\u00a0": " ", "\u200b": "",
})


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def paths(args):
    name = SCENES[args.scene]
    stem = Path(name).stem
    return {
        "input": args.assets / name,
        "csv": args.work / "translations" / (stem + "_RU.csv"),
        "prep_report": args.work / "reports" / (stem + "_prepare.json"),
        "cache": args.work / "translations" / (stem + "_machine_cache.json"),
        "ssb": args.work / "patches" / (stem + "_RU_DRAFT.ssb"),
        "ssb_report": args.work / "reports" / (stem + "_patched.json"),
        "cpk": args.work / "patches" / ("DATA_EPISODE_" + args.scene.upper() + "_RU_DRAFT.CPK"),
    }


def atomic_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".sakurasou-", suffix=".json.tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".sakurasou-", suffix=".csv.tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not set(COLUMNS).issubset(reader.fieldnames or ()):
            raise ValueError(f"{path}: CSV columns are missing; use prepare")
        rows = list(reader)
    if not rows:
        raise ValueError("No extracted rows in CSV")
    return rows


def index_pointers(data: bytes) -> dict[int, list[int]]:
    boundary = find_story_start(data)
    if boundary is None or boundary % 4:
        raise ValueError("Unknown SSB scene boundary: cannot validate pointers")
    result = defaultdict(list)
    for pos in range(4, boundary - 3, 4):
        if struct.unpack_from("<I", data, pos - 4)[0] == 3:
            word = struct.unpack_from("<I", data, pos)[0]
            result[word * 4].append(pos)
    return result


def prepare(args, p) -> list[dict]:
    if p["csv"].exists():
        raise FileExistsError(f"Refusing to overwrite existing local translations: {p['csv']}")
    if not p["input"].is_file():
        raise FileNotFoundError(f"Extracted scene missing: {p['input']}")
    data = p["input"].read_bytes()
    extracted, stats = extract(data)
    start = find_story_start(data)
    speakers = [
        {
            "id": f"ssb_{entry['offset']:08x}",
            "offset_hex": f"0x{entry['offset']:08X}",
            "original_bytes": entry["byte_len"],
            "kind": "speaker",
            "speaker_candidate": entry["source"],
            "voice_candidate": "",
            "source_ja": entry["source"],
            "translation_ru": NAMES.get(entry["source"], ""),
            "notes": "",
        }
        for entry in iter_strings(data, start)
        if classify(entry["source"]) == "speaker_candidate"
    ]
    dialogues = [dict(item, kind="dialogue") for item in extracted]
    ptrs = index_pointers(data)
    rows = speakers + dialogues
    rows.sort(key=lambda row: int(row["offset_hex"], 0))
    if not rows:
        raise ValueError("No recognizable text strings in episode")
    for row in rows:
        refs = ptrs.get(int(row["offset_hex"], 0), [])
        row["pointer_count"] = str(len(refs))
        eligible = len(refs) == 1
        row["status"] = "ready" if eligible else "manual_inspection"
        if not eligible:
            row["translation_ru"] = ""
            row["notes"] = f"SKIPPED: {len(refs)} verified opcode-3 pointers (must be 1)"
    if not any(row["status"] == "ready" and row["kind"] == "dialogue" for row in rows):
        raise ValueError("No safely patchable dialogue in this SSB")
    report = {
        "format": "Sakurasou-RU episode preparer v1",
        "scene": SCENES[args.scene],
        "original_sha256": sha(data),
        "total_text_candidates": len(rows),
        "dialogue_candidates": sum(r["kind"] == "dialogue" for r in rows),
        "speaker_candidates": sum(r["kind"] == "speaker" for r in rows),
        "eligible_verified_one_pointer": sum(r["status"] == "ready" for r in rows),
        "unpatchable_needs_manual_inspection": sum(r["status"] != "ready" for r in rows),
        "exported_dialogue_heuristic": stats["exported_text_candidates"],
        "warning": "Heuristic; completeness of all gameplay text not guaranteed. Local CSV is copyrighted user data.",
    }
    atomic_csv(p["csv"], rows)
    atomic_json(p["prep_report"], report)
    print("Prepared scene:", report["scene"])
    print("Dialogues:", report["dialogue_candidates"], "speakers:", report["speaker_candidates"])
    print("Safely patchable:", report["eligible_verified_one_pointer"],
          "requires investigation:", report["unpatchable_needs_manual_inspection"])
    print("Editable local CSV:", p["csv"])
    return rows


def translate_dialogue(source: str, translate_fn) -> str:
    """Preserve original scene markers and exact count of line separators."""
    if source in NAMES:
        return NAMES[source]
    result = []
    pieces = re.split(r"([▼▽])", source)
    for piece in pieces:
        if piece in ("▼", "▽"):
            result.append(piece)
            continue
        lines = piece.split("\n")
        localized = []
        for line in lines:
            leading = len(line) - len(line.lstrip(" \u3000"))
            trailing = len(line) - len(line.rstrip(" \u3000"))
            core = line.strip()
            if JP_RE.search(core):
                translated = translate_fn(core)
                if not isinstance(translated, str) or not translated.strip():
                    raise ValueError("Translator returned empty or invalid text")
                core = translated.strip().translate(DASHES)
                if any(marker in core for marker in "▼▽") or "\x00" in core or "\n" in core:
                    raise ValueError("Translator inserted a scene marker or a line break")
            localized.append((" " * leading) + core + (" " * trailing))
        result.append("\n".join(localized))
    answer = "".join(result)
    if answer.count("\n") != source.count("\n"):
        raise AssertionError("Line count changed")
    for m in ("▼", "▽"):
        if answer.count(m) != source.count(m):
            raise AssertionError(f"Scene marker {m} count changed")
    return answer


def online_translate(args, p) -> tuple[int, int]:
    if not args.online:
        raise ValueError("Online machine translation requires explicit --online "
                         "(Japanese text will be sent to a third-party service)")
    try:
        from deep_translator import GoogleTranslator
    except ImportError as exc:
        raise RuntimeError("Install dependency: py -3 -m pip install deep-translator") from exc

    rows = read_csv(p["csv"])
    if not p["input"].is_file():
        raise FileNotFoundError("Original extracted scene missing")
    prep = json.loads(p["prep_report"].read_text(encoding="utf-8"))
    if sha(p["input"].read_bytes()) != prep["original_sha256"]:
        raise ValueError("Original SSB changed since CSV extraction; refusing translation")
    cache = json.loads(p["cache"].read_text(encoding="utf-8")) if p["cache"].exists() else {}
    if not isinstance(cache, dict):
        raise ValueError("Invalid machine translation cache")
    translator = GoogleTranslator(source="ja", target="ru")
    performed = 0
    errors = 0

    def translate_fragment(value: str) -> str:
        nonlocal performed
        if value in cache:
            return cache[value]
        for attempt in range(3):
            try:
                text = translator.translate(value)
                if not text or not text.strip():
                    raise ValueError("Empty translation")
                cache[value] = text
                atomic_json(p["cache"], cache)
                performed += 1
                time.sleep(0.3)
                return text
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 ** (attempt + 1))
        raise AssertionError("Unreachable")

    print("DRAFT MACHINE TRANSLATION. Japanese text is sent to Google Translate.", flush=True)
    for i, row in enumerate(rows):
        if row["status"] != "ready" or (row["translation_ru"] or "").strip():
            continue
        try:
            row["translation_ru"] = translate_dialogue(row["source_ja"], translate_fragment)
            # Mark overly wide lines for review, without introducing unvalidated newlines.
            longest = max(len(line.replace("▼", "").replace("▽", "")) for line
                          in row["translation_ru"].split("\n"))
            row["notes"] = (row.get("notes") or "")
            if longest > args.max_line_chars:
                row["notes"] = f"REVIEW DISPLAY WIDTH: {longest} characters in longest line"
            atomic_csv(p["csv"], rows)
            print(f"[{i + 1}/{len(rows)}] translated {row['kind']}, "
                  f"offset {row['offset_hex']}", flush=True)
        except Exception as exc:
            errors += 1
            atomic_csv(p["csv"], rows)
            print(f"Stopped at {row['offset_hex']}: {exc}. Re-run to resume.", flush=True)
            break
    pending = sum(r["status"] == "ready" and not (r["translation_ru"] or "").strip()
                  for r in rows)
    print(f"Translator requests: {performed}; pending patchable rows: {pending}; errors: {errors}")
    return performed, pending


def finish(args, p) -> None:
    rows = read_csv(p["csv"])
    original = p["input"].read_bytes()
    prep = json.loads(p["prep_report"].read_text(encoding="utf-8"))
    if sha(original) != prep["original_sha256"]:
        raise ValueError("Source SSB SHA256 does not match exported translation CSV")
    eligible = [r for r in rows if r["status"] == "ready"]
    unpatchable = [r for r in rows if r["status"] != "ready"]
    if not eligible:
        raise ValueError("Nothing can be safely patched")
    missing = [r for r in eligible if not (r["translation_ru"] or "").strip()]
    if missing and not args.partial:
        raise ValueError(f"{len(missing)} patchable rows have no translation; "
                         "run translate --online or edit the CSV; "
                         "use --partial only if deliberately testing an incomplete episode")
    if any(p[k].exists() for k in ("ssb", "ssb_report", "cpk")):
        raise FileExistsError("Output already exists; refusing to overwrite previously built patch")
    if not args.cpk or not args.cpk.is_file():
        raise FileNotFoundError("--cpk must point to ORIGINAL decrypted DATA.CPK")
    if not args.tool.is_file():
        raise FileNotFoundError(f"CriPakTools is missing: {args.tool}")
    fonts = [FNTFont(f) for f in args.fonts]
    final_rows = [r for r in eligible if (r["translation_ru"] or "").strip()]
    patched, report = build_ssb(original, final_rows, expected_sha=prep["original_sha256"], fonts=fonts)
    if report["modified_pointer_operands"] != len(final_rows):
        raise ValueError("Not every translated row was actually patched")
    report["scene"] = SCENES[args.scene]
    report["eligible_rows"] = len(eligible)
    report["translated_rows"] = len(final_rows)
    report["unpatchable_rows"] = len(unpatchable)
    report["skipped_untranslated_rows"] = len(missing)
    report["unreviewed_machine_translation"] = True
    # The binary is written only locally and can be used for a rebuild.
    p["ssb"].parent.mkdir(parents=True, exist_ok=True)
    p["ssb_report"].parent.mkdir(parents=True, exist_ok=True)
    p["ssb"].write_bytes(patched)
    try:
        cpk_report = build_cpk(
            args.cpk, p["ssb"], args.tool, p["cpk"],
            entry=SCENES[args.scene], expected_ssb_sha=report["patched_sha256"]
        )
    except Exception:
        p["ssb"].unlink(missing_ok=True)
        raise
    report["cpk_verified"] = cpk_report["patched_ssb_roundtrip_verified"]
    report["cpk_sha256"] = cpk_report["modified_cpk_sha256"]
    atomic_json(p["ssb_report"], report)
    print("BULK DRAFT CPK READY:", p["cpk"])
    print(f"Translated {len(final_rows)}/{len(eligible)} patchable rows; "
          f"{len(unpatchable)} strings require structural inspection")
    print("Verified CPK roundtrip:", report["cpk_verified"])
    print("This is a MACHINE DRAFT. Review meanings and text-box overflow in Vita3K.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "translate", "build", "run"))
    parser.add_argument("--scene", choices=SCENES.keys(), default="1y")
    parser.add_argument("--assets", type=Path, default=Path("work/all-assets-scan"))
    parser.add_argument("--work", type=Path, default=Path("work"))
    parser.add_argument("--cpk", type=Path)
    parser.add_argument("--tool", type=Path, default=Path("tools/bin/CriPakTools.exe"))
    parser.add_argument("--fonts", type=Path, nargs="*", default=[
        Path("work/samples/font_m.fnt"), Path("work/samples/font_s.fnt")])
    parser.add_argument("--online", action="store_true", help="Consent: send original Japanese dialogue to Google Translate")
    parser.add_argument("--partial", action="store_true", help="Explicitly allow incomplete translations")
    parser.add_argument("--max-line-chars", type=int, default=42)
    args = parser.parse_args(argv)
    p = paths(args)
    try:
        if args.mode in ("prepare", "run"):
            if not p["csv"].exists():
                prepare(args, p)
            elif args.mode == "prepare":
                raise FileExistsError("CSV already exists: " + str(p["csv"]))
            else:
                print("Resuming existing translation CSV:", p["csv"])
        if args.mode in ("translate", "run"):
            _, pending = online_translate(args, p)
            if args.mode == "run" and pending and not args.partial:
                raise ValueError("Translation incomplete; run again to resume before building CPK")
        if args.mode in ("build", "run"):
            finish(args, p)
    except (OSError, ValueError, RuntimeError, AssertionError) as exc:
        parser.exit(1, f"Episode translation FAILED: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
