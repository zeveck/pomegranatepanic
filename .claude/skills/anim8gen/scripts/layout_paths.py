#!/usr/bin/env python3
"""Resolve anim8gen workspace, export, scratch, and runtime paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_WORKSPACE_ROOT = ".anim8gen"
DEFAULT_EXPORT_ROOT = "assets/anim8gen"
LEGACY_WORKSPACE_ROOT = "anim8gen"


@dataclass(frozen=True)
class Anim8genLayout:
    project_root: Path
    workspace_root: Path
    run_root: Path
    config_dir: Path
    reference_dir: Path
    raw_dir: Path
    aligned_dir: Path
    review_dir: Path
    manifest_dir: Path
    report_dir: Path
    preview_dir: Path
    gif_dir: Path
    scratch_root: Path
    export_root: Path
    export_frames_dir: Path
    export_raw_dir: Path
    runtime_tool_root: Path
    legacy_spec_path: Path

    @property
    def spec_path(self) -> Path:
        return self.config_dir / f"{self.run_root.name}.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("animation_id", help="Animation package id.")
    parser.add_argument("--project-root", default=".", help="Project root or directory inside the project.")
    parser.add_argument("--workspace-root", help="Override ANIM8GEN_WORKSPACE_ROOT for this resolution.")
    parser.add_argument("--export-root", help="Override ANIM8GEN_EXPORT_ROOT for this resolution.")
    parser.add_argument("--tmpdir", help="Override ANIM8GEN_TMPDIR for this resolution.")
    parser.add_argument(
        "--field",
        choices=[
            "project_root",
            "workspace_root",
            "run_root",
            "scratch_root",
            "export_root",
            "runtime_tool_root",
            "spec_path",
            "legacy_spec_path",
        ],
        help="Print only one resolved field.",
    )
    parser.add_argument("--json", action="store_true", help="Print the full layout as JSON.")
    return parser.parse_args()


def _project_root(start: Path) -> Path:
    current = start.expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def _resolve_under_project(project_root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _project_hash(project_root: Path) -> str:
    return hashlib.sha1(str(project_root.resolve()).encode("utf-8")).hexdigest()[:12]


def resolve_layout(
    animation_id: str,
    project_root: Path | str | None = None,
    *,
    workspace_root: str | Path | None = None,
    export_root: str | Path | None = None,
    tmpdir: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    skill_dir: Path = SKILL_DIR,
) -> Anim8genLayout:
    env = os.environ if env is None else env
    root = _project_root(Path(project_root or "."))

    workspace_value = str(workspace_root or env.get("ANIM8GEN_WORKSPACE_ROOT", DEFAULT_WORKSPACE_ROOT))
    workspace = _resolve_under_project(root, workspace_value)
    run_root = workspace / "runs" / animation_id

    export_value = str(export_root or env.get("ANIM8GEN_EXPORT_ROOT", DEFAULT_EXPORT_ROOT))
    export_base = _resolve_under_project(root, export_value)
    export_package = export_base / animation_id

    tmp_value = str(tmpdir or env.get("ANIM8GEN_TMPDIR", ""))
    if tmp_value:
        scratch_base = Path(tmp_value).expanduser()
    else:
        scratch_base = Path(tempfile.gettempdir()) / f"anim8gen-{_project_hash(root)}"
    if not scratch_base.is_absolute():
        scratch_base = root / scratch_base
    scratch = scratch_base.resolve() / animation_id / "scratch"

    runtime_tool_root = (skill_dir / "runtime" / "tools").resolve()

    return Anim8genLayout(
        project_root=root,
        workspace_root=workspace,
        run_root=run_root,
        config_dir=run_root / "config",
        reference_dir=run_root / "reference",
        raw_dir=run_root / "raw",
        aligned_dir=run_root / "aligned",
        review_dir=run_root / "review",
        manifest_dir=run_root / "manifests",
        report_dir=run_root / "reports",
        preview_dir=run_root / "preview",
        gif_dir=run_root / "gifs",
        scratch_root=scratch,
        export_root=export_package,
        export_frames_dir=export_package / "frames",
        export_raw_dir=export_package / "raw",
        runtime_tool_root=runtime_tool_root,
        legacy_spec_path=root / LEGACY_WORKSPACE_ROOT / "config" / f"{animation_id}.json",
    )


def layout_to_json(layout: Anim8genLayout) -> str:
    data = {key: str(value) for key, value in asdict(layout).items()}
    data["spec_path"] = str(layout.spec_path)
    return json.dumps(data, indent=2, sort_keys=True)


def main() -> None:
    args = parse_args()
    layout = resolve_layout(
        args.animation_id,
        args.project_root,
        workspace_root=args.workspace_root,
        export_root=args.export_root,
        tmpdir=args.tmpdir,
    )
    if args.field:
        print(getattr(layout, args.field))
    elif args.json:
        print(layout_to_json(layout))
    else:
        print(layout.run_root)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
