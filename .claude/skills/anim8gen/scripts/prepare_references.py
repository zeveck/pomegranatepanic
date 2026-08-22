#!/usr/bin/env python3
"""Copy and prepare anim8gen reference images for generation."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
RUNTIME_TOOLS = SKILL_DIR / "runtime" / "tools"
sys.path.insert(0, str(RUNTIME_TOOLS))

import clean_reference  # noqa: E402


SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="Anim8gen animation spec JSON.")
    parser.add_argument("--project-root", default=".", help="Project root for relative reference paths.")
    parser.add_argument("--manifest", help="Optional manifest output path. Defaults to reference/prepared-references.json.")
    parser.add_argument("--no-cleanup", action="store_true", help="Use references exactly as provided.")
    return parser.parse_args()


def path_text(path: Path, project_root: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return resolved.relative_to(project_root.expanduser().resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def resolve_source(path: str, project_root: Path) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    resolved = candidate.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"reference does not exist: {path}")
    return resolved


def safe_name(path: Path, index: int) -> str:
    stem = SAFE_NAME_RE.sub("-", path.stem).strip("-._") or f"reference-{index}"
    suffix = path.suffix.lower() or ".png"
    return f"{index:02d}-{stem}{suffix}"


def prepare_references(
    spec_path: Path,
    project_root: Path,
    *,
    manifest_path: Path | None = None,
    no_cleanup: bool = False,
) -> dict[str, Any]:
    spec = json.loads(spec_path.read_text())
    references = spec.get("asset", {}).get("references", [])
    if not isinstance(references, list):
        raise ValueError("spec.asset.references must be an array")

    run_root = spec_path.parent.parent
    reference_dir = run_root / "reference"
    reference_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_path or reference_dir / "prepared-references.json"

    global_cleanup = bool(spec.get("generation", {}).get("referenceCleanup", True)) and not no_cleanup
    prepared: list[dict[str, Any]] = []
    selected_key: str | None = None
    for index, reference in enumerate(references):
        if not isinstance(reference, dict):
            raise ValueError(f"spec.asset.references[{index}] must be an object")
        source = resolve_source(str(reference["path"]), project_root)
        stored_original = reference_dir / f"original-{safe_name(source, index)}"
        shutil.copy2(source, stored_original)

        cleanup_enabled = bool(reference.get("cleanup", global_cleanup)) and global_cleanup
        generation_path = stored_original
        cleanup_report_path: Path | None = None
        cleanup_summary = "original preserved"
        if cleanup_enabled and source.suffix.lower() == ".png":
            clean_name = f"{stored_original.stem.removeprefix('original-')}.clean.png"
            generation_path = reference_dir / clean_name
            cleanup_report_path = reference_dir / f"{generation_path.stem}.report.json"
            image = clean_reference.Image.open(source).convert("RGBA")
            selected_key = selected_key or clean_reference.choose_chroma_key(image)
            report = clean_reference.clean_reference(source, generation_path, chroma_key=selected_key)
            cleanup_report_path.write_text(json.dumps(report, indent=2) + "\n")
            cleanup_summary = "prepared reference image; original preserved"
        elif cleanup_enabled:
            cleanup_summary = "original preserved; cleanup skipped for non-PNG reference"
        else:
            cleanup_summary = "using original reference exactly as provided"

        prepared.append(
            {
                "index": index,
                "role": reference["role"],
                **({"frameIndex": reference["frameIndex"]} if "frameIndex" in reference else {}),
                **({"note": reference["note"]} if "note" in reference else {}),
                "source": path_text(source, project_root),
                "storedOriginal": path_text(stored_original, project_root),
                "generationPath": path_text(generation_path, project_root),
                "cleanupApplied": generation_path != stored_original,
                "cleanupReport": path_text(cleanup_report_path, project_root) if cleanup_report_path else None,
                "summary": cleanup_summary,
            }
        )

    manifest = {
        "id": spec.get("id"),
        "referenceCleanup": global_cleanup,
        "selectedChromaKey": selected_key,
        "references": prepared,
        "userSummary": [
            "I prepared the reference image for animation. The original was preserved."
            for item in prepared
            if item["cleanupApplied"]
        ],
    }
    if selected_key:
        spec.setdefault("segmentation", {})["chromaKey"] = selected_key
        spec_path.write_text(json.dumps(spec, indent=2) + "\n")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    args = parse_args()
    manifest = prepare_references(
        Path(args.spec),
        Path(args.project_root).expanduser().resolve(),
        manifest_path=Path(args.manifest) if args.manifest else None,
        no_cleanup=args.no_cleanup,
    )
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
