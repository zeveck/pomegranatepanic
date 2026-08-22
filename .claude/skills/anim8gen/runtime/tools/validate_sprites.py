#!/usr/bin/env python3
"""Validate aligned sprite frames for structural issues and likely drift."""

from __future__ import annotations

import argparse
import colorsys
import json
import math
from pathlib import Path
from statistics import median
from typing import Any

from PIL import Image


Mask = list[bool]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--frames", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def output_name(frame: dict[str, Any]) -> str:
    return f"frame-{frame['index']:03d}.{frame['label']}.png"


def pct_delta(a: float, b: float) -> float:
    baseline = (abs(a) + abs(b)) / 2
    if baseline == 0:
        return 0.0
    return abs(a - b) / baseline * 100


def hue_delta(a: float, b: float) -> float:
    diff = abs(a - b) % 360
    return min(diff, 360 - diff)


def mask_from_image(image: Image.Image, alpha_threshold: int) -> Mask:
    return [pixel[3] > alpha_threshold for pixel in image.get_flattened_data()]


def bbox_for(mask: Mask, width: int) -> tuple[int, int, int, int] | None:
    xs: list[int] = []
    ys: list[int] = []
    for idx, visible in enumerate(mask):
        if visible:
            xs.append(idx % width)
            ys.append(idx // width)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def centroid(mask: Mask, width: int) -> tuple[float, float]:
    points = [(idx % width, idx // width) for idx, visible in enumerate(mask) if visible]
    if not points:
        return 0.0, 0.0
    return sum(x for x, _ in points) / len(points), sum(y for _, y in points) / len(points)


def anchor_for(mask: Mask, width: int, bbox: tuple[int, int, int, int], strategy: str) -> tuple[float, float]:
    min_x, _min_y, max_x, max_y = bbox
    cx, cy = centroid(mask, width)
    if strategy in ("body_bottom_center", "feet_center"):
        band_y = max_y - 4
        xs = [idx % width for idx, visible in enumerate(mask) if visible and idx // width >= band_y]
        if xs:
            xs.sort()
            middle = len(xs) // 2
            anchor_x = xs[middle] if len(xs) % 2 else (xs[middle - 1] + xs[middle]) / 2
        else:
            anchor_x = (min_x + max_x) / 2
        return float(anchor_x), float(max_y)
    if strategy == "body_center":
        return cx, cy
    if strategy == "head_center":
        min_y = bbox[1]
        upper_limit = min_y + max(1, (max_y - min_y + 1) // 3)
        points = [(idx % width, idx // width) for idx, visible in enumerate(mask) if visible and idx // width <= upper_limit]
        if not points:
            return cx, cy
        xs = sorted(x for x, _ in points)
        ys = sorted(y for _, y in points)
        middle = len(points) // 2
        return float(xs[middle]), float(ys[middle])
    return cx, cy


def frame_stats(path: Path, frame: dict[str, Any], alpha_threshold: int) -> tuple[dict[str, Any] | None, str | None]:
    try:
        image = Image.open(path).convert("RGBA")
    except OSError as exc:
        return None, f"unreadable image: {exc}"

    width, height = image.size
    mask = mask_from_image(image, alpha_threshold)
    bbox = bbox_for(mask, width)
    if bbox is None:
        return None, "empty sprite mask"

    pixels = list(image.get_flattened_data())
    visible_pixels = [pixels[idx] for idx, visible in enumerate(mask) if visible]
    luminance_values = [0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b, _a in visible_pixels]
    mean_luminance = sum(luminance_values) / len(luminance_values)

    hue_bins: dict[int, int] = {}
    for r, g, b, _a in visible_pixels:
        hue, saturation, value = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if saturation < 0.08 or value < 0.08:
            continue
        hue_bin = round(hue * 360) % 360
        hue_bins[hue_bin] = hue_bins.get(hue_bin, 0) + 1
    dominant_hue = max(hue_bins.items(), key=lambda item: item[1])[0] if hue_bins else 0
    anchor_strategy = frame.get("anchor", "body_bottom_center")
    anchor = anchor_for(mask, width, bbox, anchor_strategy)
    cx, cy = centroid(mask, width)

    min_x, min_y, max_x, max_y = bbox
    return (
        {
            "index": frame["index"],
            "label": frame["label"],
            "path": str(path),
            "dimensions": [width, height],
            "bbox": [min_x, min_y, max_x, max_y],
            "bboxWidth": max_x - min_x + 1,
            "bboxHeight": max_y - min_y + 1,
            "visibleArea": len(visible_pixels),
            "centroid": [round(cx, 3), round(cy, 3)],
            "anchorStrategy": anchor_strategy,
            "anchor": [round(anchor[0], 3), round(anchor[1], 3)],
            "meanLuminance": round(mean_luminance, 3),
            "dominantHueDegrees": dominant_hue,
            "mask": mask,
        },
        None,
    )


def effective_thresholds(spec: dict[str, Any], left_index: int, right_index: int) -> tuple[str | None, dict[str, float], list[str]]:
    thresholds = dict(spec["validation"]["defaultThresholds"])
    for phase in spec["validation"].get("motionPhases", []):
        frame_set = set(phase.get("frames", []))
        if left_index in frame_set and right_index in frame_set:
            thresholds.update(phase.get("thresholdOverrides", {}))
            return phase.get("name"), thresholds, list(phase.get("ignoredWarnings", []))
    return None, thresholds, []


def silhouette_iou(left: Mask, right: Mask) -> float:
    intersection = 0
    union = 0
    for a, b in zip(left, right):
        if a or b:
            union += 1
            if a and b:
                intersection += 1
    return intersection / union if union else 0.0


def add_warning(
    warnings: list[dict[str, Any]],
    metric: str,
    message: str,
    value: float,
    threshold: float,
    severity: str = "warning",
) -> None:
    warnings.append(
        {
            "metric": metric,
            "severity": severity,
            "value": round(value, 3),
            "threshold": threshold,
            "message": message,
        }
    )


def compare_frames(left: dict[str, Any], right: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    phase_name, thresholds, ignored = effective_thresholds(spec, left["index"], right["index"])
    warnings: list[dict[str, Any]] = []

    anchor_x_jump = abs(right["anchor"][0] - left["anchor"][0])
    anchor_y_jump = abs(right["anchor"][1] - left["anchor"][1])
    bbox_width_delta = pct_delta(left["bboxWidth"], right["bboxWidth"])
    bbox_height_delta = pct_delta(left["bboxHeight"], right["bboxHeight"])
    area_delta = pct_delta(left["visibleArea"], right["visibleArea"])
    centroid_jump = math.dist(left["centroid"], right["centroid"])
    head_top_drift = abs(right["bbox"][1] - left["bbox"][1])
    iou = silhouette_iou(left["mask"], right["mask"])
    luminance_delta = pct_delta(left["meanLuminance"], right["meanLuminance"])
    hue_shift = hue_delta(left["dominantHueDegrees"], right["dominantHueDegrees"])

    if anchor_x_jump > thresholds.get("anchorXJumpPx", math.inf):
        add_warning(warnings, "anchorXJumpPx", "anchor x jump exceeds threshold", anchor_x_jump, thresholds["anchorXJumpPx"])
    if anchor_y_jump > thresholds.get("anchorYJumpPx", math.inf):
        add_warning(warnings, "anchorYJumpPx", "anchor y jump exceeds threshold", anchor_y_jump, thresholds["anchorYJumpPx"])
    if bbox_width_delta > thresholds.get("bboxWidthVariancePct", math.inf):
        add_warning(warnings, "bboxWidthVariancePct", "bbox width changed more than expected", bbox_width_delta, thresholds["bboxWidthVariancePct"])
    if bbox_height_delta > thresholds.get("bboxHeightVariancePct", math.inf):
        add_warning(warnings, "bboxHeightVariancePct", "bbox height changed more than expected", bbox_height_delta, thresholds["bboxHeightVariancePct"])
    if area_delta > thresholds.get("visibleAreaVariancePct", math.inf):
        add_warning(warnings, "visibleAreaVariancePct", "visible area changed more than expected", area_delta, thresholds["visibleAreaVariancePct"])
    if centroid_jump > thresholds.get("centroidJumpPx", math.inf):
        add_warning(warnings, "centroidJumpPx", "centroid jump exceeds threshold", centroid_jump, thresholds["centroidJumpPx"])
    if head_top_drift > thresholds.get("headTopDriftPx", math.inf):
        add_warning(warnings, "headTopDriftPx", "top of head drift exceeds phase threshold", head_top_drift, thresholds["headTopDriftPx"])
    if iou < thresholds.get("adjacentSilhouetteIouMin", -math.inf):
        add_warning(warnings, "adjacentSilhouetteIouMin", "adjacent silhouette overlap is low", iou, thresholds["adjacentSilhouetteIouMin"])
    if luminance_delta > thresholds.get("meanLuminanceShiftPct", math.inf):
        add_warning(warnings, "meanLuminanceShiftPct", "mean luminance shifted more than expected", luminance_delta, thresholds["meanLuminanceShiftPct"])
    if hue_shift > thresholds.get("dominantHueShiftDegrees", math.inf):
        add_warning(warnings, "dominantHueShiftDegrees", "dominant hue shifted more than expected", hue_shift, thresholds["dominantHueShiftDegrees"])

    warnings = [warning for warning in warnings if warning["metric"] not in ignored]
    notes = [
        {"code": warning_name, "severity": "info", "message": f"{warning_name} ignored for this motion phase"}
        for warning_name in ignored
    ]

    return {
        "from": left["index"],
        "to": right["index"],
        "labels": [left["label"], right["label"]],
        "phase": phase_name or "default",
        "effectiveThresholds": thresholds,
        "metrics": {
            "anchorXJumpPx": round(anchor_x_jump, 3),
            "anchorYJumpPx": round(anchor_y_jump, 3),
            "bboxWidthVariancePct": round(bbox_width_delta, 3),
            "bboxHeightVariancePct": round(bbox_height_delta, 3),
            "visibleAreaVariancePct": round(area_delta, 3),
            "centroidJumpPx": round(centroid_jump, 3),
            "headTopDriftPx": round(head_top_drift, 3),
            "adjacentSilhouetteIou": round(iou, 3),
            "meanLuminanceShiftPct": round(luminance_delta, 3),
            "dominantHueShiftDegrees": round(hue_shift, 3),
        },
        "warnings": warnings,
        "notes": notes,
    }


def strip_masks(frame: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in frame.items() if key != "mask"}


def stabilize_frame_anchor_x(frames: list[dict[str, Any]], spec: dict[str, Any]) -> None:
    if not spec["alignment"].get("stabilizeAnchorX", True) or not frames:
        return
    stable_x = median([frame["anchor"][0] for frame in frames])
    for frame in frames:
        frame["measuredAnchor"] = frame["anchor"]
        frame["anchor"] = [round(stable_x, 3), frame["anchor"][1]]


def edge_padding_warnings(frame: dict[str, Any], spec: dict[str, Any]) -> list[dict[str, Any]]:
    threshold = spec["validation"]["defaultThresholds"].get("edgePaddingPx", 0)
    if threshold <= 0:
        return []
    width, height = frame["dimensions"]
    min_x, min_y, max_x, max_y = frame["bbox"]
    paddings = {
        "left": min_x,
        "top": min_y,
        "right": width - max_x - 1,
        "bottom": height - max_y - 1,
    }
    warnings: list[dict[str, Any]] = []
    for edge, padding in paddings.items():
        if padding < threshold:
            add_warning(
                warnings,
                "edgePaddingPx",
                f"{edge} edge padding is below threshold",
                padding,
                threshold,
                "warning" if padding > 0 else "error",
            )
    frame["edgePadding"] = paddings
    return warnings


def print_table(comparisons: list[dict[str, Any]], structural_failures: list[dict[str, Any]]) -> None:
    print("pair       phase           warnings  iou    centroid  area%")
    print("--------- --------------- --------- ------ --------- ------")
    for item in comparisons:
        metrics = item["metrics"]
        print(
            f"{item['from']:03d}->{item['to']:03d}  "
            f"{item['phase'][:15]:15} "
            f"{len(item['warnings']):9d} "
            f"{metrics['adjacentSilhouetteIou']:6.3f} "
            f"{metrics['centroidJumpPx']:9.3f} "
            f"{metrics['visibleAreaVariancePct']:6.2f}"
        )
    if structural_failures:
        print("\nstructural failures:")
        for failure in structural_failures:
            print(f"- frame {failure['index']:03d}: {failure['message']}")


def main() -> None:
    args = parse_args()
    spec = json.loads(Path(args.spec).read_text())
    frame_dir = Path(args.frames)
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    alpha_threshold = spec["segmentation"].get("alphaThreshold", 8)

    frames: list[dict[str, Any]] = []
    structural_failures: list[dict[str, Any]] = []
    expected_dimensions = tuple(spec["render"]["canvas"])
    for frame in spec["frames"]:
        path = frame_dir / output_name(frame)
        if not path.exists():
            structural_failures.append({"index": frame["index"], "label": frame["label"], "path": str(path), "message": "missing frame"})
            continue
        stats, error = frame_stats(path, frame, alpha_threshold)
        if error or stats is None:
            structural_failures.append({"index": frame["index"], "label": frame["label"], "path": str(path), "message": error})
            continue
        if tuple(stats["dimensions"]) != expected_dimensions:
            structural_failures.append(
                {
                    "index": frame["index"],
                    "label": frame["label"],
                    "path": str(path),
                    "message": f"inconsistent dimensions {stats['dimensions']} expected {list(expected_dimensions)}",
                }
            )
            continue
        frames.append(stats)

    frames.sort(key=lambda item: item["index"])
    stabilize_frame_anchor_x(frames, spec)
    frame_warnings = [
        {"frameIndex": frame["index"], "frameLabel": frame["label"], "warnings": edge_padding_warnings(frame, spec)}
        for frame in frames
    ]
    comparisons = [compare_frames(left, right, spec) for left, right in zip(frames, frames[1:])]
    if spec["alignment"].get("loopClosure", True) and len(frames) > 2:
        loop_comparison = compare_frames(frames[-1], frames[0], spec)
        loop_comparison["loopClosure"] = True
        comparisons.append(loop_comparison)
    warning_count = sum(len(item["warnings"]) for item in comparisons)
    warning_count += sum(len(item["warnings"]) for item in frame_warnings)
    result = {
        "id": spec["id"],
        "spec": args.spec,
        "framesDir": args.frames,
        "status": "failed" if structural_failures else "passed",
        "summary": {
            "frameCount": len(frames),
            "expectedFrameCount": len(spec["frames"]),
            "structuralFailureCount": len(structural_failures),
            "warningCount": warning_count,
        },
        "structuralFailures": structural_failures,
        "frameWarnings": frame_warnings,
        "frames": [strip_masks(frame) for frame in frames],
        "comparisons": comparisons,
    }
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    print_table(comparisons, structural_failures)
    print(f"\nwrote validation report to {output_path}")
    if structural_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
