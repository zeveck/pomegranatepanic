# Anim8gen Prompting

Use this template for each generated frame:

```text
<style> sprite frame of <subject>, <view> view, single centered full-body
subject, pose for frame <index> (<label>): <frame pose>. Compact readable
silhouette, consistent identity with the reference, full body inside the image,
solid #ff00ff chroma-key background, no text, no watermark, no labels, no UI
overlay, no extra subjects, no props unless requested, no motion marks, no
baked preview effects.
```

For animation packages, use references aggressively:

- If the user provides an existing image, sprite, contact sheet, or frame set,
  verify the paths and copy them into `.anim8gen/runs/<id>/reference/`.
- Use the strongest identity/style image as the canonical reference.
- If the user provides a frame set, use corresponding frames as pose references
  where possible.
- If no reference is provided, create or accept canonical frame 0 first.
- If two planned frames are intentionally identical, generate the pose once and
  reuse the accepted source for the repeated frame instead of prompting the
  image model again.

Declare the intended registration point before generation:

- Use bottom-center/feet anchors for grounded full-body characters and objects.
- Use body-center anchors for floating sprites, projectiles, pickups, spell
  effects, explosions, smoke, or objects that expand/rotate around the middle.
- Use head-center anchors for portraits, talking heads, blinks, or expressions.
- For in-place sprite loops, preserve transparent padding and keep the same
  floor/contact line across frames. Asymmetric paws, tails, robes, weapons, or
  spell effects should extend into padding rather than recentering the body.

Pass the canonical image to `imagegen2` with `--image` for every later frame.
Put it first when multiple references are used. For adjacent-frame continuity,
consider passing the previous accepted frame as an additional reference when
that does not over-constrain the requested pose.

Do not let reference consistency erase the action. Later-frame prompts should
say both "keep the same design" and "make the action unmistakable." If a
candidate merely shifts, scales, or wiggles without showing the requested pose
or effect, reject and retry with a larger visible beat.

For character sprites, include anatomy constraints when relevant: exactly the
expected number of legs, arms, paws, fins, wings, eyes, fingers, held weapons,
and facial features. Treat extra appendages or malformed anatomy as rejected
artifacts, even if the pose is otherwise readable.

Name identity locks explicitly in each later-frame prompt:

```text
Keep exactly the same character design as the reference: same hair color, face,
helmet/hat state, clothing colors, weapon shape, held hand, proportions, and
pixel-art rendering. Change only the pose for this frame.
```

Keep each retry targeted. Preserve the accepted identity, style, camera, and
background instructions, then name the one failure that caused the retry.

Retry prompts should name the specific failure:

```text
Retry frame 002. Keep the same cat identity and side view as the reference, but
make the paw visibly raised and touching the mouth. Keep the magenta background
flat and remove all labels or motion marks.
```
