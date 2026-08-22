---
name: anim8gen
description: Generate short, simple sprite animations from natural-language prompts by using imagegen2 for raster frame candidates, agentic frame review for pose and continuity, and local anim8gen tools for alignment, validation, contact sheets, previews, and package reports. Requires the imagegen2 skill.
---

# anim8gen

Use this skill when the user asks to make a short, simple animation from text:
walk cycles, idle loops, blinks, hops, emotes, small object motion, or compact
character actions of roughly two to eight frames. The output is a reviewable
anim8gen package, not a production animation editor.

anim8gen requires the `imagegen2` skill. If imagegen2 is unavailable, stop
before starting an anim8gen run.

Do not use this skill for long cinematic animation, complex multi-character
scenes, four-direction sprite packs, production-grade motion authoring, or
requests where the user only wants a single static image.

## Workflow

1. Locate the project root from the user's current working directory. Do not
   create or copy a repo-root `anim8gen/` workbench for normal use. This skill
   carries its own runtime tools and minimal config templates under
   `runtime/`, while per-run project state belongs under `.anim8gen/runs/<id>`
   by default.
   Helper scripts live next to this `SKILL.md` in `scripts/`. When running a
   helper command, first `cd` to this installed anim8gen skill directory, then
   invoke `python3 scripts/skill_paths.py ...`. Do not assume a `.codex/` path
   exists, and do not install a second anim8gen copy just to make helper paths
   resolve.
2. Locate the `imagegen2` skill before parsing or initializing a package. Check
   sibling skill installs first, then common project and user-level skill
   directories:
   `../imagegen2`, `.claude/skills/imagegen2`, `.codex/skills/imagegen2`,
   `.agents/skills/imagegen2`, `~/.claude/skills/imagegen2`,
   `${CLAUDE_CONFIG_DIR}/skills/imagegen2`, `~/.codex/skills/imagegen2`, and
   `${CODEX_HOME}/skills/imagegen2`. Internally, a valid install must include
   the imagegen2 CLI. If imagegen2 cannot be found, stop and tell the user
   exactly:

   ```text
   anim8gen requires the imagegen2 skill, but I could not find it.

   Install imagegen2 from:
   https://github.com/zeveck/imagegen2

   Suggested prompt for your agent:
   Install the imagegen2 skill from github.com/zeveck/imagegen2, then reload or restart the agent so the skill is available.
   ```
3. Parse invocation flags and retry commands separately from the animation
   brief. Recognize `anim8gen retry [notes]` as a request to revise the most
   recent anim8gen package, and `anim8gen retry <animation-id> [notes]` as a
   request to revise a specific package. Treat `[notes]` as corrective review
   guidance, for example "more padding", "ears are clipped", "use true
   transparent background", or "frame 2 pose is wrong". Preserve existing raw
   candidates, append new retry records, update accepted-frame and review
   manifests, rerun alignment, validation, contact sheet, preview, and package
   report. Regenerate only frames affected by the notes unless the notes imply
   the whole sequence is weak. If no recent package can be determined, ask
   which animation id to retry.
4. Recognize `noshow` as a preview flag that skips the local preview server.
   Remove this flag token from the prompt before deriving subject, style,
   frame labels, or poses.
5. Parse the natural-language request into a brief: `id`, subject, style, view,
   frame count, frame labels, per-frame pose descriptions, canvas size, FPS,
   references, anchor behavior, and preview-only effects. Default to the fewest
   frames that can make the action pleasing: usually 2-4 frames. Use more only
   when the user asks for specific beats or the motion needs anticipation,
   contact, recovery, or holds. The hard cap is 12 frames; ask the user to split
   broader actions into sub-actions rather than forcing a long sequence into one
   package. When the plan intentionally repeats an identical pose, set that
   frame's `reuseFrame` to the earlier frame index instead of generating a
   duplicate.
6. Ask for clarification when the subject, camera view, frame count, or core
   action is ambiguous. Narrow or decline requests that exceed the first
   anim8gen scope.
7. Initialize the package paths under `.anim8gen/runs/<id>/` with the
   installed skill helper:
   `python3 "$(python3 scripts/skill_paths.py init-package)" --brief <brief.json>`
   from the installed anim8gen skill directory. Use the reusable shape in
   `$(python3 scripts/skill_paths.py template-animation-spec)`. The
   initializer adds `.anim8gen/` to the project root `.gitignore` when needed.
   Do not automatically ignore `assets/anim8gen/`; that export bundle is a
   project asset decision.
8. Use `imagegen2` as the required raster generator. Do not choose `nanogen`,
   `imagegen`, or another generator for anim8gen work. If imagegen2 is
   unavailable, stop before generation and tell the user to install or repair
   imagegen2.
9. Run `imagegen2` directly and let its bundled CLI handle credentials. Do not
   source `.env`, inspect `OPENAI_API_KEY`, echo credential state, or wrap
   imagegen2 with ad hoc key-loading shell. The imagegen2 CLI loads `.env`
   itself and reports missing or invalid credentials safely. For anim8gen
   frame generation, pass `--no-history`; anim8gen records per-run provenance
   in `.anim8gen/runs/<id>/manifests/`, so imagegen2's root
   `.imagegen2-history.jsonl` log is redundant and should not be produced.
10. For sprite work that needs transparency, prefer imagegen2's GPT Image 2
   chroma-key mode:
   `--background transparent --transparent-mode chroma-key --chroma-key <key>`.
   This asks the model for an opaque solid key background, then lets imagegen2
   remove that key locally into PNG alpha. Record `transparentMode`, `chromaKey`,
   `chromaTolerance`, and postprocess metadata in `candidates.jsonl` and the
   package report. Use `--transparent-mode fallback-model` only when the user
   explicitly asks for native model alpha or when chroma-key output is
   unavailable or repeatedly fails review. Choose a key color that is absent
   from the subject and requested effects: magenta is fine for many sprites,
   but avoid it for purple/blue-heavy subjects, magic, or sprites where magenta
   fringe is likely to be confused with art. Cyan or green keys are acceptable
   when they contrast better with the sprite palette.
11. Resolve any user-provided reference image, sprite, contact sheet, or frame
   set before generation. Add them to `brief.references`, preserving any
   request to use a reference exactly as provided with `referenceCleanup:
   false` or per-reference `"cleanup": false`. After package initialization,
   run the bundled helper resolved by
   `python3 scripts/skill_paths.py prepare-references`. This copies originals,
   prepares PNG references by default, writes
   `reference/prepared-references.json`, and returns the image paths to pass to
   imagegen2. Use `generationPath` from that manifest for all image inputs. In
   normal user-facing output, summarize this only as "I prepared the reference
   image for animation. The original was preserved." Keep technical cleanup
   details in the JSON reports. If the user provides a sequence, use matching
   prepared frames as pose references when possible; otherwise use the strongest
   prepared identity/style image as the canonical reference.
12. Run an `imagegen2 --dry-run` before live generation. If no suitable
   canonical reference was provided, generate frame 0 first and treat the
   accepted frame 0 image as the canonical visual reference for the package.
   Copy or symlink the accepted canonical image to
   `.anim8gen/runs/<id>/reference/reference.png` when practical, and record it
   in the manifests.
13. Generate later raw frame candidates into
   `.anim8gen/runs/<id>/raw/frame-<index>.retry-<retry>.png` with the
   canonical reference passed as the first `--image`. For poses that depend on
   adjacent motion or user-provided frame references, pass those images as
   additional `--image` inputs, but keep the canonical reference first.
   Preserve these input image paths in `candidates.jsonl`. For frames with
   `reuseFrame`, do not call imagegen2; point the accepted-frame record at the
   reused frame's accepted source and record a local reuse candidate.
14. Inspect candidates before accepting them. Verify pose presence, identity
   continuity, camera continuity, sprite hygiene, segmentable background, and
   absence of text, watermarks, UI labels, extra subjects, unwanted props, or
   baked preview effects. Reject frames where the requested action only appears
   as a resize, small translation, or vague wiggle. A frame must visibly show
   the intended beat: open mouth, raised staff, released bubble, striking
   weapon, flapping wing, impact pose, or other concrete pose/effect named by
   the plan. Reject obvious anatomy or object slop: extra legs, arms, paws,
   fins, wings, fingers, eyes, duplicate weapons, malformed faces, and fused or
   impossible appendages. Do not mark a frame `accepted` while also saying
   "final visual grading required"; use `candidate` until it has passed visual
   review.
15. Reject identity drift rather than accepting it as a warning. Hair, helmet,
   face age, robe color, held-hand, weapon shape, chest clasp, border design,
   and primary palette changes are identity failures unless the brief
   explicitly asks for them. Reject cut-off silhouettes, cropped weapons,
   missing held items, missing requested action/effect, and frames that cannot
   be fixed with alignment.
16. Record every attempt in
   `.anim8gen/runs/<id>/manifests/candidates.jsonl`. Keep generation
   transport metadata separate from review fields: use `reviewStatus` and
   `reviewNotes` for review decisions. Preserve rejected candidates and notes;
   do not silently replace weak outputs.
17. When a frame is missing or weak, revise the prompt and retry within the
   package retry budget. If acceptable poses cannot be produced, continue with
   a partial or blocked package report instead of claiming success.
18. Write `.anim8gen/runs/<id>/review/frame-reviews.json` before alignment
    succeeds or fails. Every accepted frame must have an explicit pose,
    identity, camera, hygiene, background, and decision record.
19. Align accepted frames with the bundled runtime tool resolved by
    `python3 scripts/skill_paths.py align-frames`, validate with
    `python3 scripts/skill_paths.py validate-sprites`, create a contact sheet
    with `python3 scripts/skill_paths.py make-contact-sheet`, and create an
    HTML preview with `python3 scripts/skill_paths.py make-preview`. Export an
    animated GIF with `python3 scripts/skill_paths.py export-gif` for every
    complete or partial package after the preview is built, and export an
    animated WebP with `python3 scripts/skill_paths.py export-webp` when
    transparent or painterly edges need a higher-fidelity review artifact.
    GIF and WebP export are local post-processing, should not call image
    generation, and should honor `render.fps`, `preview.playbackIndexes`,
    `reuseFrame`, and `preview.displayOffsets`.
20. Export the visible deliverable bundle with
    `python3 scripts/skill_paths.py export-bundle`. The bundle should contain
    `frames/`, `preview.html`, `<id>.gif`, and `<id>.webp` when WebP export is
    available; raw candidates should appear only when they materially differ
    from final aligned frames.
21. Review the contact sheet and exported preview. For grounded in-place
    sprites, keep
    `alignment.stabilizeAnchorX` enabled so tails, paws, robes, or weapons do
    not move the registration point. Use bottom-center anchors for grounded
    full-body characters, body-center for floating/projectile/effect sprites,
    and head-center only for portraits or face-locked animation. Use spec
    manual anchors only when automatic registration still drifts. Use
    `preview.displayOffsets` only for playback polish; regenerate images for
    wrong identity, wrong pose, wrong camera angle, or unclean sprite pixels.
    Keep `preview.runtimeEffects` separate from sprite pixels unless the user
    explicitly asks for baked effects.
22. After exporting a preview, automatically choose an unused localhost port,
    start a static server rooted at `assets/anim8gen/<id>` for the generated
    preview, and provide a clickable URL such as
    `http://127.0.0.1:<port>/preview.html`. With `noshow`, do not offer or
    start a preview server. Prefer
    `python3 -m http.server <port> --bind 127.0.0.1 --directory assets/anim8gen/<id>`;
    if that port is busy, pick another. Keep the server running for review and
    mention the session only after it successfully starts.
23. Return final package paths, validation status, review warnings, rejected
    candidate summary, exported preview path, preview-only offsets/effects, and
    remaining limitations.

## Required Package Paths

Use these paths for each animation id:

```text
.anim8gen/runs/<animation-id>/config/<animation-id>.json
.anim8gen/runs/<animation-id>/reference/
.anim8gen/runs/<animation-id>/raw/frame-000.retry-001.png
.anim8gen/runs/<animation-id>/aligned/frame-000.<label>.png
.anim8gen/runs/<animation-id>/review/contact-sheet.png
.anim8gen/runs/<animation-id>/review/frame-reviews.json
.anim8gen/runs/<animation-id>/manifests/candidates.jsonl
.anim8gen/runs/<animation-id>/manifests/accepted-frames.json
.anim8gen/runs/<animation-id>/reports/<animation-id>.validation.json
.anim8gen/runs/<animation-id>/reports/<animation-id>.package.md
.anim8gen/runs/<animation-id>/preview/<animation-id>.html
.anim8gen/runs/<animation-id>/gifs/<animation-id>.gif
assets/anim8gen/<animation-id>/frames/
assets/anim8gen/<animation-id>/preview.html
assets/anim8gen/<animation-id>/<animation-id>.gif
```

The visible sprite outputs are under `assets/anim8gen/<animation-id>/`.
Internal raw candidates, references, aligned PNGs, review images, manifests,
reports, specs, and hidden preview HTML are provenance in `.anim8gen/runs/`.

## Imagegen2 Prompt Rules

Keep prompts frame-specific and continuity-aware:

- State the subject, style, camera view, and exact pose for that frame.
- Request a single centered subject on a solid flat chroma-key background,
  using the spec's `segmentation.chromaKey`. Include "no
  shadows", "no gradients", and "no background objects" when segmentation
  quality matters.
- Ask for a compact readable silhouette and full body within the canvas.
- For continuity, always use the accepted frame 0 image as the canonical
  reference for later frames. Pass it as the first `--image` to imagegen2.
  Optionally pass the previous accepted frame as a second neighboring reference
  when it helps the motion.
- Explicitly say no text, no watermark, no labels, no UI overlay, no extra
  subjects, no shadows that prevent segmentation, and no baked runtime effects.
- For transparent sprite requests, the live imagegen2 command should include
  `--background transparent --transparent-mode chroma-key --chroma-key <key>`
  and `--no-history`, and normally leave `--chroma-tolerance` at the CLI
  default unless review shows retained key pixels or subject erosion.

Use `references/prompting.md` when a task needs a prompt template.

## Frame Count Guidance

Use the fewest frames that make the requested motion read well:

- 2 frames: blink, toggle, tiny bounce, simple open/closed state.
- 3 frames: squash/air/land, closed/open/shine, anticipation/action/recover.
- 4 frames: most small game actions, including idle beats, attacks, casts,
  dodges, emotes, and object state changes.
- 5-8 frames: richer acting, holds, peeks, sleep/wake cycles, or motions with
  distinct anticipation/contact/recovery beats.
- 9-12 frames: only when the user clearly asks for that many beats or provides
  a reference frame set. Tell the user larger sequences take longer and are
  more likely to need retries.

For more than 12 frames, ask the user to split the request into sub-actions or
separate packages.

## Candidate State Model

Treat `imagegen2` output metadata and review decisions as different records.
`candidates.jsonl` is append-only provenance for every attempt. Each record
must include at least `prompt`, `frameIndex`, `frameLabel`, `outputPath`,
`retry`, `reviewStatus`, and `reviewNotes`.

Allowed `reviewStatus` values:

- `candidate`: generated or staged but not reviewed yet.
- `accepted`: accepted as the source for that spec frame.
- `accepted-with-warning`: usable source frame with documented limits.
- `rejected-pose`: wrong or unreadable requested pose.
- `rejected-identity`: different subject, style, or character identity.
- `rejected-background`: background is not segmentable or contains scene
  elements.
- `rejected-artifact`: text, watermark, labels, extra subjects, baked effects,
  crop failure, or other unusable artifact.

Normal alignment requires one `accepted` or `accepted-with-warning` candidate
for every spec frame. If that cannot be achieved within `generation.retryBudget`
then set the package state to `partial` or `blocked` and explain the gap.

`review/frame-reviews.json` is the visual review ledger. It records
`packageStatus` as `complete`, `partial`, or `blocked`, plus per-frame pose,
identity, camera, hygiene, background, decision, retry reason, and notes.
Validate these records with:

```bash
cd <installed-anim8gen-skill-dir>
python3 "$(python3 scripts/skill_paths.py validate-review-records)" \
  --candidates .anim8gen/runs/<id>/manifests/candidates.jsonl \
  --reviews .anim8gen/runs/<id>/review/frame-reviews.json
```

## Agentic Review

Do not accept generated frames blindly. A frame can be accepted only after
visual inspection of the raw candidate, the contact sheet, or both.

Minimum review checks:

- Pose presence: the requested pose is visibly represented.
- Identity continuity: the same character or object appears across frames.
- Camera continuity: the requested side, front, top-down, isometric, or
  three-quarter view does not drift.
- Sprite hygiene: no text, watermarks, UI labels, unwanted props, extra
  subjects, complex background, or baked preview-only effects.
- Animation continuity: size, anchor, baseline, centroid drift, and silhouette
  changes are acceptable or documented.
- Runtime separation: preview effects stay out of source sprite pixels unless
  the user explicitly requested baked pixels.
- Preview layout separation: `preview.displayOffsets` may shift an accepted
  frame during playback, but it does not upgrade a weak pose or replace review
  evidence.

Use `references/review-checklist.md` for candidate acceptance notes.

## Package Initialization

After parsing the user's request, write a prepared brief JSON and initialize
the package deterministically:

```bash
cd <installed-anim8gen-skill-dir>
python3 "$(python3 scripts/skill_paths.py init-package)" \
  --brief /tmp/<id>.brief.json
```

The initializer creates the spec, package directories, `.gitkeep` files,
package `.gitignore`, empty candidate manifest, accepted-frame manifest, and
package manifest. It refuses to overwrite an existing package unless `--force`
is passed.

For local smoke tests only, create synthetic chroma-keyed raw frames without
calling image generation:

```bash
cd <installed-anim8gen-skill-dir>
python3 "$(python3 scripts/skill_paths.py create-synthetic-frames)" \
  --spec .anim8gen/runs/<id>/config/<id>.json \
  --root .anim8gen/runs/<id>
```

Do not present synthetic helper frames as `imagegen2` output.

## Local Tool Commands

Replace `<id>` with the package id:

```bash
python3 "$(python3 scripts/skill_paths.py align-frames)" \
  --spec .anim8gen/runs/<id>/config/<id>.json \
  --input .anim8gen/runs/<id>/raw \
  --output .anim8gen/runs/<id>/aligned

python3 "$(python3 scripts/skill_paths.py validate-sprites)" \
  --spec .anim8gen/runs/<id>/config/<id>.json \
  --frames .anim8gen/runs/<id>/aligned \
  --out .anim8gen/runs/<id>/reports/<id>.validation.json

python3 "$(python3 scripts/skill_paths.py make-contact-sheet)" \
  --spec .anim8gen/runs/<id>/config/<id>.json \
  --raw .anim8gen/runs/<id>/raw \
  --aligned .anim8gen/runs/<id>/aligned \
  --validation .anim8gen/runs/<id>/reports/<id>.validation.json \
  --out .anim8gen/runs/<id>/review/contact-sheet.png

python3 "$(python3 scripts/skill_paths.py make-preview)" \
  --spec .anim8gen/runs/<id>/config/<id>.json \
  --frames .anim8gen/runs/<id>/aligned \
  --validation .anim8gen/runs/<id>/reports/<id>.validation.json \
  --out .anim8gen/runs/<id>/preview/<id>.html

python3 "$(python3 scripts/skill_paths.py export-gif)" \
  --spec .anim8gen/runs/<id>/config/<id>.json \
  --frames .anim8gen/runs/<id>/aligned \
  --out .anim8gen/runs/<id>/gifs/<id>.gif

python3 "$(python3 scripts/skill_paths.py export-bundle)" \
  --spec .anim8gen/runs/<id>/config/<id>.json \
  --out assets/anim8gen/<id> \
  --force
```

Preview display flags:

- `noshow`: skip the preview server and do not start one.
- no flag: automatically start a local preview server after packaging and
  provide the clickable preview URL.

When showing a generated preview, start a local static server on an unused
port:

```bash
python3 -m http.server <port> --bind 127.0.0.1 --directory assets/anim8gen/<id>
```

Then give the user:

```text
http://127.0.0.1:<port>/preview.html
```

## Quality Reporting

End every run with package paths and an honest status:

- `complete`: every spec frame has an accepted or accepted-with-warning
  candidate, alignment and validation ran, contact sheet and preview exist, and
  warnings are documented.
- `partial`: at least one frame is weak or missing, but the package is useful
  for review.
- `blocked`: generation, credentials, missing tools, or invalid inputs prevent
  a meaningful package.

Include validation failures, advisory continuity drift, and the exported GIF
path in the package report and final response. Never describe a preview as
final without reviewing both the generated frames and the playback package.
