#!/usr/bin/env python3
"""Create deterministic chroma-keyed raw PNG candidates for Anim8gen tests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="Path to an Anim8gen animation spec JSON file.")
    parser.add_argument(
        "--root",
        help="Hidden run root. Defaults to the spec parent package root.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing synthetic raw frames.")
    return parser.parse_args()


def load_spec(path: Path) -> dict[str, Any]:
    try:
        spec = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(spec, dict) or not isinstance(spec.get("frames"), list):
        raise SystemExit(f"{path}: not an Anim8gen spec")
    return spec


def parse_hex_color(value: str) -> tuple[int, int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        raise SystemExit("segmentation.chromaKey must be a #rrggbb color")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4)) + (255,)


def draw_pixel_square(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, color: tuple[int, int, int, int]) -> None:
    draw.rectangle((x, y, x + size - 1, y + size - 1), fill=color)


def draw_sprite(draw: ImageDraw.ImageDraw, frame: dict[str, Any], image_size: tuple[int, int]) -> None:
    width, height = image_size
    index = int(frame["index"])
    unit = max(4, min(width, height) // 16)
    body_size = unit * 4
    x_offset = (index % 4) * unit
    hop = unit if "hop" in frame.get("label", "") or "up" in frame.get("label", "") else 0
    base_x = width // 2 - body_size // 2 + x_offset
    base_y = height // 2 - body_size // 2 - hop

    body = (66, 135, 245, 255)
    outline = (12, 34, 72, 255)
    highlight = (133, 196, 255, 255)
    shadow = (21, 79, 160, 255)

    draw.rectangle(
        (base_x - unit // 2, base_y - unit // 2, base_x + body_size + unit // 2, base_y + body_size + unit // 2),
        fill=outline,
    )
    draw.rectangle((base_x, base_y, base_x + body_size, base_y + body_size), fill=body)
    draw.rectangle((base_x + unit, base_y + unit, base_x + unit * 2, base_y + unit * 2), fill=highlight)
    draw.rectangle((base_x + unit * 3, base_y + unit * 3, base_x + unit * 4, base_y + unit * 4), fill=shadow)

    # Add a simple pose marker that changes per frame without relying on text.
    marker_x = base_x + unit + index * max(1, unit // 2)
    marker_y = base_y - unit * 2 if hop else base_y + body_size + unit
    draw_pixel_square(draw, marker_x, marker_y, unit, (245, 196, 66, 255))


def synthetic_record(spec: dict[str, Any], frame: dict[str, Any], output_path: Path) -> dict[str, Any]:
    animation_id = spec["id"]
    return {
        "generatorSkill": "anim8gen-test-helper",
        "model": "deterministic-synthetic",
        "prompt": f"synthetic test frame for {animation_id} frame {frame['index']} {frame['label']}",
        "negativePrompt": "not applicable; deterministic local test helper",
        "style": [spec.get("asset", {}).get("style", "pixel art")],
        "sourceReferencePath": None,
        "seed": 0,
        "historyId": f"{animation_id}-synthetic-frame-{frame['index']:03d}-retry-001",
        "requestId": f"synthetic-{animation_id}-{frame['index']:03d}",
        "frameIndex": frame["index"],
        "frameLabel": frame["label"],
        "pose": frame["pose"],
        "outputPath": str(output_path),
        "retry": 1,
        "parentCandidate": None,
        "neighboringReference": None,
        "status": "candidate",
        "reviewStatus": "accepted",
        "reviewNotes": "deterministic synthetic helper frame accepted for local plumbing tests",
        "bytes": output_path.stat().st_size,
        "outputFormat": "png",
        "refusalReason": None,
        "testHelper": True,
    }


def synthetic_review(spec: dict[str, Any], frame: dict[str, Any], output_path: Path) -> dict[str, Any]:
    return {
        "frameIndex": frame["index"],
        "frameLabel": frame["label"],
        "candidatePath": str(output_path),
        "retry": 1,
        "poseVerdict": "matches",
        "identityVerdict": "matches",
        "cameraVerdict": "matches",
        "hygieneVerdict": "clean",
        "backgroundVerdict": "segmentable",
        "decision": "accepted",
        "retryReason": None,
        "notes": "Deterministic synthetic helper output for smoke tests, not live imagegen2 output.",
    }


def initialized_review_file(path: Path) -> bool:
    if not path.exists() or not path.read_text().strip():
        return True
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return False
    return (
        isinstance(payload, dict)
        and payload.get("packageStatus") == "initialized"
        and payload.get("frames") == []
    )


def infer_run_root(spec_path: Path) -> Path:
    if spec_path.parent.name == "config":
        return spec_path.parent.parent
    return spec_path.parent


def main() -> None:
    args = parse_args()
    spec_path = Path(args.spec)
    root = Path(args.root) if args.root else infer_run_root(spec_path)
    spec = load_spec(spec_path)
    animation_id = spec["id"]
    working_size = tuple(spec.get("render", {}).get("workingSize", [1024, 1024]))
    if len(working_size) != 2:
        raise SystemExit("render.workingSize must contain width and height")
    background = parse_hex_color(spec.get("segmentation", {}).get("chromaKey", "#ff00ff"))

    raw_dir = root / "raw"
    manifest_dir = root / "manifests"
    review_dir = root / "review"
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    for frame in spec["frames"]:
        if not isinstance(frame, dict) or "index" not in frame or "label" not in frame:
            raise SystemExit("each spec frame must include index and label")
        out = raw_dir / f"frame-{frame['index']:03d}.retry-001.png"
        if out.exists() and not args.force:
            raise SystemExit(f"{out} already exists; pass --force to overwrite")
        image = Image.new("RGBA", working_size, background)
        draw_sprite(ImageDraw.Draw(image), frame, working_size)
        image.save(out)
        records.append(synthetic_record(spec, frame, out))
        reviews.append(synthetic_review(spec, frame, out))

    manifest = manifest_dir / "candidates.jsonl"
    if manifest.exists() and manifest.read_text() and not args.force:
        raise SystemExit(f"{manifest} already has content; pass --force to overwrite")
    manifest.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records))
    review_path = review_dir / "frame-reviews.json"
    if not initialized_review_file(review_path) and not args.force:
        raise SystemExit(f"{review_path} already has content; pass --force to overwrite")
    review_payload = {
        "id": animation_id,
        "reviewSchemaVersion": 1,
        "packageStatus": "complete",
        "retryBudget": spec.get("generation", {}).get("retryBudget", 2),
        "frames": reviews,
    }
    review_path.write_text(json.dumps(review_payload, indent=2) + "\n")
    print(f"wrote {len(records)} synthetic raw frames to {raw_dir}")
    print(f"wrote candidate manifest to {manifest}")
    print(f"wrote frame reviews to {review_path}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
