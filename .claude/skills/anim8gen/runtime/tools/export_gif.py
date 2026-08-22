#!/usr/bin/env python3
"""Export an anim8gen package preview as an animated GIF."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image

import make_preview
import render_options


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--frames", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--fps", type=float, help="Override spec render.fps")
    parser.add_argument("--scale", type=int, default=1, help="Export scale using the spec render.resampling mode")
    parser.add_argument(
        "--alpha-threshold",
        type=int,
        help="Alpha below this value is transparent in GIF output. Defaults to render.gifAlphaThreshold or 96.",
    )
    return parser.parse_args()


def playback_indexes(spec: dict[str, Any]) -> list[int]:
    return make_preview.build_payload_for_indexes(spec)


def render_frame(
    source: Path,
    canvas_size: tuple[int, int],
    offset: dict[str, Any],
    scale: int,
    resampling: str,
) -> Image.Image:
    source_image = Image.open(source).convert("RGBA")
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    canvas.alpha_composite(source_image, (round(offset["x"]), round(offset["y"])))
    if scale != 1:
        scaled_size = (canvas.width * scale, canvas.height * scale)
        canvas = render_options.resize_rgba(canvas, scaled_size, resampling)
    return canvas


def gif_alpha_threshold(spec: dict[str, Any], override: int | None = None) -> int:
    value = override if override is not None else spec.get("render", {}).get("gifAlphaThreshold", 96)
    if not isinstance(value, int):
        raise ValueError("render.gifAlphaThreshold must be an integer")
    if value < 0 or value > 255:
        raise ValueError("GIF alpha threshold must be between 0 and 255")
    return value


def prepare_gif_frame(image: Image.Image, alpha_threshold: int) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = []
    for red, green, blue, alpha in rgba.getdata():
        if alpha < alpha_threshold:
            pixels.append((red, green, blue, 0))
        else:
            pixels.append((red, green, blue, 255))
    prepared = Image.new("RGBA", rgba.size)
    prepared.putdata(pixels)
    return prepared


def export_gif(
    spec: dict[str, Any],
    frames_dir: Path,
    out_path: Path,
    fps: float,
    scale: int,
    alpha_threshold: int | None = None,
) -> None:
    if fps <= 0:
        raise ValueError("--fps must be greater than zero")
    if scale < 1:
        raise ValueError("--scale must be at least 1")

    canvas_size = tuple(spec["render"]["canvas"])
    if len(canvas_size) != 2:
        raise ValueError("spec render.canvas must contain width and height")

    preview = spec.get("preview", {})
    resampling = render_options.resolve_resampling(spec)
    threshold = gif_alpha_threshold(spec, alpha_threshold)
    rendered: list[Image.Image] = []
    for index in playback_indexes(spec):
        frame = spec["frames"][index]
        source = frames_dir / make_preview.aligned_name(frame)
        if not source.exists():
            raise FileNotFoundError(f"missing aligned frame: {source}")
        rgba = render_frame(source, canvas_size, make_preview.preview_offset(preview, frame), scale, resampling)
        rendered.append(prepare_gif_frame(rgba, threshold))

    if not rendered:
        raise ValueError("no frames to export")

    duration_ms = max(20, round(1000 / fps))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rendered[0].save(
        out_path,
        save_all=True,
        append_images=rendered[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,
        optimize=False,
    )


def main() -> None:
    args = parse_args()
    spec = json.loads(Path(args.spec).read_text())
    fps = args.fps if args.fps is not None else float(spec["render"].get("fps", 8))
    export_gif(spec, Path(args.frames), Path(args.out), fps, args.scale, args.alpha_threshold)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
