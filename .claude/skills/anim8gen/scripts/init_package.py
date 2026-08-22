#!/usr/bin/env python3
"""Initialize an Anim8gen package from a prepared JSON brief."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from layout_paths import resolve_layout


ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ANCHORS = {"body_bottom_center", "feet_center", "body_center", "head_center", "manual"}
VIEWS = {"side", "front", "three-quarter", "top-down", "isometric"}
PACKAGE_DIRS = ("reference", "raw", "aligned", "review", "manifests")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, help="Path to a prepared Anim8gen brief JSON file.")
    parser.add_argument(
        "--root",
        help=(
            "Deprecated compatibility alias for the run root. Prefer "
            "--workspace-root and --export-root."
        ),
    )
    parser.add_argument("--project-root", default=".", help="Project root for relative package paths.")
    parser.add_argument(
        "--workspace-root",
        help="Hidden anim8gen workspace root. Defaults to ANIM8GEN_WORKSPACE_ROOT or .anim8gen.",
    )
    parser.add_argument(
        "--export-root",
        help="Visible export root. Defaults to ANIM8GEN_EXPORT_ROOT or assets/anim8gen.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite an existing spec and manifests.")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: brief must be a JSON object")
    return data


def require_text(data: dict[str, Any], key: str, default: str | None = None) -> str:
    value = data.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"brief.{key} must be a non-empty string")
    return value.strip()


def require_pair(data: dict[str, Any], key: str, default: list[int], minimum: int, maximum: int) -> list[int]:
    value = data.get(key, default)
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(isinstance(item, int) for item in value)
        or not all(minimum <= item <= maximum for item in value)
    ):
        raise SystemExit(f"brief.{key} must be two integers between {minimum} and {maximum}")
    return [int(value[0]), int(value[1])]


def validate_frames(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_frames = data.get("frames")
    if not isinstance(raw_frames, list) or not (2 <= len(raw_frames) <= 12):
        raise SystemExit("brief.frames must contain 2 to 12 frame objects")

    frames: list[dict[str, Any]] = []
    seen_labels: set[str] = set()
    for expected_index, raw_frame in enumerate(raw_frames):
        if not isinstance(raw_frame, dict):
            raise SystemExit(f"brief.frames[{expected_index}] must be an object")
        index = raw_frame.get("index")
        if index != expected_index:
            raise SystemExit(
                f"brief.frames[{expected_index}].index must be contiguous from 0; got {index!r}"
            )
        label = require_text(raw_frame, "label")
        if not ID_RE.fullmatch(label):
            raise SystemExit(f"brief.frames[{expected_index}].label must be lowercase kebab-case")
        if label in seen_labels:
            raise SystemExit(f"duplicate frame label: {label}")
        seen_labels.add(label)
        pose = require_text(raw_frame, "pose")
        anchor = raw_frame.get("anchor", "body_bottom_center")
        if anchor not in ANCHORS:
            raise SystemExit(f"brief.frames[{expected_index}].anchor must be one of {sorted(ANCHORS)}")
        frame = {"index": index, "label": label, "pose": pose, "anchor": anchor}
        reuse_frame = raw_frame.get("reuseFrame")
        if reuse_frame is not None:
            if not isinstance(reuse_frame, int) or not (0 <= reuse_frame < expected_index):
                raise SystemExit(
                    f"brief.frames[{expected_index}].reuseFrame must reference an earlier frame index"
                )
            frame["reuseFrame"] = reuse_frame
        frames.append(frame)
    return frames


def validate_references(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_references = data.get("references", [])
    if not isinstance(raw_references, list) or len(raw_references) > 16:
        raise SystemExit("brief.references must be an array with at most 16 items")
    allowed_roles = {"canonical", "style", "pose", "frame", "frame-set", "contact-sheet"}
    references: list[dict[str, Any]] = []
    for index, raw_reference in enumerate(raw_references):
        if not isinstance(raw_reference, dict):
            raise SystemExit(f"brief.references[{index}] must be an object")
        path = require_text(raw_reference, "path")
        role = require_text(raw_reference, "role")
        if role not in allowed_roles:
            raise SystemExit(f"brief.references[{index}].role must be one of {sorted(allowed_roles)}")
        reference: dict[str, Any] = {"path": path, "role": role}
        frame_index = raw_reference.get("frameIndex")
        if frame_index is not None:
            if not isinstance(frame_index, int) or not (0 <= frame_index <= 11):
                raise SystemExit(f"brief.references[{index}].frameIndex must be an integer from 0 to 11")
            reference["frameIndex"] = frame_index
        note = raw_reference.get("note")
        if note is not None:
            if not isinstance(note, str):
                raise SystemExit(f"brief.references[{index}].note must be a string")
            reference["note"] = note
        cleanup = raw_reference.get("cleanup")
        if cleanup is not None:
            if not isinstance(cleanup, bool):
                raise SystemExit(f"brief.references[{index}].cleanup must be a boolean")
            reference["cleanup"] = cleanup
        references.append(reference)
    return references


def path_text(path: Path, project_root: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return resolved.relative_to(project_root.expanduser().resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def build_spec(
    brief: dict[str, Any],
    *,
    canonical_reference: str | None = None,
    candidate_manifest: str | None = None,
    accepted_manifest: str | None = None,
) -> dict[str, Any]:
    animation_id = require_text(brief, "id")
    if not ID_RE.fullmatch(animation_id):
        raise SystemExit("brief.id must be lowercase kebab-case")

    subject = require_text(brief, "subject")
    style = require_text(brief, "style", "pixel art")
    view = require_text(brief, "view", "side")
    if view not in VIEWS:
        raise SystemExit(f"brief.view must be one of {sorted(VIEWS)}")
    canvas = require_pair(brief, "canvas", [128, 128], 32, 512)
    working_size = require_pair(brief, "workingSize", [1024, 1024], 256, 2048)
    fps = brief.get("fps", 8)
    if not isinstance(fps, int) or not (1 <= fps <= 24):
        raise SystemExit("brief.fps must be an integer between 1 and 24")
    resampling = brief.get("resampling", "auto")
    if resampling not in {"auto", "nearest", "lanczos"}:
        raise SystemExit("brief.resampling must be one of auto, nearest, lanczos")
    edge_treatment = brief.get("edgeTreatment", "auto")
    if edge_treatment not in {"auto", "hard", "soft"}:
        raise SystemExit("brief.edgeTreatment must be one of auto, hard, soft")
    retry_budget = brief.get("retryBudget", 2)
    if not isinstance(retry_budget, int) or not (0 <= retry_budget <= 5):
        raise SystemExit("brief.retryBudget must be an integer between 0 and 5")
    reference_cleanup = brief.get("referenceCleanup", True)
    if not isinstance(reference_cleanup, bool):
        raise SystemExit("brief.referenceCleanup must be a boolean")
    runtime_effects = brief.get("runtimeEffects", [])
    if not isinstance(runtime_effects, list) or not all(isinstance(item, str) for item in runtime_effects):
        raise SystemExit("brief.runtimeEffects must be an array of strings")
    display_offsets = brief.get("displayOffsets", {})
    if not isinstance(display_offsets, dict):
        raise SystemExit("brief.displayOffsets must be an object")
    for key, offset in display_offsets.items():
        if not isinstance(key, str) or not isinstance(offset, dict):
            raise SystemExit("brief.displayOffsets must map frame indexes or labels to objects")
        if not isinstance(offset.get("x"), (int, float)) or not isinstance(offset.get("y"), (int, float)):
            raise SystemExit(f"brief.displayOffsets.{key} must include numeric x and y")
        if "reason" in offset and not isinstance(offset["reason"], str):
            raise SystemExit(f"brief.displayOffsets.{key}.reason must be a string")

    floor_y = brief.get("floorY", max(0, canvas[1] - 16))
    if not isinstance(floor_y, int) or not (0 <= floor_y < canvas[1]):
        raise SystemExit("brief.floorY must be an integer inside the canvas height")

    prompt_traits = [
        "single subject",
        f"{view}-view",
        "compact readable silhouette",
        "solid chroma-key background",
        "no text",
    ]
    references = validate_references(brief)

    return {
        "id": animation_id,
        "asset": {
            "subject": subject,
            "style": style,
            "canonicalReference": canonical_reference or f".anim8gen/runs/{animation_id}/reference/reference.png",
            "references": references,
            "promptTraits": prompt_traits,
        },
        "render": {
            "canvas": canvas,
            "workingSize": working_size,
            "exportScale": brief.get("exportScale", 8),
            "fps": fps,
            "paletteLimit": brief.get("paletteLimit", 48),
            "resampling": resampling,
            "edgeTreatment": edge_treatment,
        },
        "generation": {
            "preferredSkill": "imagegen2",
            "candidateManifest": candidate_manifest or f".anim8gen/runs/{animation_id}/manifests/candidates.jsonl",
            "acceptedManifest": accepted_manifest or f".anim8gen/runs/{animation_id}/manifests/accepted-frames.json",
            "retryBudget": retry_budget,
            "referenceCleanup": reference_cleanup,
        },
        "segmentation": {
            "strategy": "chroma-key",
            "chromaKey": brief.get("chromaKey", "#ff00ff"),
            "alphaThreshold": brief.get("alphaThreshold", 8),
            "chromaTolerance": brief.get("chromaTolerance", 32),
        },
        "alignment": {
            "defaultAnchor": brief.get("defaultAnchor", "body_bottom_center"),
            "floorY": floor_y,
            "stabilizeAnchorX": brief.get("stabilizeAnchorX", True),
            "loopClosure": brief.get("loopClosure", True),
            "supportedAnchors": sorted(ANCHORS),
            "manualOverrides": {},
        },
        "validation": {
            "defaultThresholds": {
                "anchorXJumpPx": 3,
                "anchorYJumpPx": 2,
                "edgePaddingPx": 2,
                "bboxHeightVariancePct": 12,
                "bboxWidthVariancePct": 18,
                "visibleAreaVariancePct": 20,
                "centroidJumpPx": 5,
                "adjacentSilhouetteIouMin": 0.55,
                "meanLuminanceShiftPct": 15,
                "dominantHueShiftDegrees": 12,
            },
            "motionPhases": [],
        },
        "preview": {
            "strategy": "canvas-playback",
            "displayOffsets": display_offsets,
            "runtimeEffects": runtime_effects,
            "minimalControls": ["playPause", "fps", "step", "frameLabel", "checkerboard"],
        },
        "frames": validate_frames(brief),
    }


def package_gitignore() -> str:
    return """# Generated or externally produced image assets stay out of source control.
reference/*
raw/*
aligned/*
review/*

# Keep the package folder structure visible.
!reference/.gitkeep
!raw/.gitkeep
!aligned/.gitkeep
!review/.gitkeep
!review/*.json
!review/*.md
"""


def project_gitignore_block() -> str:
    return """# anim8gen local run workspace
.anim8gen/
"""


def write_if_missing(path: Path, content: str, force: bool = False) -> None:
    if path.exists() and not force:
        raise SystemExit(f"{path} already exists; pass --force to overwrite")
    path.write_text(content)


def ensure_project_gitignore(project_root: Path) -> None:
    gitignore_path = project_root / ".gitignore"
    block = project_gitignore_block()
    required = [line for line in block.splitlines() if line and not line.startswith("#")]
    existing = gitignore_path.read_text() if gitignore_path.exists() else ""
    existing_lines = set(existing.splitlines())
    if all(pattern in existing_lines for pattern in required):
        return

    prefix = "" if not existing or existing.endswith("\n") else "\n"
    spacer = "" if not existing.strip() else "\n"
    with gitignore_path.open("a") as handle:
        handle.write(f"{prefix}{spacer}{block}")


def init_package(root: Path, spec: dict[str, Any], force: bool) -> None:
    init_package_at(root, spec, force=force, project_root=Path.cwd(), export_root=None)


def init_package_at(root: Path, spec: dict[str, Any], *, force: bool, project_root: Path, export_root: Path | None) -> None:
    animation_id = spec["id"]
    config_dir = root / "config"
    reference_dir = root / "reference"
    raw_dir = root / "raw"
    aligned_dir = root / "aligned"
    review_dir = root / "review"
    manifests_dir = root / "manifests"
    reports_dir = root / "reports"
    preview_dir = root / "preview"
    gifs_dir = root / "gifs"

    for path in (config_dir, reports_dir, preview_dir, gifs_dir):
        path.mkdir(parents=True, exist_ok=True)
    for folder in PACKAGE_DIRS:
        package_dir = root / folder
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / ".gitkeep").touch()

    spec_path = config_dir / f"{animation_id}.json"
    candidate_manifest_path = manifests_dir / "candidates.jsonl"
    accepted_manifest_path = manifests_dir / "accepted-frames.json"
    preview_path = preview_dir / f"{animation_id}.html"
    export_path = export_root / animation_id if export_root is not None else None

    ensure_project_gitignore(project_root)
    write_if_missing(root / ".gitignore", package_gitignore(), force=force)
    write_if_missing(config_dir / f"{animation_id}.json", json.dumps(spec, indent=2) + "\n", force=force)
    write_if_missing(candidate_manifest_path, "", force=force)
    write_if_missing(
        review_dir / "frame-reviews.json",
        json.dumps(
            {
                "id": animation_id,
                "reviewSchemaVersion": 1,
                "packageStatus": "initialized",
                "retryBudget": spec["generation"]["retryBudget"],
                "frames": [],
            },
            indent=2,
        )
        + "\n",
        force=force,
    )

    accepted_manifest = {
        "id": animation_id,
        "status": "initialized",
        "generator": {
            "skill": "imagegen2",
            "candidateManifest": path_text(candidate_manifest_path, project_root),
        },
        "frames": [],
    }
    write_if_missing(
        accepted_manifest_path,
        json.dumps(accepted_manifest, indent=2) + "\n",
        force=force,
    )

    package_manifest = {
        "id": animation_id,
        "packageStatus": "initialized",
        "runRoot": path_text(root, project_root),
        "spec": path_text(spec_path, project_root),
        "reference": path_text(reference_dir, project_root),
        "raw": path_text(raw_dir, project_root),
        "aligned": path_text(aligned_dir, project_root),
        "review": path_text(review_dir, project_root),
        "manifests": path_text(manifests_dir, project_root),
        "preview": path_text(preview_path, project_root),
        "gifs": path_text(gifs_dir, project_root),
        "reports": {
            "validation": path_text(reports_dir / f"{animation_id}.validation.json", project_root),
            "package": path_text(reports_dir / f"{animation_id}.package.md", project_root),
        },
    }
    if export_path is not None:
        package_manifest["export"] = path_text(export_path, project_root)
    write_if_missing(
        manifests_dir / "package-manifest.json",
        json.dumps(package_manifest, indent=2) + "\n",
        force=force,
    )


def main() -> None:
    args = parse_args()
    brief = load_json(Path(args.brief))
    animation_id = require_text(brief, "id")
    if args.root:
        project_root = Path(args.project_root).expanduser().resolve()
        root = Path(args.root).expanduser()
        if not root.is_absolute():
            root = project_root / root
        root = root.resolve()
        export_root = None
    else:
        layout = resolve_layout(
            animation_id,
            args.project_root,
            workspace_root=args.workspace_root,
            export_root=args.export_root,
        )
        project_root = layout.project_root
        root = layout.run_root
        export_root = layout.export_root.parent

    spec = build_spec(
        brief,
        canonical_reference=path_text(root / "reference" / "reference.png", project_root),
        candidate_manifest=path_text(root / "manifests" / "candidates.jsonl", project_root),
        accepted_manifest=path_text(root / "manifests" / "accepted-frames.json", project_root),
    )
    init_package_at(root, spec, force=args.force, project_root=project_root, export_root=export_root)
    print(f"initialized {spec['id']}")
    print(f"spec: {root / 'config' / (spec['id'] + '.json')}")
    print(f"run: {root}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
