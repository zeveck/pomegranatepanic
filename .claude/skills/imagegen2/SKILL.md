---
name: imagegen2
description: Generate or edit game-oriented raster assets using OpenAI gpt-image-2 through a bundled zero-dependency CLI. Ideal for sprites, tiles, UI elements, icons, portraits, backgrounds, concept art, and reference-image edits. Supports iteration and project asset organization.
disable-model-invocation: false
allowed-tools: "Bash(node .claude/skills/imagegen2/generate.cjs *), Bash(node */imagegen2/generate.cjs *), Bash(node cli/generate.cjs *), Bash(node generate.cjs *)"
argument-hint: <description> [--image path] [size: auto|WxH] [quality: low|medium|high] [transparent] [format: png|webp|jpg]
---

# ImageGen2 for Claude Code

Use this skill when the user asks to generate, edit, or iterate on project-local
bitmap assets with OpenAI `gpt-image-2`.

The CLI is bundled next to this `SKILL.md`. Resolve it relative to the skill
directory when installed. In this repository, the canonical development copy is
also available at `cli/generate.cjs`.

```bash
node /path/to/imagegen2-skill/generate.cjs --prompt "..." --output "..." [options]
```

## Workflow

1. Resolve the user's request into a concrete prompt, output path, size,
   quality, and optional reference images.
2. Check whether the output file already exists. Use a versioned filename
   unless the user explicitly asked to replace it.
3. Use `--dry-run` for unfamiliar option combinations or reference-image edits.
4. Run the CLI and parse its JSON stdout.
5. Report the saved path, model, size, quality, and any transparency mode.

## Important Differences from the old imagegen skill

- Default model is `gpt-image-2`.
- History is `.imagegen2-history.jsonl`.
- `--input-fidelity` is not supported because `gpt-image-2` uses high-fidelity
  image inputs automatically.
- Transparent output is explicit:
  - prefer `chroma-key` for transparent PNG sprites; it keeps `gpt-image-2`,
    requests an opaque solid key-color background, and locally removes matching
    PNG pixels, alpha-bleeds hidden RGB in fully transparent pixels from
    nearby visible pixels, and can suppress strongly key-colored visible edge
    pixels when clean nearby subject colors are available.
  - use `fallback-model` only when native alpha is required; it uses
    `gpt-image-1.5`.
  Disclose which path was used.

## Examples

```bash
node /path/to/imagegen2-skill/generate.cjs \
  --prompt "32-bit pixel art cat wearing a top hat, centered, blank background, no text" \
  --output "./assets/sprites/cat-tophat.png" \
  --quality low \
  --size 1024x1024
```

```bash
node /path/to/imagegen2-skill/generate.cjs \
  --prompt "Create a potion icon matching this item style" \
  --output "./assets/items/potion.png" \
  --image "./assets/items/sword.png" \
  --quality low
```

```bash
node /path/to/imagegen2-skill/generate.cjs \
  --prompt "A cute 16-bit RPG kitten sprite, centered, no text, solid flat #ff00ff chroma-key background, no shadows, no gradients, no background objects" \
  --output "./assets/sprites/kitten.png" \
  --background transparent \
  --transparent-mode chroma-key \
  --chroma-key '#ff00ff' \
  --quality low
```

```bash
node /path/to/imagegen2-skill/generate.cjs \
  --prompt "A clean pixel art health potion icon, standalone, no shadow, no text" \
  --output "./assets/items/health-potion.png" \
  --background transparent \
  --transparent-mode fallback-model \
  --quality low
```

Read `reference.md` for style presets and prompt templates when needed.
