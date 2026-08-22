#!/usr/bin/env python3
"""Print install-independent anim8gen skill helper paths."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import layout_paths


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "name",
        choices=[
            "skill-dir",
            "script-dir",
            "init-package",
            "prepare-references",
            "validate-review-records",
            "create-synthetic-frames",
            "runtime-tools",
            "runtime-config",
            "align-frames",
            "validate-sprites",
            "make-contact-sheet",
            "make-preview",
            "export-gif",
            "export-webp",
            "export-bundle",
            "clean-reference",
            "brief-schema",
            "template-animation-spec",
            "imagegen2-cli",
        ],
    )
    parser.add_argument("--start", default=".", help="Project search start directory")
    parser.add_argument("--animation-id", default="example", help="Animation id for layout-derived paths")
    return parser.parse_args()


def candidate_roots(start: Path) -> list[Path]:
    roots: list[Path] = []
    current = start.resolve()
    roots.extend([current, *current.parents])
    home = Path.home()
    for raw in (
        os.environ.get("CLAUDE_CONFIG_DIR"),
        os.environ.get("CODEX_HOME"),
    ):
        if raw:
            roots.append(Path(raw).expanduser())
    roots.extend([home / ".claude", home / ".codex"])
    return roots


def find_imagegen2_cli(start: Path) -> Path:
    candidates: list[Path] = []
    for root in candidate_roots(start):
        candidates.extend(
            [
                root / ".claude" / "skills" / "imagegen2" / "generate.cjs",
                root / ".codex" / "skills" / "imagegen2" / "generate.cjs",
                root / ".agents" / "skills" / "imagegen2" / "generate.cjs",
                root / "skills" / "imagegen2" / "generate.cjs",
                root / "imagegen2" / "generate.cjs",
            ]
        )
    sibling = SKILL_DIR.parent / "imagegen2" / "generate.cjs"
    candidates.insert(0, sibling)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit("ERROR: could not find imagegen2 generate.cjs")


def main() -> None:
    args = parse_args()
    layout = layout_paths.resolve_layout(args.animation_id, args.start)
    runtime_tools = layout.runtime_tool_root
    runtime_config = SKILL_DIR / "runtime" / "config"
    paths = {
        "skill-dir": SKILL_DIR,
        "script-dir": SCRIPT_DIR,
        "init-package": SCRIPT_DIR / "init_package.py",
        "prepare-references": SCRIPT_DIR / "prepare_references.py",
        "validate-review-records": SCRIPT_DIR / "validate_review_records.py",
        "create-synthetic-frames": SCRIPT_DIR / "create_synthetic_frames.py",
        "runtime-tools": runtime_tools,
        "runtime-config": runtime_config,
        "align-frames": runtime_tools / "align_frames.py",
        "validate-sprites": runtime_tools / "validate_sprites.py",
        "make-contact-sheet": runtime_tools / "make_contact_sheet.py",
        "make-preview": runtime_tools / "make_preview.py",
        "export-gif": runtime_tools / "export_gif.py",
        "export-webp": runtime_tools / "export_webp.py",
        "export-bundle": runtime_tools / "export_bundle.py",
        "clean-reference": runtime_tools / "clean_reference.py",
        "brief-schema": runtime_config / "brief.schema.json",
        "template-animation-spec": runtime_config / "template.animation-spec.json",
    }
    if args.name == "imagegen2-cli":
        print(find_imagegen2_cli(Path(args.start)))
    else:
        print(paths[args.name])


if __name__ == "__main__":
    main()
