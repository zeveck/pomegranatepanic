#!/usr/bin/env python3
"""Export an anim8gen package preview as an animated WebP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image

import export_gif
import make_preview
import render_options


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--frames", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--fps", type=float, help="Override spec render.fps")
    parser.add_argument("--scale", type=int, default=1, help="Export scale using the spec render.resampling mode")
    parser.add_argument("--quality", type=int, default=100, help="WebP quality for lossy output")
    parser.add_argument("--lossless", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def export_webp(
    spec: dict[str, Any],
    frames_dir: Path,
    out_path: Path,
    fps: float,
    scale: int,
    *,
    lossless: bool = True,
    quality: int = 100,
) -> None:
    if fps <= 0:
        raise ValueError("--fps must be greater than zero")
    if scale < 1:
        raise ValueError("--scale must be at least 1")
    if quality < 0 or quality > 100:
        raise ValueError("--quality must be between 0 and 100")

    canvas_size = tuple(spec["render"]["canvas"])
    if len(canvas_size) != 2:
        raise ValueError("spec render.canvas must contain width and height")

    preview = spec.get("preview", {})
    resampling = render_options.resolve_resampling(spec)
    rendered: list[Image.Image] = []
    for index in export_gif.playback_indexes(spec):
        frame = spec["frames"][index]
        source = frames_dir / make_preview.aligned_name(frame)
        if not source.exists():
            raise FileNotFoundError(f"missing aligned frame: {source}")
        rendered.append(export_gif.render_frame(source, canvas_size, make_preview.preview_offset(preview, frame), scale, resampling))

    if not rendered:
        raise ValueError("no frames to export")

    duration_ms = max(20, round(1000 / fps))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rendered[0].save(
        out_path,
        format="WEBP",
        save_all=True,
        append_images=rendered[1:],
        duration=duration_ms,
        loop=0,
        lossless=lossless,
        quality=quality,
        method=6,
    )


def main() -> None:
    args = parse_args()
    spec = json.loads(Path(args.spec).read_text())
    fps = args.fps if args.fps is not None else float(spec["render"].get("fps", 8))
    export_webp(
        spec,
        Path(args.frames),
        Path(args.out),
        fps,
        args.scale,
        lossless=args.lossless,
        quality=args.quality,
    )
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
