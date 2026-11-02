#!/usr/bin/env python3
"""Sakurasou-RU complete local resource audit: ALL Japanese-bearing surfaces.

Processes files already extracted from the user's own DATA.CPK (and optionally
STRM.CPK). Generates metadata-only inventory CSV/JSON and optional private
SSB translation-candidate CSVs. Does not overwrite game assets or send text
online. Never mistake *no detectable UTF-8* for *no Japanese content*.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re

from ssb_extract import extract as extract_ssb

SCRIPT = {".ssb"}
TEXT_TABLES = {".cmed", ".tipd", ".tmd", ".slpd", ".tskd", ".tskt"}
GRAPHICS = {".txg", ".txgtl", ".cbg", ".csu", ".loc", ".gxt", ".dds"}
FONTS = {".fnt"}
VIDEO = {".pmf", ".usm", ".mp4", ".m2v"}
AUDIO = {".awb", ".adx", ".hca", ".at9", ".wav"}
MODELS = {".lbd"}
JP_PATTERN = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
INVENTORY_FIELDS = (
    "archive", "path", "bytes", "extension", "category", "magic_hex",
    "japanese_utf8_hint", "dialogue_candidates", "localized_manifest",
    "translation_status", "visual_review", "notes",
)
MAX_SCAN_BYTES = 32 * 1024 * 1024


def category_for(suffix: str) -> str:
    if suffix in SCRIPT:
        return "script"
    if suffix in TEXT_TABLES:
        return "text_or_configuration"
    if suffix in GRAPHICS:
        return "texture_or_graphics"
    if suffix in FONTS:
        return "font"
    if suffix in VIDEO:
        return "video"
    if suffix in AUDIO:
        return "audio"
    if suffix in MODELS:
        return "models"
    return "unknown_review_required"


def hint_count(data: bytes) -> int:
    # This heuristic is only a signal; binary/encoded text is often invisible.
    text = data.decode("utf-8", errors="ignore")
    return len(JP_PATTERN.findall(text))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def known_manifests(directory: Path) -> dict[str, list[dict]]:
    known: dict[str, list[dict]] = {}
    if not directory.is_dir():
        return known
    for path in sorted(directory.glob("*.ru.json")):
        try:
            info = json.loads(path.read_text(encoding="utf-8"))
            name = info.get("scene")
            if info.get("format") != "sakurasou-ssb-ru-manifest-v1":
                continue
            if not name or Path(name).name != name or not name.endswith(".ssb"):
                continue
        except (ValueError, OSError, AttributeError):
            continue
        known.setdefault(name, []).append({"name": path.name, "sha": info.get("original_sha256")})
    return known


def write_csv(output: Path, records: list[dict]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing audit CSV: {output}")
    with output.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=INVENTORY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def audit_root(root: Path, archive: str, manifests: dict, *, export: Path | None,
               max_read: int = MAX_SCAN_BYTES) -> list[dict]:
    if not root.is_dir():
        raise FileNotFoundError(f"Extraction directory is missing: {root}")
    results = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root)
        ext = path.suffix.lower()
        cat = category_for(ext)
        total = path.stat().st_size
        with path.open("rb") as fp:
            magic = fp.read(16).hex(" ")
        readable = total <= max_read
        candidates = 0
        jp_hint = 0
        notes: list[str] = []
        translations = manifests.get(path.name, []) if cat == "script" else []
        matched = ""
        if readable and cat in ("script", "text_or_configuration", "unknown_review_required"):
            data = path.read_bytes()
            jp_hint = hint_count(data)
            if cat == "script":
                try:
                    records, _ = extract_ssb(data)
                    candidates = len(records)
                    if export is not None:
                        csv_path = export / archive / rel.with_suffix(".csv")
                        if csv_path.exists():
                            notes.append("existing_local_csv_preserved")
                        elif records:
                            csv_path.parent.mkdir(parents=True, exist_ok=True)
                            fields = list(records[0])
                            with csv_path.open("w", encoding="utf-8-sig", newline="") as fp:
                                writer = csv.DictWriter(fp, fieldnames=fields)
                                writer.writeheader()
                                writer.writerows(records)
                except ValueError as e:
                    notes.append(f"unknown_script_variant:{str(e)[:65]}")
            if translations:
                digest = hashlib.sha256(data).hexdigest()
                recognized = [m for m in translations if m["sha"] == digest]
                if recognized:
                    matched = ",".join(m["name"] for m in recognized)
                else:
                    notes.append("manifest_hash_mismatch")
        elif not readable and cat in ("script", "text_or_configuration", "unknown_review_required"):
            notes.append("oversize_binary_skipped_heuristics")
        if cat == "script":
            status = "translation_manifest_exists_needs_runtime_review" if matched else "needs_translation"
        elif cat == "text_or_configuration":
            status = "needs_format_analysis_and_translation"
        elif cat == "texture_or_graphics":
            status = "needs_decode_and_visual_text_review"
        elif cat == "video":
            status = "needs_video_frame_and_subtitle_review"
        elif cat == "font":
            status = "needs_glyph_spacing_and_render_review"
        else:
            status = "needs_japanese_content_review"
        results.append({
            "archive": archive,
            "path": rel.as_posix(),
            "bytes": total,
            "extension": ext or "(none)",
            "category": cat,
            "magic_hex": magic,
            "japanese_utf8_hint": jp_hint,
            "dialogue_candidates": candidates,
            "localized_manifest": matched,
            "translation_status": status,
            "visual_review": "yes" if cat in ("texture_or_graphics", "video", "font",
                                                "models", "unknown_review_required") else "maybe",
            "notes": ";".join(notes),
        })
    return results


def make_summary(rows: list[dict]) -> dict:
    categories = Counter(r["category"] for r in rows)
    extensions = Counter(r["extension"] for r in rows)
    statuses = Counter(r["translation_status"] for r in rows)
    archive_counts = Counter(r["archive"] for r in rows)
    return {
        "format": "Sakurasou-RU total-content-audit v1",
        "files_total": len(rows),
        "assets_per_archive": dict(sorted(archive_counts.items())),
        "categories": dict(sorted(categories.items())),
        "extensions": dict(sorted(extensions.items())),
        "translation_statuses": dict(sorted(statuses.items())),
        "ssb_candidate_dialogues": sum(r["dialogue_candidates"] for r in rows),
        "files_with_utf8_japanese_hint": sum(r["japanese_utf8_hint"] > 0 for r in rows),
        "graphics_awaiting_visual_review": categories["texture_or_graphics"],
        "note": (
            "This is coverage/inventory, NOT an assertion that all Japanese content is translated. "
            "Textures, videos, compiled code, images, and encoded or compressed strings may contain "
            "Japanese even when a UTF-8 scan finds nothing. Local full CSVs must not be published."
        ),
    }


def run(args) -> dict:
    known = known_manifests(args.manifests)
    rows = audit_root(args.assets, "DATA", known, export=args.export_ssb)
    if args.stream_assets:
        rows.extend(audit_root(args.stream_assets, "STRM", known, export=args.export_ssb))
    if not rows:
        raise ValueError("No extracted files found")
    summary = make_summary(rows)
    if args.game_root:
        game = args.game_root
        summary["game_root_outside_cpk"] = {
            "eboot_bin_found": (game / "eboot.bin").is_file(),
            "sce_sys_found": (game / "sce_sys").is_dir(),
            "notice": "UI strings in executable/sce_sys are NOT included in CPK and must be separately audited.",
        }
    if args.report.exists() or args.csv.exists():
        raise FileExistsError("Report or CSV already exists; rename or archive previous audit first")
    write_csv(args.csv, rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--assets", type=Path, default=Path("work/all-assets-scan"),
                    help="Extracted DATA.CPK contents, NOT the CPK archive itself")
    ap.add_argument("--stream-assets", type=Path, default=None,
                    help="Optional separate extracted STRM.CPK contents")
    ap.add_argument("--game-root", type=Path, default=None,
                    help="Optional original PCSG00129 folder; check eboot.bin/sce_sys")
    ap.add_argument("--manifests", type=Path, default=Path("translations"))
    ap.add_argument("--report", type=Path, default=Path("work/reports/complete_audit.json"))
    ap.add_argument("--csv", type=Path, default=Path("work/reports/complete_inventory.csv"))
    ap.add_argument("--export-ssb", type=Path, default=None,
                    help="Export private translation CSV for EVERY discovered SSB")
    args = ap.parse_args(argv)
    try:
        summary = run(args)
    except (OSError, ValueError) as exc:
        ap.exit(1, f"Total-content audit FAILED: {exc}\n")
    print("Total files:", summary["files_total"])
    print("SSB dialogue candidates:", summary["ssb_candidate_dialogues"])
    for cat, n in summary["categories"].items():
        print(f"  {cat:<28} {n}")
    print("Graphics awaiting visual review:", summary["graphics_awaiting_visual_review"])
    print("Inventory:", args.csv)
    print("Report:", args.report)
    print("NOTE: This is an inventory, not 100% localization.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
