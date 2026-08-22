# ImageGen2 Reference

Supplementary style presets, prompt templates, and practical guidance for the
`imagegen2` skill.

## Model Notes

`imagegen2` defaults to OpenAI `gpt-image-2`.

Strengths:

- high-quality image generation and editing
- flexible image sizes up to 4K-class outputs
- high-fidelity image inputs by default
- stronger text rendering and instruction following than older image models

Limitations:

- `gpt-image-2` does not currently support native transparent backgrounds
- exact layout and composition are not deterministic
- recurring character and brand consistency can drift across generations
- precise in-image text may still need retries
- complex prompts can take up to about 2 minutes

Use `--transparent-mode chroma-key` for PNG sprite workflows that should keep
`gpt-image-2` generation quality. That path requests an opaque solid key-color
background from `gpt-image-2`, locally removes matching pixels, alpha-bleeds
transparent RGB, and can suppress strongly key-colored visible edge pixels
when clean nearby subject colors are available. Disclose that the transparency
comes from local chroma-key cleanup, not native model alpha.

Use `--transparent-mode fallback-model` only when true native alpha output is
required. That path uses `gpt-image-1.5` explicitly and should be disclosed to
the user.

Native `gpt-image-2` transparent-background behavior was probed on 2026-05-03.
The API returned HTTP 400: "Transparent background is not supported for this
model."

## Style Presets

Adapt these as starting points. Do not paste a preset blindly if the user gave
specific art direction.

### Pixel Art

> Pixel art style, clean pixels, limited color palette, readable silhouette,
> crisp edges, no text, no watermark.

Variants:

- **8-bit:** NES-era pixel art, 4-color sprite feel, simple shading.
- **16-bit:** SNES-era pixel art, richer palette, subtle shading.
- **32-bit:** late 1990s console pixel art, detailed sprite shading, readable
  at small sizes.
- **Modern pixel:** high-detail pixel-art look, vibrant palette, polished game
  asset.

### Flat Vector

> Clean flat vector illustration, solid colors, sharp edges, minimal shapes,
> UI-ready icon, no texture, no text.

### Hand-Painted

> Digital hand-painted game art, visible brushwork, rich color blending,
> polished concept-art lighting.

### Isometric

> Isometric perspective, 2:1 tile feel, consistent light from top-left, clean
> edge readability, game-ready terrain/object.

### Low-Poly 3D

> Low-poly 3D render, flat-shaded polygons, simplified geometry, studio
> lighting, clean silhouette.

### Watercolor

> Watercolor illustration, soft edges, subtle paper texture, gentle color bleed,
> storybook mood.

## Game Presets

### Platformer

> 2D side-view perspective, clear silhouette, high contrast, readable at small
> size, bright platform-game palette.

### Top-Down RPG

> Top-down RPG perspective, detailed but clean, tile-scale readability, fantasy
> adventure palette.

### Tactical RPG

> Isometric tactical RPG asset, muted fantasy palette, compact proportions,
> readable on a grid, dark outline, no text.

### Card Game

> Card illustration, portrait framing, strong central subject, readable focal
> point, polished fantasy painting.

### Mobile/Casual

> Bright casual game art, rounded shapes, friendly color palette, simple forms,
> high contrast, icon-friendly.

## Prompt Templates

### Sprite or Character

```text
<style>. <character description> in <pose>, facing <direction>.
Clear silhouette, readable at small size, <palette>. For a <genre> game.
No text, no watermark, no extra objects.
```

### Item or Icon

```text
<style>. <item name>, centered, standalone, crisp edges, readable as a game
icon. <key material/color details>. No text, no watermark, no extra objects.
```

### Tile or Terrain

```text
<style>. <terrain type> tile, top-down view, consistent lighting, clean edges,
texture detail suitable for a game map.
```

### Background

```text
<style>. <scene description>, <time of day>, <mood>, <perspective>, layered
depth, no text, no watermark.
```

## Size Guidance

- `1024x1024`: sprites, items, icons, square tiles
- `1536x1024`: landscape scenes, wide backgrounds
- `1024x1536`: portraits, tall characters
- `2048x2048`: higher-detail square final assets
- `3840x2160`: high-resolution landscape finals
- `2160x3840`: high-resolution portrait finals

Use larger sizes intentionally. They cost more and may take longer.

## Quality Guidance

- `low`: exploration, batches, first drafts
- `medium`: good single assets and selected variants
- `high`: final/keeper images, hero art, detailed backgrounds
- `auto`: when the prompt itself should drive the tradeoff

For exact current costs, use the OpenAI pricing page or image generation
calculator. Avoid hardcoding stale price promises into user-facing output.

## Reference Image Tips

- Use one strong reference image when preserving style matters.
- Use multiple references for a set of related icons or tiles.
- Put the most important subject/style reference first.
- `gpt-image-2` automatically uses high-fidelity image inputs; do not use
  `--input-fidelity`.
- For iterative refinement, feed the prior output back with `--image`.

## Transparency Tips

- Prefer a blank or opaque background with `gpt-image-2` when alpha is not
  strictly required.
- Prefer `--transparent-mode chroma-key` for transparent PNG sprites so the
  generation stays on `gpt-image-2`.
- Use `--transparent-mode fallback-model` only when actual native alpha
  PNG/WebP output is required or chroma-key cleanup is unsuitable.
- Avoid JPEG for transparency. Chroma-key mode currently targets PNG output.
- Choose a key color absent from the subject, such as `#ff00ff` or `#00ff00`.
- Ask for a "solid flat chroma-key background", with "no shadows", "no
  gradients", and "no background objects".
- Chroma-key cleanup removes matching key pixels, alpha-bleeds hidden RGB in
  fully transparent pixels from nearby visible pixels, and can suppress
  strongly key-colored visible edge pixels without changing alpha.
- Keep `--chroma-tolerance` conservative. The default is `24`; valid values are
  `0` through `442`.
