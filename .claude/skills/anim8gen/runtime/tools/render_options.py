"""Shared rendering options for anim8gen runtime tools."""

from __future__ import annotations

from collections import deque
from typing import Any

from PIL import Image, ImageFilter


PIXEL_STYLE_TERMS = ("pixel", "8-bit", "16-bit", "32-bit", "crisp", "low-res", "low res", "vector")
SMOOTH_STYLE_TERMS = ("watercolor", "storybook", "painted", "hand-painted", "painterly", "soft", "pastel")


def style_text(spec: dict[str, Any]) -> str:
    return str(spec.get("asset", {}).get("style", "")).lower()


def style_prefers_smooth(spec: dict[str, Any]) -> bool:
    text = style_text(spec)
    if any(term in text for term in PIXEL_STYLE_TERMS):
        return False
    return any(term in text for term in SMOOTH_STYLE_TERMS)


def resolve_resampling(spec: dict[str, Any]) -> str:
    value = str(spec.get("render", {}).get("resampling", "auto")).lower()
    if value not in {"auto", "nearest", "lanczos"}:
        raise ValueError("render.resampling must be one of auto, nearest, lanczos")
    if value != "auto":
        return value
    return "lanczos" if style_prefers_smooth(spec) else "nearest"


def resampling_filter(name: str) -> Image.Resampling:
    return Image.Resampling.LANCZOS if name == "lanczos" else Image.Resampling.NEAREST


def resolve_edge_treatment(spec: dict[str, Any]) -> str:
    value = str(spec.get("render", {}).get("edgeTreatment", "auto")).lower()
    if value not in {"auto", "hard", "soft"}:
        raise ValueError("render.edgeTreatment must be one of auto, hard, soft")
    if value != "auto":
        return value
    return "soft" if style_prefers_smooth(spec) else "hard"


def alpha_level_count(image: Image.Image) -> int:
    return sum(1 for count in image.getchannel("A").histogram() if count)


def alpha_bleed_transparent_rgb(image: Image.Image) -> int:
    width, height = image.size
    pixels = image.load()
    nearest: list[list[tuple[int, int] | None]] = [[None for _x in range(width)] for _y in range(height)]
    queue: deque[tuple[int, int]] = deque()
    for y in range(height):
        for x in range(width):
            if pixels[x, y][3] > 0:
                nearest[y][x] = (x, y)
                queue.append((x, y))

    if not queue or len(queue) == width * height:
        return 0

    while queue:
        x, y = queue.popleft()
        source = nearest[y][x]
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if nx < 0 or ny < 0 or nx >= width or ny >= height or nearest[ny][nx] is not None:
                continue
            nearest[ny][nx] = source
            queue.append((nx, ny))

    changed = 0
    for y in range(height):
        for x in range(width):
            if pixels[x, y][3] != 0:
                continue
            source = nearest[y][x]
            if source is None:
                continue
            sx, sy = source
            red, green, blue, _alpha = pixels[sx, sy]
            pixels[x, y] = (red, green, blue, 0)
            changed += 1
    return changed


def resize_rgba(image: Image.Image, size: tuple[int, int], resampling: str) -> Image.Image:
    if resampling == "nearest":
        return image.resize(size, Image.Resampling.NEAREST)

    source = image.convert("RGBA")
    alpha_bleed_transparent_rgb(source)
    premultiplied = []
    for red, green, blue, alpha in source.getdata():
        premultiplied.append((
            round(red * alpha / 255),
            round(green * alpha / 255),
            round(blue * alpha / 255),
            alpha,
        ))
    premul = Image.new("RGBA", source.size)
    premul.putdata(premultiplied)
    resized = premul.resize(size, resampling_filter(resampling))
    unpremultiplied = []
    for red, green, blue, alpha in resized.getdata():
        if alpha == 0:
            unpremultiplied.append((0, 0, 0, 0))
        else:
            unpremultiplied.append((
                min(255, round(red * 255 / alpha)),
                min(255, round(green * 255 / alpha)),
                min(255, round(blue * 255 / alpha)),
                alpha,
            ))
    out = Image.new("RGBA", size)
    out.putdata(unpremultiplied)
    alpha_bleed_transparent_rgb(out)
    return out


def soften_sprite_edges(image: Image.Image, edge_treatment: str) -> dict[str, Any]:
    before_levels = alpha_level_count(image)
    if edge_treatment != "soft" or before_levels > 2:
        return {
            "edgeTreatment": edge_treatment,
            "alphaLevelsBefore": before_levels,
            "alphaLevelsAfter": before_levels,
            "softenedPixels": 0,
            "alphaBleedPixels": 0,
        }

    alpha = image.getchannel("A")
    if alpha.getbbox() is None:
        return {
            "edgeTreatment": edge_treatment,
            "alphaLevelsBefore": before_levels,
            "alphaLevelsAfter": before_levels,
            "softenedPixels": 0,
            "alphaBleedPixels": 0,
        }

    alpha_bleed_pixels = alpha_bleed_transparent_rgb(image)
    blurred = alpha.filter(ImageFilter.GaussianBlur(radius=0.65))
    original_pixels = list(alpha.getdata())
    blurred_pixels = list(blurred.getdata())
    softened_alpha = []
    softened_pixels = 0
    for original, blurred_value in zip(original_pixels, blurred_pixels):
        value = min(original, blurred_value) if original > 0 else 0
        if value != original:
            softened_pixels += 1
        softened_alpha.append(value)
    alpha.putdata(softened_alpha)
    image.putalpha(alpha)
    return {
        "edgeTreatment": edge_treatment,
        "alphaLevelsBefore": before_levels,
        "alphaLevelsAfter": alpha_level_count(image),
        "softenedPixels": softened_pixels,
        "alphaBleedPixels": alpha_bleed_pixels,
    }
