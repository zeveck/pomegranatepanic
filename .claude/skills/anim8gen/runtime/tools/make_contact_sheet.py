#!/usr/bin/env python3
"""Build a sprite review contact sheet from raw, aligned, and validation data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CANVAS_BG = (34, 34, 38, 255)
PANEL_BG = (246, 246, 242, 255)
GRID_LIGHT = (220, 220, 220, 255)
GRID_DARK = (184, 184, 184, 255)
TEXT = (24, 24, 28, 255)
MUTED = (88, 88, 96, 255)
WARNING = (210, 40, 40, 255)
FLOOR = (42, 130, 210, 255)
ANCHOR = (34, 160, 85, 255)
BBOX = (244, 156, 40, 255)
PREV = (220, 44, 44, 92)
NEXT = (36, 92, 220, 92)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--raw", required=True)
    parser.add_argument("--aligned", required=True)
    parser.add_argument("--validation", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def aligned_name(frame: dict[str, Any]) -> str:
    return f"frame-{frame['index']:03d}.{frame['label']}.png"


def raw_path(raw_dir: Path, frame: dict[str, Any]) -> Path:
    matches = sorted(raw_dir.glob(f"frame-{frame['index']:03d}.retry-*.png"))
    if not matches:
        raise FileNotFoundError(f"missing raw frame for index {frame['index']}")
    return matches[0]


def accepted_sources(spec: dict[str, Any]) -> dict[int, Path]:
    manifest_path = spec.get("generation", {}).get("acceptedManifest")
    if not manifest_path:
        return {}
    path = Path(manifest_path)
    if not path.exists():
        return {}
    manifest = json.loads(path.read_text())
    sources: dict[int, Path] = {}
    for frame in manifest.get("frames", []):
        raw = frame.get("raw")
        if raw:
            sources[int(frame["index"])] = Path(raw)
    return sources


def load_font() -> ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, 13)
    return ImageFont.load_default()


def checkerboard(size: tuple[int, int], square: int = 8) -> Image.Image:
    image = Image.new("RGBA", size, GRID_LIGHT)
    draw = ImageDraw.Draw(image)
    width, height = size
    for y in range(0, height, square):
        for x in range(0, width, square):
            if (x // square + y // square) % 2:
                draw.rectangle((x, y, x + square - 1, y + square - 1), fill=GRID_DARK)
    return image


def fit_image(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    fitted = image.copy()
    fitted.thumbnail(size, Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", size, PANEL_BG)
    offset = ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2)
    canvas.alpha_composite(fitted.convert("RGBA"), offset)
    return canvas


def warning_index(validation: dict[str, Any]) -> dict[int, list[str]]:
    by_frame: dict[int, list[str]] = {}
    for comparison in validation.get("comparisons", []):
        warnings = comparison.get("warnings", [])
        if not warnings:
            continue
        label = f"{comparison['from']:03d}->{comparison['to']:03d}: {len(warnings)}"
        for index in (comparison["from"], comparison["to"]):
            by_frame.setdefault(index, []).append(label)
    for failure in validation.get("structuralFailures", []):
        by_frame.setdefault(failure["index"], []).append("structural")
    return by_frame


def frame_stats(validation: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {frame["index"]: frame for frame in validation.get("frames", [])}


def overlay_aligned(
    image: Image.Image,
    stats: dict[str, Any],
    floor_y: int,
    warnings: list[str],
    scale: int,
) -> Image.Image:
    base = checkerboard(image.size)
    base.alpha_composite(image.convert("RGBA"), (0, 0))
    draw = ImageDraw.Draw(base)
    draw.line((0, floor_y, image.width, floor_y), fill=FLOOR, width=1)

    bbox = stats.get("bbox")
    if bbox:
        draw.rectangle(tuple(bbox), outline=BBOX, width=1)
    anchor = stats.get("anchor")
    if anchor:
        x, y = round(anchor[0]), round(anchor[1])
        draw.line((x - 4, y, x + 4, y), fill=ANCHOR, width=1)
        draw.line((x, y - 4, x, y + 4), fill=ANCHOR, width=1)

    if warnings:
        draw.ellipse((4, 4, 22, 22), fill=WARNING)
        draw.text((10, 5), str(len(warnings)), anchor="ma", fill=(255, 255, 255, 255))

    return base.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)


def tint_mask(image: Image.Image, color: tuple[int, int, int, int]) -> Image.Image:
    alpha = image.getchannel("A")
    tinted = Image.new("RGBA", image.size, color)
    tinted.putalpha(alpha.point(lambda value: min(value, color[3])))
    return tinted


def onion_skin(images: list[Image.Image], index: int, scale: int) -> Image.Image:
    size = images[index].size
    base = checkerboard(size)
    if index > 0:
        base.alpha_composite(tint_mask(images[index - 1], PREV), (0, 0))
    base.alpha_composite(images[index].convert("RGBA"), (0, 0))
    if index + 1 < len(images):
        base.alpha_composite(tint_mask(images[index + 1], NEXT), (0, 0))
    return base.resize((size[0] * scale, size[1] * scale), Image.Resampling.NEAREST)


def draw_label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font: ImageFont.ImageFont, fill: tuple[int, int, int, int] = TEXT) -> None:
    draw.text(xy, text, fill=fill, font=font)


def main() -> None:
    args = parse_args()
    spec = json.loads(Path(args.spec).read_text())
    validation = json.loads(Path(args.validation).read_text())
    raw_dir = Path(args.raw)
    aligned_dir = Path(args.aligned)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    frames = list(spec["frames"])
    accepted = accepted_sources(spec)
    scale = 2
    cell = (spec["render"]["canvas"][0] * scale, spec["render"]["canvas"][1] * scale)
    gap = 18
    label_h = 44
    row_label_w = 116
    margin = 24
    rows = [("Raw", "raw candidates"), ("Aligned", "bbox, anchor, floor, warnings"), ("Onion", "previous red, next blue")]
    width = margin * 2 + row_label_w + len(frames) * cell[0] + (len(frames) - 1) * gap
    height = margin * 2 + label_h + len(rows) * cell[1] + (len(rows) - 1) * 42

    sheet = Image.new("RGBA", (width, height), CANVAS_BG)
    draw = ImageDraw.Draw(sheet)
    font = load_font()
    title_font = font
    draw_label(draw, (margin, margin), f"{spec['id']} review contact sheet", title_font, (255, 255, 255, 255))
    summary = validation.get("summary", {})
    draw_label(
        draw,
        (margin, margin + 18),
        f"{summary.get('frameCount', len(frames))} frames, {summary.get('warningCount', 0)} validation warnings",
        font,
        (210, 210, 214, 255),
    )

    warnings_by_frame = warning_index(validation)
    stats_by_frame = frame_stats(validation)
    floor_y = spec["alignment"]["floorY"]
    aligned_images = [Image.open(aligned_dir / aligned_name(frame)).convert("RGBA") for frame in frames]

    y = margin + label_h
    for row_index, (row_title, row_hint) in enumerate(rows):
        draw_label(draw, (margin, y + 6), row_title, font, (255, 255, 255, 255))
        draw_label(draw, (margin, y + 24), row_hint, font, (190, 190, 196, 255))
        x = margin + row_label_w
        for frame_index, frame in enumerate(frames):
            draw.rectangle((x - 1, y - 1, x + cell[0], y + cell[1]), fill=PANEL_BG)
            if row_index == 0:
                source = accepted.get(frame["index"])
                if source is None:
                    source = raw_path(raw_dir, frame)
                tile = fit_image(Image.open(source).convert("RGBA"), cell)
            elif row_index == 1:
                tile = overlay_aligned(
                    aligned_images[frame_index],
                    stats_by_frame.get(frame["index"], {}),
                    floor_y,
                    warnings_by_frame.get(frame["index"], []),
                    scale,
                )
            else:
                tile = onion_skin(aligned_images, frame_index, scale)
            sheet.alpha_composite(tile, (x, y))
            if row_index == 0:
                draw_label(draw, (x, y + cell[1] + 4), f"{frame['index']:03d} {frame['label']}", font, (230, 230, 234, 255))
            x += cell[0] + gap
        y += cell[1] + 42

    legend_y = height - margin + 2
    draw.rectangle((margin, legend_y - 6, margin + 10, legend_y + 4), outline=BBOX)
    draw_label(draw, (margin + 16, legend_y - 10), "bbox", font, MUTED)
    draw.line((margin + 70, legend_y - 1, margin + 100, legend_y - 1), fill=FLOOR, width=2)
    draw_label(draw, (margin + 106, legend_y - 10), "floor", font, MUTED)
    draw.line((margin + 168, legend_y - 1, margin + 190, legend_y - 1), fill=ANCHOR, width=2)
    draw_label(draw, (margin + 196, legend_y - 10), "anchor", font, MUTED)
    draw.ellipse((margin + 268, legend_y - 8, margin + 282, legend_y + 6), fill=WARNING)
    draw_label(draw, (margin + 290, legend_y - 10), "warning marker", font, MUTED)

    sheet.convert("RGB").save(out_path)
    print(f"wrote contact sheet to {out_path}")


if __name__ == "__main__":
    main()
