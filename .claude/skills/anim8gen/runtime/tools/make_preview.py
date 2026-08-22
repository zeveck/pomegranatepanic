#!/usr/bin/env python3
"""Generate a local HTML preview for aligned sprite frames."""

from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
from typing import Any

import render_options


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--frames", required=True)
    parser.add_argument("--validation", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def aligned_name(frame: dict[str, Any]) -> str:
    return f"frame-{frame['index']:03d}.{frame['label']}.png"


def relative_src(path: Path, out_path: Path) -> str:
    return Path(os.path.relpath(path.resolve(), out_path.parent.resolve())).as_posix()


def preview_offset(preview: dict[str, Any], frame: dict[str, Any]) -> dict[str, Any]:
    offsets = preview.get("displayOffsets", {})
    if not isinstance(offsets, dict):
        raise ValueError("preview.displayOffsets must be an object when provided")

    raw = offsets.get(str(frame["index"]), offsets.get(frame["label"], {}))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError(f"preview display offset for frame {frame['index']} must be an object")

    x = raw.get("x", 0)
    y = raw.get("y", 0)
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        raise ValueError(f"preview display offset for frame {frame['index']} must use numeric x and y")

    offset: dict[str, Any] = {"x": x, "y": y}
    if raw.get("reason"):
        offset["reason"] = str(raw["reason"])
    return offset


def build_payload_for_indexes(spec: dict[str, Any]) -> list[int]:
    frames = spec["frames"]
    indexes = list(range(len(frames)))
    preview = spec.get("preview", {})
    play_terminal_reuse = preview.get("playTerminalReuseFrame")
    if play_terminal_reuse is None:
        play_terminal_reuse = False
    if not play_terminal_reuse and len(frames) > 2 and frames[-1].get("reuseFrame") == frames[0]["index"]:
        indexes = indexes[:-1]
    return indexes


def build_payload(
    spec: dict[str, Any],
    validation: dict[str, Any],
    frames_dir: Path,
    out_path: Path,
    gif_path: Path | None = None,
    webp_path: Path | None = None,
    gif_href: Path | None = None,
    webp_href: Path | None = None,
) -> dict[str, Any]:
    preview = spec.get("preview", {})
    frames = []
    for frame in spec["frames"]:
        path = frames_dir / aligned_name(frame)
        if not path.exists():
            raise FileNotFoundError(f"missing aligned frame: {path}")
        frames.append(
            {
                "index": frame["index"],
                "label": frame["label"],
                "pose": frame.get("pose", ""),
                "reuseFrame": frame.get("reuseFrame"),
                "sleep": "sleep" in frame["label"] or "eyes closed" in frame.get("pose", ""),
                "displayOffset": preview_offset(preview, frame),
                "src": relative_src(path, out_path),
            }
        )
    payload = {
        "id": spec["id"],
        "canvas": spec["render"]["canvas"],
        "fps": spec["render"].get("fps", 8),
        "resampling": render_options.resolve_resampling(spec),
        "playbackIndexes": build_payload_for_indexes(spec),
        "previewStrategy": preview.get("strategy", "canvas-playback"),
        "runtimeEffects": preview.get("runtimeEffects", []),
        "frames": frames,
    }
    if gif_path is not None:
        payload["gifSrc"] = relative_src(gif_path, out_path)
        payload["gifHref"] = relative_src(gif_href or gif_path, out_path)
    if webp_path is not None:
        payload["webpSrc"] = relative_src(webp_path, out_path)
        payload["webpHref"] = relative_src(webp_href or webp_path, out_path)
    return payload


def render_html(payload: dict[str, Any]) -> str:
    payload_json = json.dumps(payload, separators=(",", ":"))
    title = html.escape(f"{payload['id']} preview")
    image_rendering_css = ""
    if payload.get("resampling") != "lanczos":
        image_rendering_css = """
      image-rendering: pixelated;
      image-rendering: crisp-edges;"""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1d1d22;
      --muted: #66666f;
      --panel: #f6f4ee;
      --line: #cbc8bd;
      --accent: #2776b8;
      --warn: #c94a36;
      --checker-a: #d9d9d9;
      --checker-b: #f5f5f5;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: #ece8dc;
      color: var(--ink);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      width: min(1120px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 24px 0 32px;
    }}
    header {{
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 12px;
    }}
    h1 {{
      margin: 0;
      font-size: 22px;
      line-height: 1.15;
      font-weight: 700;
      letter-spacing: 0;
    }}
    .meta {{
      color: var(--muted);
      font-size: 13px;
      text-align: right;
    }}
    .stage-row {{
      display: grid;
      grid-template-columns: minmax(560px, 1fr) 300px;
      gap: 20px;
      align-items: start;
    }}
    .side {{
      display: grid;
      gap: 12px;
      grid-template-rows: 430px 176px auto;
      align-items: start;
    }}
    .stage {{
      position: relative;
      height: 618px;
      padding: 20px;
      display: grid;
      place-items: center;
      border: 1px solid var(--line);
      background-color: var(--checker-b);
      background-image:
        linear-gradient(45deg, var(--checker-a) 25%, transparent 25%),
        linear-gradient(-45deg, var(--checker-a) 25%, transparent 25%),
        linear-gradient(45deg, transparent 75%, var(--checker-a) 75%),
        linear-gradient(-45deg, transparent 75%, var(--checker-a) 75%);
      background-size: 24px 24px;
      background-position: 0 0, 0 12px, 12px -12px, -12px 0;
      overflow: hidden;
    }}
    .mini {{
      position: relative;
      display: grid;
      gap: 6px;
      justify-items: center;
      align-content: center;
      height: 176px;
      padding: 8px;
      border: 1px solid var(--line);
      background: #fffdf8;
    }}
    .mini-asset-link {{
      position: absolute;
      right: 8px;
      bottom: 7px;
      color: var(--muted);
      text-decoration: none;
      font-size: 11px;
      font-weight: 650;
      line-height: 1;
    }}
    .mini-asset-link:hover {{ color: var(--accent); }}
    .mini-asset-link[hidden] {{ display: none; }}
    .mini-asset-link.webp {{
      right: 36px;
    }}
    .mini canvas {{
      width: min(128px, 100%);
      height: auto;
      max-height: 128px;
      aspect-ratio: var(--canvas-aspect);
    }}
    .mini-label {{
      color: var(--muted);
      font-size: 11px;
      line-height: 1;
    }}
    .stage.plain {{
      background: #f4f0e6;
    }}
    canvas {{
      width: var(--display-width, auto);
      height: var(--display-height, auto);
      max-width: 100%;
      max-height: 100%;
      aspect-ratio: var(--canvas-aspect);{image_rendering_css}
    }}
    .zs {{
      position: absolute;
      left: 50%;
      top: 39%;
      width: 160px;
      height: 140px;
      pointer-events: none;
      transform: translate(-4%, -50%);
      opacity: 0;
    }}
    .zs.active {{
      opacity: 1;
    }}
    .z {{
      position: absolute;
      color: #5b6db7;
      font-family: Georgia, "Times New Roman", serif;
      font-weight: 700;
      text-shadow: 0 2px 0 rgba(255, 255, 255, 0.75);
      animation: drift 1600ms linear infinite;
    }}
    .z:nth-child(1) {{ left: 18px; bottom: 12px; font-size: 22px; animation-delay: 0ms; }}
    .z:nth-child(2) {{ left: 60px; bottom: 44px; font-size: 28px; animation-delay: 260ms; }}
    .z:nth-child(3) {{ left: 106px; bottom: 82px; font-size: 36px; animation-delay: 520ms; }}
    @keyframes drift {{
      from {{ transform: translateY(16px); opacity: 0; }}
      20% {{ opacity: 1; }}
      78% {{ opacity: 1; }}
      to {{ transform: translateY(-26px); opacity: 0; }}
    }}
    .controls {{
      display: grid;
      gap: 12px;
      border: 1px solid var(--line);
      background: var(--panel);
      padding: 14px;
      height: 430px;
      align-content: start;
      overflow: hidden;
    }}
    .buttons {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
    }}
    button {{
      min-height: 38px;
      border: 1px solid #a8a496;
      background: #fffdf8;
      color: var(--ink);
      font: inherit;
      font-weight: 650;
      cursor: pointer;
    }}
    button:hover {{ border-color: var(--accent); }}
    label {{
      display: grid;
      gap: 6px;
      font-size: 13px;
      color: var(--muted);
    }}
    input[type="range"] {{ width: 100%; }}
    .fps-row {{
      position: relative;
      display: grid;
      gap: 6px;
    }}
    .fps-readout {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
    }}
    .mini-button {{
      min-height: 24px;
      padding: 0 8px;
      font-size: 12px;
      font-weight: 650;
    }}
    .toggles {{
      display: grid;
      gap: 8px;
    }}
    .toggle[hidden] {{
      display: none;
    }}
    .toggle {{
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--ink);
    }}
    .frame-card {{
      border-top: 1px solid var(--line);
      padding-top: 12px;
      display: grid;
      gap: 4px;
    }}
    .frame-label {{
      font-size: 18px;
      font-weight: 700;
    }}
    .pose {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.35;
      height: 54px;
      overflow: auto;
    }}
    .strip {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(42px, 1fr));
      gap: 6px;
    }}
    .thumb {{
      border: 2px solid transparent;
      background: #fffdf8;
      padding: 2px;
      cursor: pointer;
    }}
    .thumb.active {{ border-color: var(--accent); }}
    .thumb img {{
      display: block;
      width: 100%;
      aspect-ratio: 1 / 1;
      object-fit: contain;{image_rendering_css}
    }}
    @media (max-width: 760px) {{
      .stage-row {{ grid-template-columns: 1fr; }}
      .stage {{ height: min(520px, calc(100vw - 32px)); }}
      .side {{ grid-template-rows: auto; }}
      .controls {{ height: auto; }}
      header {{ align-items: start; flex-direction: column; }}
      .meta {{ text-align: left; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{html.escape(payload["id"])}</h1>
      <div class="meta">
        <div id="meta"></div>
      </div>
    </header>
    <div class="stage-row">
      <section class="stage" id="stage" aria-label="Sprite preview stage" style="--canvas-aspect: {payload["canvas"][0]} / {payload["canvas"][1]}">
        <canvas id="sprite" width="{payload["canvas"][0]}" height="{payload["canvas"][1]}"></canvas>
        <div class="zs" id="zs" aria-hidden="true"><span class="z">Z</span><span class="z">Z</span><span class="z">Z</span></div>
      </section>
      <div class="side">
        <section class="controls" aria-label="Playback controls">
          <div class="buttons">
            <button type="button" id="prev" title="Previous frame">Prev</button>
            <button type="button" id="play" title="Play or pause">Pause</button>
            <button type="button" id="next" title="Next frame">Next</button>
          </div>
          <label class="fps-row">FPS
            <input type="range" id="fps" min="1" max="16" step="1">
            <span class="fps-readout"><span id="fpsValue"></span><button class="mini-button" type="button" id="specFpsButton"></button></span>
          </label>
          <div class="toggles">
            <label class="toggle"><input type="checkbox" id="checker" checked> Checkerboard</label>
            <label class="toggle"><input type="checkbox" id="zToggle" checked> Sleeping Zs</label>
          </div>
          <div class="frame-card">
            <div class="frame-label" id="frameLabel"></div>
            <div class="pose" id="pose"></div>
          </div>
          <div class="strip" id="strip"></div>
        </section>
        <div class="mini" aria-label="Spec speed preview">
          <canvas id="miniSprite" width="{payload["canvas"][0]}" height="{payload["canvas"][1]}"></canvas>
          <a class="mini-asset-link webp" id="miniWebpLink" href="" hidden>WebP</a>
          <a class="mini-asset-link" id="miniGifLink" href="" hidden>GIF</a>
        </div>
      </div>
    </div>
  </main>
  <script>
    const payload = {payload_json};
    const canvas = document.getElementById("sprite");
    const ctx = canvas.getContext("2d");
    const miniCanvas = document.getElementById("miniSprite");
    const miniCtx = miniCanvas.getContext("2d");
    const stage = document.getElementById("stage");
    const zs = document.getElementById("zs");
    const frameLabel = document.getElementById("frameLabel");
    const pose = document.getElementById("pose");
    const playButton = document.getElementById("play");
    const fpsInput = document.getElementById("fps");
    const fpsValue = document.getElementById("fpsValue");
    const specFpsButton = document.getElementById("specFpsButton");
    const checkerInput = document.getElementById("checker");
    const zToggle = document.getElementById("zToggle");
    const meta = document.getElementById("meta");
    const miniWebpLink = document.getElementById("miniWebpLink");
    const miniGifLink = document.getElementById("miniGifLink");
    const strip = document.getElementById("strip");
    const images = [];
    let frameIndex = 0;
    let playbackPosition = 0;
    let miniPlaybackPosition = 0;
    let playing = true;
    let lastTime = 0;
    let miniLastTime = 0;

    ctx.imageSmoothingEnabled = payload.resampling === "lanczos";
    miniCtx.imageSmoothingEnabled = payload.resampling === "lanczos";
    fpsInput.value = fpsInput.min || 1;
    meta.textContent = `${{payload.frames.length}} frames`;
    if (payload.webpSrc) {{
      miniWebpLink.href = payload.webpHref || payload.webpSrc;
      miniWebpLink.hidden = false;
    }}
    if (payload.gifSrc) {{
      miniGifLink.href = payload.gifHref || payload.gifSrc;
      miniGifLink.hidden = false;
    }}

    function updateFpsUi() {{
      const min = Number(fpsInput.min || 1);
      const max = Number(fpsInput.max || 16);
      const spec = Math.min(max, Math.max(min, Number(payload.fps || min)));
      fpsValue.textContent = `${{fpsInput.value}} FPS`;
      specFpsButton.textContent = "Default";
    }}

    function loadImages() {{
      return Promise.all(payload.frames.map((frame, index) => new Promise((resolve, reject) => {{
        const img = new Image();
        img.onload = () => {{
          images[index] = img;
          resolve();
        }};
        img.onerror = reject;
        img.src = frame.src;
      }})));
    }}

    function renderStrip() {{
      strip.innerHTML = "";
      payload.frames.forEach((frame, index) => {{
        const button = document.createElement("button");
        button.type = "button";
        button.className = "thumb";
        button.title = `${{frame.index}} ${{frame.label}}`;
        const img = document.createElement("img");
        img.alt = frame.label;
        img.src = frame.src;
        button.appendChild(img);
        button.addEventListener("click", () => {{
          frameIndex = index;
          playbackPosition = Math.max(0, payload.playbackIndexes.indexOf(index));
          render();
        }});
        strip.appendChild(button);
      }});
    }}

    function render() {{
      const frame = payload.frames[frameIndex];
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(images[frameIndex], frame.displayOffset.x, frame.displayOffset.y);
      frameLabel.textContent = `${{String(frame.index).padStart(3, "0")}} ${{frame.label}}`;
      pose.textContent = frame.pose;
      zs.classList.toggle("active", hasSleepingZs && zToggle.checked && frame.sleep);
      [...strip.children].forEach((child, index) => child.classList.toggle("active", index === frameIndex));
    }}

    function sizeStageCanvas() {{
      const stageBox = stage.getBoundingClientRect();
      const stageStyle = getComputedStyle(stage);
      const availableWidth = stageBox.width - Number.parseFloat(stageStyle.paddingLeft) - Number.parseFloat(stageStyle.paddingRight);
      const availableHeight = stageBox.height - Number.parseFloat(stageStyle.paddingTop) - Number.parseFloat(stageStyle.paddingBottom);
      const ratio = Number(payload.canvas[0]) / Number(payload.canvas[1]);
      let width = availableWidth;
      let height = width / ratio;
      if (height > availableHeight) {{
        height = availableHeight;
        width = height * ratio;
      }}
      const displayWidth = `${{Math.max(1, Math.floor(width))}}px`;
      const displayHeight = `${{Math.max(1, Math.floor(height))}}px`;
      canvas.style.setProperty("--display-width", displayWidth);
      canvas.style.setProperty("--display-height", displayHeight);
    }}

    function renderMini() {{
      const index = payload.playbackIndexes[miniPlaybackPosition] ?? 0;
      const frame = payload.frames[index];
      miniCtx.clearRect(0, 0, miniCanvas.width, miniCanvas.height);
      miniCtx.imageSmoothingEnabled = false;
      miniCtx.drawImage(images[index], frame.displayOffset.x, frame.displayOffset.y);
    }}

    function step(delta) {{
      playbackPosition = (playbackPosition + delta + payload.playbackIndexes.length) % payload.playbackIndexes.length;
      frameIndex = payload.playbackIndexes[playbackPosition];
      render();
    }}

    function tick(time) {{
      const interval = 1000 / Number(fpsInput.value || payload.fps);
      if (playing && time - lastTime >= interval) {{
        step(1);
        lastTime = time;
      }}
      const miniInterval = 1000 / Number(payload.fps || 8);
      if (time - miniLastTime >= miniInterval) {{
        miniPlaybackPosition = (miniPlaybackPosition + 1) % payload.playbackIndexes.length;
        renderMini();
        miniLastTime = time;
      }}
      requestAnimationFrame(tick);
    }}

    document.getElementById("prev").addEventListener("click", () => step(-1));
    document.getElementById("next").addEventListener("click", () => step(1));
    playButton.addEventListener("click", () => {{
      playing = !playing;
      playButton.textContent = playing ? "Pause" : "Play";
    }});
    checkerInput.addEventListener("change", () => stage.classList.toggle("plain", !checkerInput.checked));
    zToggle.addEventListener("change", render);
    fpsInput.addEventListener("input", updateFpsUi);
    specFpsButton.addEventListener("click", () => {{
      fpsInput.value = String(payload.fps || 1);
      updateFpsUi();
    }});
    window.addEventListener("resize", () => {{
      updateFpsUi();
      sizeStageCanvas();
    }});
    const hasSleepingZs = payload.runtimeEffects.includes("sleeping-zs");
    zToggle.closest(".toggle").hidden = !hasSleepingZs;

    loadImages().then(() => {{
      renderStrip();
      updateFpsUi();
      sizeStageCanvas();
      render();
      renderMini();
      requestAnimationFrame(tick);
    }}).catch((error) => {{
      frameLabel.textContent = "Preview failed to load";
      pose.textContent = String(error);
    }});
  </script>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    spec_path = Path(args.spec)
    validation_path = Path(args.validation)
    out_path = Path(args.out)
    spec = json.loads(spec_path.read_text())
    validation = json.loads(validation_path.read_text())
    payload = build_payload(spec, validation, Path(args.frames), out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_html(payload), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
