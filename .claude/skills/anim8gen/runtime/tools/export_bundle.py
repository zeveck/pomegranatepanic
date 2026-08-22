#!/usr/bin/env python3
"""Export visible anim8gen deliverables from a hidden run workspace."""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
from pathlib import Path
from typing import Any

from PIL import Image

import make_preview


def render_media_viewer(animation_id: str, media_src: str, label: str) -> str:
    title = f"{animation_id} {label}"
    escaped_title = html.escape(title)
    escaped_src = html.escape(media_src, quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    :root {{ color-scheme: light; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: #ffffff;
    }}
    img {{
      max-width: min(90vw, 768px);
      max-height: 90vh;
      width: auto;
      height: auto;
      image-rendering: auto;
    }}
  </style>
</head>
<body>
  <img src="{escaped_src}" alt="{escaped_title}">
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="Animation spec JSON.")
    parser.add_argument("--run-root", help="Hidden run root. Defaults to the spec parent package root.")
    parser.add_argument("--frames", help="Aligned frame directory. Defaults to <run-root>/aligned.")
    parser.add_argument("--validation", help="Validation JSON. Defaults to <run-root>/reports/<id>.validation.json.")
    parser.add_argument("--gif", help="GIF to export. Defaults to <run-root>/gifs/<id>.gif.")
    parser.add_argument("--webp", help="Animated WebP to export. Defaults to <run-root>/webp/<id>.webp when present.")
    parser.add_argument("--out", required=True, help="Visible export package directory.")
    parser.add_argument(
        "--raw",
        choices=["auto", "always", "never"],
        default="auto",
        help="Raw export policy. Default auto exports raw candidates only when they differ from final frames.",
    )
    parser.add_argument("--force", action="store_true", help="Remove an existing export directory before writing.")
    return parser.parse_args()


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def infer_run_root(spec_path: Path) -> Path:
    if spec_path.parent.name == "config":
        return spec_path.parent.parent
    return spec_path.parent


def accepted_raw_sources(spec: dict[str, Any], run_root: Path) -> dict[int, Path]:
    manifest_text = spec.get("generation", {}).get("acceptedManifest")
    manifest_path = Path(str(manifest_text)) if manifest_text else run_root / "manifests" / "accepted-frames.json"
    if manifest_text and not manifest_path.is_absolute():
        manifest_path = Path.cwd() / manifest_path
    if not manifest_path.exists():
        manifest_path = run_root / "manifests" / "accepted-frames.json"
    if not manifest_path.exists():
        return {}

    manifest = load_json(manifest_path, default={})
    sources: dict[int, Path] = {}
    for frame in manifest.get("frames", []):
        if not isinstance(frame, dict) or "index" not in frame or "raw" not in frame:
            continue
        source = Path(str(frame["raw"]))
        if not source.is_absolute():
            source = Path.cwd() / source
        sources[int(frame["index"])] = source
    return sources


def images_match(left: Path, right: Path) -> bool:
    if not left.exists() or not right.exists():
        return False
    try:
        with Image.open(left) as left_image, Image.open(right) as right_image:
            left_rgba = left_image.convert("RGBA")
            right_rgba = right_image.convert("RGBA")
            return left_rgba.size == right_rgba.size and list(left_rgba.getdata()) == list(right_rgba.getdata())
    except OSError:
        return False


def always_export_raw(policy: str) -> bool:
    flag = os.environ.get("ANIM8GEN_ALWAYS_EXPORT_RAW", "")
    return policy == "always" or flag.lower() in {"1", "true", "yes", "on"}


def export_raw_candidates(
    spec: dict[str, Any],
    frames_dir: Path,
    raw_sources: dict[int, Path],
    raw_out: Path,
    policy: str,
) -> int:
    if policy == "never":
        return 0

    selected: list[tuple[Path, Path]] = []
    forced = always_export_raw(policy)
    for frame in spec["frames"]:
        source = raw_sources.get(int(frame["index"]))
        if source is None or not source.exists():
            continue
        aligned = frames_dir / make_preview.aligned_name(frame)
        if forced or not images_match(source, aligned):
            selected.append((source, raw_out / make_preview.aligned_name(frame)))

    if not selected:
        return 0

    raw_out.mkdir(parents=True, exist_ok=True)
    for source, dest in selected:
        shutil.copy2(source, dest)
    return len(selected)


def export_bundle(
    spec_path: Path,
    out_dir: Path,
    *,
    run_root: Path | None = None,
    frames_dir: Path | None = None,
    validation_path: Path | None = None,
    gif_path: Path | None = None,
    webp_path: Path | None = None,
    raw_policy: str = "auto",
    force: bool = False,
) -> dict[str, Any]:
    spec = load_json(spec_path)
    animation_id = spec["id"]
    run_root = run_root or infer_run_root(spec_path)
    frames_dir = frames_dir or run_root / "aligned"
    validation_path = validation_path or run_root / "reports" / f"{animation_id}.validation.json"
    gif_path = gif_path or run_root / "gifs" / f"{animation_id}.gif"
    if not gif_path.exists():
        raise FileNotFoundError(f"missing GIF export: {gif_path}")
    webp_path = webp_path or run_root / "webp" / f"{animation_id}.webp"
    if not webp_path.exists():
        webp_path = None

    if force and out_dir.exists():
        shutil.rmtree(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()) and not force:
        raise FileExistsError(f"{out_dir} already exists and is not empty; pass --force to replace it")

    frames_out = out_dir / "frames"
    frames_out.mkdir(parents=True, exist_ok=True)
    for frame in spec["frames"]:
        src = frames_dir / make_preview.aligned_name(frame)
        if not src.exists():
            raise FileNotFoundError(f"missing aligned frame: {src}")
        shutil.copy2(src, frames_out / src.name)

    gif_out = out_dir / f"{animation_id}.gif"
    shutil.copy2(gif_path, gif_out)
    exported_gif = gif_out
    exported_webp: Path | None = None
    if webp_path is not None:
        webp_out = out_dir / f"{animation_id}.webp"
        shutil.copy2(webp_path, webp_out)
        exported_webp = webp_out

    gif_viewer = out_dir / f"{animation_id}.gif.html"
    gif_viewer.write_text(render_media_viewer(animation_id, gif_out.name, "GIF"), encoding="utf-8")
    webp_viewer: Path | None = None
    if exported_webp is not None:
        webp_viewer = out_dir / f"{animation_id}.webp.html"
        webp_viewer.write_text(render_media_viewer(animation_id, exported_webp.name, "WebP"), encoding="utf-8")

    validation = load_json(validation_path, default={"frames": []})
    preview_out = out_dir / "preview.html"
    payload = make_preview.build_payload(
        spec,
        validation,
        frames_out,
        preview_out,
        exported_gif,
        exported_webp,
        gif_viewer,
        webp_viewer,
    )
    preview_out.write_text(make_preview.render_html(payload), encoding="utf-8")

    raw_count = export_raw_candidates(
        spec,
        frames_dir,
        accepted_raw_sources(spec, run_root),
        out_dir / "raw",
        raw_policy,
    )

    return {
        "id": animation_id,
        "export": str(out_dir),
        "frames": len(spec["frames"]),
        "preview": str(preview_out),
        "gif": str(exported_gif) if exported_gif else None,
        "webp": str(exported_webp) if exported_webp else None,
        "gifViewer": str(gif_viewer),
        "webpViewer": str(webp_viewer) if webp_viewer else None,
        "rawFrames": raw_count,
    }


def main() -> None:
    args = parse_args()
    result = export_bundle(
        Path(args.spec),
        Path(args.out),
        run_root=Path(args.run_root) if args.run_root else None,
        frames_dir=Path(args.frames) if args.frames else None,
        validation_path=Path(args.validation) if args.validation else None,
        gif_path=Path(args.gif) if args.gif else None,
        webp_path=Path(args.webp) if args.webp else None,
        raw_policy=args.raw,
        force=args.force,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
