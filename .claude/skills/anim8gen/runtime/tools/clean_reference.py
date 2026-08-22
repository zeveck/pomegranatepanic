#!/usr/bin/env python3
"""Clean reference PNG alpha data for anim8gen."""

from __future__ import annotations

import argparse
import json
import math
from collections import deque
from pathlib import Path
from typing import Any

from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Source image path.")
    parser.add_argument("--output", required=True, help="Cleaned PNG output path.")
    parser.add_argument("--report", help="Optional JSON report path.")
    parser.add_argument("--chroma-key", default="#ff00ff", help="Hex chroma-key color to remove.")
    parser.add_argument("--chroma-tolerance", type=int, default=32, help="RGB distance tolerance, 0-442.")
    parser.add_argument("--alpha-threshold", type=int, default=8, help="Alpha values at or below this become 0.")
    parser.add_argument("--remove-key-family", action="store_true", help="Also remove broad anti-aliased key-family colors.")
    parser.add_argument(
        "--max-visible-removal-ratio",
        type=float,
        default=0.02,
        help="Fail if cleanup removes more than this fraction of visible pixels.",
    )
    return parser.parse_args()


def parse_hex_color(value: str) -> tuple[int, int, int]:
    text = value.strip().lstrip("#")
    if len(text) != 6:
        raise ValueError(f"invalid chroma key: {value!r}")
    return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))


def color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def is_key_family(rgb: tuple[int, int, int], key: tuple[int, int, int]) -> bool:
    high_channels = [index for index, value in enumerate(key) if value >= 180]
    low_channels = [index for index, value in enumerate(key) if value <= 80]
    if not high_channels or not low_channels:
        return False
    if any(rgb[index] < 120 for index in high_channels):
        return False
    if any(rgb[index] > 150 for index in low_channels):
        return False
    return max(rgb) - min(rgb) >= 60


def alpha_histogram(image: Image.Image) -> list[int]:
    return image.getchannel("A").histogram()


def hidden_rgb_stats(
    image: Image.Image,
    key: tuple[int, int, int],
    tolerance: int,
    *,
    include_key_family: bool = False,
) -> dict[str, Any]:
    transparent = 0
    near_key = 0
    blackish = 0
    for red, green, blue, alpha in image.get_flattened_data():
        if alpha != 0:
            continue
        transparent += 1
        rgb = (red, green, blue)
        if color_distance(rgb, key) <= tolerance or (include_key_family and is_key_family(rgb, key)):
            near_key += 1
        if red <= 16 and green <= 16 and blue <= 16:
            blackish += 1
    return {"transparentPixels": transparent, "nearKeyHiddenRgb": near_key, "blackHiddenRgb": blackish}


def visible_color_stats(
    image: Image.Image,
    key: tuple[int, int, int],
    tolerance: int,
    *,
    include_key_family: bool = False,
) -> dict[str, Any]:
    visible = 0
    near_key = 0
    for red, green, blue, alpha in image.get_flattened_data():
        if alpha == 0:
            continue
        visible += 1
        rgb = (red, green, blue)
        if color_distance(rgb, key) <= tolerance or (include_key_family and is_key_family(rgb, key)):
            near_key += 1
    ratio = near_key / visible if visible else 0.0
    return {"visiblePixels": visible, "visibleKeyLikePixels": near_key, "visibleKeyLikeRatio": ratio}


def choose_chroma_key(image: Image.Image, candidates: list[str] | None = None, alpha_threshold: int = 8) -> str:
    candidate_values = candidates or ["#00ffff", "#00ff00", "#0000ff", "#ff00ff", "#ffff00"]
    rgba = image.convert("RGBA")
    visible_pixels = [
        (red, green, blue)
        for red, green, blue, alpha in rgba.get_flattened_data()
        if alpha > alpha_threshold
    ]
    if not visible_pixels:
        return candidate_values[0].lower()

    best_key = candidate_values[0]
    best_score: tuple[float, float] | None = None
    sample_step = max(1, len(visible_pixels) // 20000)
    sampled = visible_pixels[::sample_step]
    for raw_key in candidate_values:
        key = parse_hex_color(raw_key)
        distances = [color_distance(rgb, key) for rgb in sampled]
        min_distance = min(distances)
        mean_distance = sum(distances) / len(distances)
        score = (min_distance, mean_distance)
        if best_score is None or score > best_score:
            best_score = score
            best_key = raw_key
    red, green, blue = parse_hex_color(best_key)
    return f"#{red:02x}{green:02x}{blue:02x}"


def remove_key_pixels(
    image: Image.Image,
    key: tuple[int, int, int],
    tolerance: int,
    alpha_threshold: int,
    *,
    include_key_family: bool = False,
) -> int:
    pixels = image.load()
    removed = 0
    width, height = image.size
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            rgb = (red, green, blue)
            should_remove = (
                alpha <= alpha_threshold
                or color_distance(rgb, key) <= tolerance
                or (include_key_family and is_key_family(rgb, key))
            )
            if should_remove and alpha != 0:
                removed += 1
            if should_remove:
                pixels[x, y] = (red, green, blue, 0)
    return removed


def alpha_bleed_transparent_pixels(image: Image.Image) -> int:
    width, height = image.size
    pixels = image.load()
    nearest = [-1] * (width * height)
    queue: deque[int] = deque()

    for y in range(height):
        for x in range(width):
            index = y * width + x
            if pixels[x, y][3] > 0:
                nearest[index] = index
                queue.append(index)

    if not queue or len(queue) == width * height:
        return 0

    while queue:
        index = queue.popleft()
        source = nearest[index]
        x = index % width
        y = index // width
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if nx < 0 or ny < 0 or nx >= width or ny >= height:
                continue
            next_index = ny * width + nx
            if nearest[next_index] == -1:
                nearest[next_index] = source
                queue.append(next_index)

    bled = 0
    for y in range(height):
        for x in range(width):
            if pixels[x, y][3] != 0:
                continue
            source = nearest[y * width + x]
            if source < 0:
                continue
            sx = source % width
            sy = source // width
            red, green, blue, _alpha = pixels[sx, sy]
            pixels[x, y] = (red, green, blue, 0)
            bled += 1
    return bled


def clean_reference(
    input_path: Path,
    output_path: Path,
    *,
    chroma_key: str = "#ff00ff",
    chroma_tolerance: int = 32,
    alpha_threshold: int = 8,
    max_visible_removal_ratio: float = 0.02,
    remove_key_family: bool = False,
) -> dict[str, Any]:
    if not (0 <= chroma_tolerance <= 442):
        raise ValueError("chroma_tolerance must be between 0 and 442")
    if not (0 <= alpha_threshold <= 255):
        raise ValueError("alpha_threshold must be between 0 and 255")

    key = parse_hex_color(chroma_key)
    before = Image.open(input_path).convert("RGBA")
    cleaned = before.copy()
    before_alpha = alpha_histogram(before)
    before_hidden = hidden_rgb_stats(before, key, chroma_tolerance, include_key_family=remove_key_family)
    before_visible = visible_color_stats(before, key, chroma_tolerance, include_key_family=remove_key_family)
    removed = remove_key_pixels(
        cleaned,
        key,
        chroma_tolerance,
        alpha_threshold,
        include_key_family=remove_key_family,
    )
    alpha_bleed_pixels = alpha_bleed_transparent_pixels(cleaned)
    after_alpha = alpha_histogram(cleaned)
    after_hidden = hidden_rgb_stats(cleaned, key, chroma_tolerance, include_key_family=remove_key_family)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.save(output_path)

    report = {
        "input": str(input_path),
        "output": str(output_path),
        "size": list(cleaned.size),
        "chromaKey": f"#{key[0]:02x}{key[1]:02x}{key[2]:02x}",
        "chromaTolerance": chroma_tolerance,
        "alphaThreshold": alpha_threshold,
        "removeKeyFamily": remove_key_family,
        "removedVisibleKeyPixels": removed,
        "alphaBleedPixels": alpha_bleed_pixels,
        "before": {
            "alphaUniqueValues": sum(1 for count in before_alpha if count),
            "transparentPixels": before_alpha[0],
            "semiTransparentPixels": sum(before_alpha[1:255]),
            "opaquePixels": before_alpha[255],
            **before_hidden,
            **before_visible,
        },
        "after": {
            "alphaUniqueValues": sum(1 for count in after_alpha if count),
            "transparentPixels": after_alpha[0],
            "semiTransparentPixels": sum(after_alpha[1:255]),
            "opaquePixels": after_alpha[255],
            **after_hidden,
        },
        "warnings": [],
    }
    removed_ratio = removed / before_visible["visiblePixels"] if before_visible["visiblePixels"] else 0.0
    report["removedVisibleRatio"] = removed_ratio
    if report["before"]["alphaUniqueValues"] <= 2:
        report["warnings"].append("binary-alpha-edge")
    if before_hidden["nearKeyHiddenRgb"] or before_hidden["blackHiddenRgb"]:
        report["warnings"].append("hidden-rgb-contamination")
    if removed_ratio > max_visible_removal_ratio:
        report["warnings"].append("visible-subject-erosion")
        raise ValueError(
            "reference cleanup removed too much visible artwork "
            f"({removed_ratio:.2%}); choose a different chroma key"
        )
    return report


def main() -> None:
    args = parse_args()
    report = clean_reference(
        Path(args.input),
        Path(args.output),
        chroma_key=args.chroma_key,
        chroma_tolerance=args.chroma_tolerance,
        alpha_threshold=args.alpha_threshold,
        max_visible_removal_ratio=args.max_visible_removal_ratio,
        remove_key_family=args.remove_key_family,
    )
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
