# audiogen Reference — Presets, Archetypes, Cost

This file is a preset and style library for the `/audiogen` skill. It is
**not auto-injected** — `SKILL.md` is what the agent loads on every
invocation; this file is consulted selectively when a user names a
preset ("chiptune", "orchestral", "gruff guard"), when you need voice
archetype guidance, or when you need to quote cost.

**Presets are templates, not literal prompts.** When the user says
"chiptune boss battle", compose the actual API prompt by expanding the
template below with any additional cues from the user's phrasing — mood
modifiers, instrumentation requests, tempo hints, and so on. Do not
just paste the template string verbatim; use it as a starting point.

Structure:

- [Music Presets](#music-presets) — 20 templates covering common game
  BGM needs
- [Voice Archetypes](#voice-archetypes) — 15 character types common to
  RPGs and adventure games
- [SFX Presets](#sfx-presets) — 25 common game-sfx templates
- [Cost Reference](#cost-reference) — approximate rates; live page wins

---

## Music Presets

Use with `/audiogen music <prompt>` — expand the `Template prompt`
below with any scene, instrumentation, or mood cues from the user's
phrasing. `Typical length_ms` is a starting point; adjust for the
scene (stingers are short, exploration loops are long).

### 1. Chiptune Boss Battle (NES)

- **Template prompt:** `aggressive 8-bit NES chiptune boss battle
  theme, fast driving tempo around 150 BPM, two pulse-wave lead lines
  trading melodies, triangle-wave bass, noise-channel snare, heroic
  yet menacing, minor key`
- **Typical length_ms:** 30000 – 60000 (short loop)
- **Notes:** Use `--force-instrumental`. Try `--seed` for
  reproducibility once you find a take you like. Pair with `--loop`
  in-engine (music has no native loop flag).

### 2. Chiptune Overworld (SNES)

- **Template prompt:** `bright cheerful SNES-era 16-bit chiptune
  overworld theme, medium tempo 110 BPM, sampled orchestral hits,
  FM-synth leads, bouncy bass, adventurous major key, hints of Koji
  Kondo sensibility`
- **Typical length_ms:** 60000 – 120000
- **Notes:** Keep it long enough that the loop isn't obvious.

### 3. Chiptune Game Boy (mono)

- **Template prompt:** `lo-fi Game Boy DMG-era chiptune, 4-channel
  mono, two pulse waves, one wave-table lead, one noise-channel
  percussion, wistful minor key, mid-tempo`
- **Typical length_ms:** 30000 – 60000
- **Notes:** The mono, low-bitrate feel comes through if you emphasize
  "DMG-era" and "4-channel".

### 4. Arcade Shmup (90s)

- **Template prompt:** `fast aggressive 90s arcade shoot-em-up theme,
  170 BPM, FM-synth lead melody, driving rock drums, distorted bass,
  frantic energy, ascending minor-key progression`
- **Typical length_ms:** 45000 – 90000
- **Notes:** `--force-instrumental`. Good for bullet-hell sections.

### 5. Epic Orchestral Battle

- **Template prompt:** `sweeping epic orchestral battle theme, full
  symphony, brass fanfares, aggressive string ostinato, pounding
  timpani and taiko drums, choir "ah" pads, 130 BPM, heroic D minor`
- **Typical length_ms:** 60000 – 180000
- **Notes:** Long form suits cinematic encounters. Seed helps when
  iterating take-to-take.

### 6. Orchestral Ambient Exploration

- **Template prompt:** `slow peaceful orchestral ambient exploration
  music, sustained strings, soft solo harp, distant French horn,
  gentle woodwind pads, 70 BPM, major key, cathedral reverb, evokes
  rolling hills at dawn`
- **Typical length_ms:** 90000 – 180000
- **Notes:** Long and quiet; designed to loop without fatigue.

### 7. Orchestral Sorrowful Theme

- **Template prompt:** `sorrowful orchestral theme, lone cello
  melody over sustained strings, sparse solo piano, slow 60 BPM,
  D minor, long silences, evokes a lost homeland`
- **Typical length_ms:** 45000 – 90000
- **Notes:** Use for cutscenes, character death, memorials.

### 8. Synthwave / Outrun

- **Template prompt:** `1980s outrun synthwave, driving four-on-the-
  floor kick, gated snare, arpeggiated analog synth bass, glittering
  lead saw pads, FM electric-piano chords, 118 BPM, A minor, warm
  analog tape saturation`
- **Typical length_ms:** 60000 – 180000
- **Notes:** Pairs well with neon / retro-future aesthetics.

### 9. Lo-fi Study Loop

- **Template prompt:** `lo-fi hip-hop study beat, dusty vinyl crackle,
  muted jazz piano Rhodes chords, soft swung drum loop around 75 BPM,
  warm upright bass, mellow brass stabs, rainy-afternoon mood`
- **Typical length_ms:** 120000 – 240000
- **Notes:** Great for settlement/hub scenes. `--force-instrumental`.

### 10. Jazz Noir

- **Template prompt:** `slow smoky 1950s film-noir jazz, walking
  upright bass, brushed kit, muted trumpet solo, dissonant piano
  chords, 80 BPM, evokes a rainy detective's office`
- **Typical length_ms:** 45000 – 120000
- **Notes:** Good for detective / investigation scenes.

### 11. Swing Tavern

- **Template prompt:** `upbeat 1940s swing tavern band, acoustic
  rhythm guitar, walking bass, brushed snare, clarinet and trumpet
  trading solos, 140 BPM, major key, warm wooden room tone`
- **Typical length_ms:** 60000 – 180000
- **Notes:** Works for taverns, speakeasies, prosperous towns.

### 12. Dark Ambient Dungeon

- **Template prompt:** `dark ambient dungeon drone, deep sustained
  cello and contrabass, distant metal scraping, faint distant
  whispers, occasional ritual bell, no melody, heavy reverb, dread
  and claustrophobia`
- **Typical length_ms:** 120000 – 300000
- **Notes:** Long form — designed not to repeat. No clear pulse.

### 13. Tension Build / Stinger Lead-in

- **Template prompt:** `rising orchestral tension, sustained string
  cluster slowly crescendoing, low brass rumble, heartbeat-like bass
  drum accelerating, building to a cliff-edge moment, no resolution`
- **Typical length_ms:** 15000 – 30000
- **Notes:** Place before a reveal or boss entry.

### 14. Horror Atmosphere

- **Template prompt:** `psychological horror atmosphere, atonal
  strings, detuned music-box fragments, distant child laughter
  processed into noise, subharmonic bass pulses, unpredictable silence`
- **Typical length_ms:** 60000 – 180000
- **Notes:** Avoid melodic content. Use with sparse SFX layered on top.

### 15. Celtic Folk Village

- **Template prompt:** `warm celtic folk village theme, solo tin
  whistle melody, bodhrán drum, gentle harp, fiddle countermelody,
  strummed bouzouki, 100 BPM, major key, pastoral and welcoming`
- **Typical length_ms:** 60000 – 180000
- **Notes:** Good for druid / nature / cottage scenes.

### 16. Medieval Court

- **Template prompt:** `stately medieval court music, lute, recorder,
  harpsichord, viol da gamba, no modern drum kit, 90 BPM, Mixolydian
  mode, evokes a grand audience hall`
- **Typical length_ms:** 60000 – 180000
- **Notes:** Suits castles, noble courts, formal audiences.

### 17. Western Frontier

- **Template prompt:** `Ennio Morricone-style spaghetti-western theme,
  lone electric guitar tremolo, acoustic 12-string picking,
  harmonica melody, distant ocarina, whip-crack percussion, 95 BPM,
  minor key`
- **Typical length_ms:** 60000 – 120000
- **Notes:** Works for desert, outlaw, gunslinger scenes.

### 18. EDM Cyberpunk Chase

- **Template prompt:** `aggressive cyberpunk EDM chase music, 140 BPM
  drum-and-bass groove, acid 303 bassline, distorted supersaw lead,
  reverse cymbals, glitchy stutters, high tension`
- **Typical length_ms:** 60000 – 180000
- **Notes:** Pair with vehicle / parkour / infiltration mechanics.

### 19. Victory Stinger

- **Template prompt:** `triumphant short orchestral victory stinger,
  full brass and timpani fanfare, ascending major-key flourish,
  cymbal crash at resolution, no loop, clear ending`
- **Typical length_ms:** 3000 – 8000
- **Notes:** One-shot; do NOT attempt to loop. Keep `--length-ms`
  minimal.

### 20. Game Over Stinger

- **Template prompt:** `somber short orchestral game-over stinger,
  descending minor-key progression, single solo horn, slow fade to
  low piano octave, ending on an unresolved minor chord`
- **Typical length_ms:** 5000 – 10000
- **Notes:** One-shot. Often paired with screen-fade timing.

---

## Voice Archetypes

Use with `/audiogen voice <text> --voice-id <name_or_id>`. Each
archetype below includes a suggested `voices` query for catalog
browse, starting `voice_settings`, and a model recommendation. **Do
not hard-code voice IDs here — the catalog changes. Query the cache.**

Voice settings quick reference:

- `--stability` (0–1) — higher = steadier, less emotional variation;
  lower = more expressive, more variance per take.
- `--similarity-boost` (0–1) — higher = sticks closer to the source
  voice's timbre; lower = allows more interpretation.
- `--style` (0–1) — higher = more stylistic exaggeration.
- `--speed` (0.5–2) — playback speed; 1.0 is default.

Model quick reference:

- `eleven_multilingual_v2` — default, rich, good general choice.
- `eleven_v3` — most expressive, best for emotional / dramatic
  lines.
- `eleven_flash_v2_5` — fastest, cheapest, lower fidelity.
- `eleven_turbo_v2_5` — mid-latency, mid-fidelity.

### 1. Gruff Guard Captain

- **Suggested voices query:** `/audiogen voices gruff --gender male`
  or `/audiogen voices british deep --gender male`
- **Voice profile:** male, 40s–50s, deep chest voice, slight rasp,
  British or American-mid.
- **Settings:** `--stability 0.6 --similarity-boost 0.75 --style 0.2`
- **Model:** `eleven_multilingual_v2`
- **Typical lines:** "Halt! State your business." / "Move along,
  citizen."

### 2. Wise Old Wizard

- **Suggested voices query:** `/audiogen voices old wise --gender male`
  or `/audiogen voices sage --accent british`
- **Voice profile:** male, 60s+, measured cadence, warm timbre with
  slight wavering, British theatrical.
- **Settings:** `--stability 0.7 --similarity-boost 0.7 --style 0.3
  --speed 0.95`
- **Model:** `eleven_v3` (for incantations) or `eleven_multilingual_v2`
- **Typical lines:** "Ah, young one… you stand at the crossroads of
  fate."

### 3. Mischievous Trickster

- **Suggested voices query:** `/audiogen voices playful young
  --gender male` or `/audiogen voices sly`
- **Voice profile:** androgynous or male, 20s–30s, quick bright
  delivery, frequent smirk, slight upward lilt.
- **Settings:** `--stability 0.35 --similarity-boost 0.65 --style
  0.6`
- **Model:** `eleven_v3`
- **Typical lines:** "Oh *now* you need my help? Interesting…"

### 4. Stoic Warrior

- **Suggested voices query:** `/audiogen voices stoic --gender male`
  or `/audiogen voices gravelly --gender male`
- **Voice profile:** male, 30s–40s, low, sparse, unemotional, dry
  American or Scandinavian timbre.
- **Settings:** `--stability 0.8 --similarity-boost 0.8 --style 0.1`
- **Model:** `eleven_multilingual_v2`
- **Typical lines:** "Then we fight." / "I have seen worse."

### 5. Arcane Scholar

- **Suggested voices query:** `/audiogen voices scholarly
  --accent british` or `/audiogen voices articulate --gender female`
- **Voice profile:** any gender, 30s–50s, crisp articulation, dry
  intellectual tone, British RP or refined American.
- **Settings:** `--stability 0.65 --similarity-boost 0.7 --style 0.25`
- **Model:** `eleven_multilingual_v2`
- **Typical lines:** "Fascinating — note the sigil's clockwise spiral.
  That rules out three of the four schools."

### 6. Cheerful Shopkeeper

- **Suggested voices query:** `/audiogen voices cheerful
  --gender female` or `/audiogen voices warm friendly`
- **Voice profile:** any gender, 30s–50s, bright warm tone, slight
  regional accent optional, frequent smile.
- **Settings:** `--stability 0.5 --similarity-boost 0.75 --style 0.4`
- **Model:** `eleven_multilingual_v2`
- **Typical lines:** "Welcome, welcome! Have a look around — no obligation."

### 7. Sinister Villain

- **Suggested voices query:** `/audiogen voices menacing --gender male`
  or `/audiogen voices villain theatrical`
- **Voice profile:** male, 40s+, low resonant voice, slow deliberate
  delivery, hint of smirk.
- **Settings:** `--stability 0.55 --similarity-boost 0.8 --style 0.6
  --speed 0.92`
- **Model:** `eleven_v3` (villains need expressiveness)
- **Typical lines:** "You truly believed you could stop me? How…
  *charming*."

### 8. Frightened Child

- **Suggested voices query:** `/audiogen voices child --gender female`
  or `/audiogen voices young high`
- **Voice profile:** high-pitched, 8–12 years old, breathy when
  scared.
- **Settings:** `--stability 0.3 --similarity-boost 0.7 --style 0.5`
- **Model:** `eleven_v3`
- **Typical lines:** "Is… is it gone? Please say it's gone."
- **Notes:** Be mindful — high emotion benefits from `eleven_v3`.

### 9. Rugged Ranger

- **Suggested voices query:** `/audiogen voices rugged --gender male`
  or `/audiogen voices weathered outdoorsy`
- **Voice profile:** male, 30s–50s, weathered, quiet confidence,
  slight drawl.
- **Settings:** `--stability 0.7 --similarity-boost 0.75 --style 0.2`
- **Model:** `eleven_multilingual_v2`
- **Typical lines:** "Tracks lead north. Three days old. Move quiet."

### 10. Noble Queen

- **Suggested voices query:** `/audiogen voices regal --gender female
  --accent british` or `/audiogen voices commanding elegant`
- **Voice profile:** female, 30s–50s, cultured, authoritative,
  British RP or refined continental.
- **Settings:** `--stability 0.7 --similarity-boost 0.75 --style 0.3`
- **Model:** `eleven_multilingual_v2`
- **Typical lines:** "Rise, Sir Knight. The realm thanks you."

### 11. Street-smart Rogue

- **Suggested voices query:** `/audiogen voices streetwise cockney`
  or `/audiogen voices rough urban`
- **Voice profile:** any gender, 20s–30s, casual, clipped urban
  accent.
- **Settings:** `--stability 0.45 --similarity-boost 0.65 --style 0.5`
- **Model:** `eleven_multilingual_v2`
- **Typical lines:** "Oi — I didn't see nothin' and neither did you,
  right?"

### 12. Ancient Evil Entity

- **Suggested voices query:** `/audiogen voices deep ominous` or
  `/audiogen voices otherworldly`
- **Voice profile:** male or androgynous, unnaturally low, slow,
  reverberant. Consider engine-side pitch-shift / reverb as well.
- **Settings:** `--stability 0.85 --similarity-boost 0.75 --style 0.5
  --speed 0.85`
- **Model:** `eleven_v3`
- **Typical lines:** "I have waited… eons… for this moment."

### 13. Narrator / Storyteller

- **Suggested voices query:** `/audiogen voices narrator
  --gender male` or `/audiogen voices documentary`
- **Voice profile:** any gender, warm, measured, clear diction.
- **Settings:** `--stability 0.7 --similarity-boost 0.7 --style 0.2`
- **Model:** `eleven_multilingual_v2`
- **Typical lines:** "In the beginning, there was only the Song, and
  the Silence that answered it."

### 14. Battle-hardened Mercenary Captain

- **Suggested voices query:** `/audiogen voices gritty --gender female`
  or `/audiogen voices commanding rough`
- **Voice profile:** female, 30s–40s, dry gravelly delivery, clipped
  military cadence.
- **Settings:** `--stability 0.65 --similarity-boost 0.75 --style 0.3`
- **Model:** `eleven_multilingual_v2`
- **Typical lines:** "Form up. Shields interlocked. You break ranks,
  I break you."

### 15. Eccentric Inventor

- **Suggested voices query:** `/audiogen voices eccentric
  --gender male` or `/audiogen voices excited fast-talking`
- **Voice profile:** any gender, fast cadence, jumps between
  excitement and muttering, slight stutter on consonants.
- **Settings:** `--stability 0.35 --similarity-boost 0.65 --style
  0.65 --speed 1.1`
- **Model:** `eleven_v3`
- **Typical lines:** "YES! No — wait — YES! That's it! Brass
  couplings, of *course*!"

---

## SFX Presets

Use with `/audiogen sfx <prompt>`. Duration is capped at 30 s by the
API; for longer ambience, generate a loopable clip with `--loop` and
repeat in-engine. `Typical duration_seconds` below is a starting
point; `auto` means omit `--duration` and let the API choose.

### Doors & Portals

1. **Heavy Wooden Door Slam**
   - *Prompt:* `heavy oak door slamming shut in a stone corridor,
     thick wooden thud, iron hardware rattle, long stone reverb tail`
   - *Duration:* 2.0 | *Loop:* no

2. **Iron Portcullis Raise**
   - *Prompt:* `massive iron portcullis grinding upward on rusted
     chains, metallic scraping, deep chain rattle, finishing clunk`
   - *Duration:* 4.0 | *Loop:* no

3. **Creaky Door Open (haunted)**
   - *Prompt:* `slow creaking of old wooden door opening, long dry
     hinge squeal, faint draft, haunted house ambience`
   - *Duration:* 3.0 | *Loop:* no

4. **Stone Slab Grinding Open**
   - *Prompt:* `heavy stone slab grinding sideways, deep rumble,
     grit and pebbles scattering, tomb-like reverb`
   - *Duration:* 4.5 | *Loop:* no

### Footsteps

5. **Footsteps on Stone**
   - *Prompt:* `single pair of footsteps walking on stone flagstones,
     leather boots, moderate pace, mild dungeon reverb`
   - *Duration:* auto | *Loop:* yes (seamless loop for walk cycle)

6. **Footsteps on Wood Planks**
   - *Prompt:* `footsteps on creaky wooden planks, leather boots,
     each step accompanied by a plank creak, slow pace`
   - *Duration:* auto | *Loop:* yes

7. **Footsteps on Snow**
   - *Prompt:* `crunchy footsteps in deep snow, each step a
     satisfying squeaky crunch, winter ambience`
   - *Duration:* auto | *Loop:* yes

8. **Footsteps on Metal Grating**
   - *Prompt:* `metal boot footsteps on industrial metal grating,
     sharp metallic resonance each step, echoey factory space`
   - *Duration:* auto | *Loop:* yes

### Combat

9. **Sword Swing (whoosh)**
   - *Prompt:* `quick sharp sword whoosh through air, metallic
     overtone, no impact`
   - *Duration:* 0.7 | *Loop:* no

10. **Sword Hit on Shield**
    - *Prompt:* `metal sword striking wooden shield, loud sharp clang,
      wood splintering undertone, short ring-out`
    - *Duration:* 1.0 | *Loop:* no

11. **Axe Hit on Wood**
    - *Prompt:* `heavy battle-axe chopping into wooden log, deep thunk,
      wood splinter crack, forest ambience`
    - *Duration:* 1.2 | *Loop:* no

12. **Fist Punch Impact**
    - *Prompt:* `solid fist punch impact, meaty thud, brief grunt,
      no reverb`
    - *Duration:* 0.6 | *Loop:* no

### Magic

13. **Fireball Cast**
    - *Prompt:* `magic fireball spell casting, whoosh of building
      energy, burst of flame ignition, crackling fire tail`
    - *Duration:* 2.5 | *Loop:* no

14. **Ice Spell**
    - *Prompt:* `frost magic spell, crystalline shimmer, glass-like
      freezing crack, cold wind breath`
    - *Duration:* 2.0 | *Loop:* no

15. **Lightning Bolt**
    - *Prompt:* `magic lightning bolt, sharp electric zap, ozone
      crackle, thunderclap resolution`
    - *Duration:* 1.5 | *Loop:* no

16. **Healing Spell**
    - *Prompt:* `gentle healing spell, soft crystalline chime,
      ascending shimmer, warm glow sustain, angelic pad`
    - *Duration:* 2.5 | *Loop:* no

### UI

17. **Menu Select / Click**
    - *Prompt:* `soft UI menu select click, short synth pop, crisp
      high-frequency transient`
    - *Duration:* 0.3 | *Loop:* no

18. **Coin Pickup**
    - *Prompt:* `bright metallic coin pickup, short sparkling
      chime, gold-coin timbre, video-game flavor`
    - *Duration:* 0.5 | *Loop:* no

19. **Item Equip**
    - *Prompt:* `inventory item equip, leather-and-metal rustle,
      soft click confirmation`
    - *Duration:* 0.6 | *Loop:* no

20. **Error Buzz**
    - *Prompt:* `negative UI error, short dissonant low buzz, muted
      double-beep, no musicality`
    - *Duration:* 0.5 | *Loop:* no

### Ambience (30 s cap — loop in engine)

21. **Forest Ambience Loop**
    - *Prompt:* `peaceful forest ambience, distant birdsong, gentle
      leaf rustle in breeze, faint stream, no musical content,
      seamlessly loopable`
    - *Duration:* 20.0 | *Loop:* yes
    - *Notes:* Loop in-engine for continuous ambience — 30 s cap
      means a single-clip loop is the pattern here.

22. **Cave Ambience Loop**
    - *Prompt:* `deep cave ambience, distant water drips, faint
      echoing wind, occasional pebble fall, long reverb, seamlessly
      loopable`
    - *Duration:* 20.0 | *Loop:* yes

23. **Tavern Ambience Loop**
    - *Prompt:* `busy tavern crowd murmur, clinking mugs, distant
      laughter, fireplace crackle, no music, seamlessly loopable`
    - *Duration:* 25.0 | *Loop:* yes

### Creatures

24. **Goblin Snarl**
    - *Prompt:* `small goblin creature snarl, raspy throaty growl,
      high-pitched angry edge, short`
    - *Duration:* 1.2 | *Loop:* no

25. **Wolf Howl**
    - *Prompt:* `lone wolf howl at night, long mournful rising pitch,
      slight reverb, distant forest ambience, crisp cold air`
    - *Duration:* 3.5 | *Loop:* no

26. **Dragon Roar**
    - *Prompt:* `massive dragon roar, deep chest rumble, sustained
      mid-range growl, final crackle, huge reverb tail, cinematic`
    - *Duration:* 4.0 | *Loop:* no

---

## Cost Reference

**Always defer to the live pricing page at
<https://elevenlabs.io/pricing/api> for authoritative numbers.** The
values below are approximate API-tier rates as of April 2026 and may
lag changes.

### API-tier rates (approximate, April 2026)

| Modality | Rate | Notes |
| -------- | ---- | ----- |
| Music | ~$0.30 / minute of output | Pay per minute of generated audio. |
| TTS — Flash / Turbo (`eleven_flash_v2_5`, `eleven_turbo_v2_5`) | ~$0.05 / 1,000 characters | Fast and cheap; lower fidelity. |
| TTS — Multilingual v2 / v3 (`eleven_multilingual_v2`, `eleven_v3`) | ~$0.10 / 1,000 characters | Default / expressive. |
| SFX | ~$0.12 / generation | Flat rate — 1 s and 30 s cost the same. |

### Free-tier quota

- **10,000 credits / month.** Roughly 60 minutes of Flash TTS, ~30
  minutes of Multilingual-v2 TTS, or ~80 SFX generations.
- Free-tier output **requires attribution** per ElevenLabs' terms.
- Free-tier `output_format` is restricted to `mp3_44100_64` — see the
  Edge Cases section of `SKILL.md` for the 422 recovery hint.

### Worked examples

- **One 30 s chiptune loop + two iterations:** 3 × 30 s = 90 s of
  music ≈ **$0.45**.
- **A quest's worth of dialogue (10 lines × 120 chars with Multilingual-
  v2):** 1,200 chars ≈ **$0.12**.
- **A dungeon's worth of sfx (door, footsteps loop, 4 combat hits, 3
  magic spells, 2 ambience loops) = 11 generations:** 11 × $0.12 ≈
  **$1.32**.
- **A short animated scene with 5 voice lines (1,000 chars, v3) + 1
  music cue (60 s) + 8 sfx:** $0.10 + $0.30 + (8 × $0.12) = **$1.36**.

### Cost-guidance policy (from SKILL.md)

- **Single generation:** no cost quote needed — just generate.
- **Batch of 3 or more generations in one turn:** quote the estimated
  cost and confirm before starting. Use this reference table for the
  numbers.
- Quote the live page URL when precision matters: this reference may
  be out of date.

### Concurrency limits (affect throughput, not cost)

| Tier | Concurrent requests |
| ---- | ------------------- |
| Free | 2 |
| Starter | 3 |
| Creator | 5 |
| Pro | 10 |
| Scale / Business | 15 |

Exceed the limit and the API returns 429. The CLI retries three
times with backoff; beyond that, throttle your batch or upgrade.

---

*End of reference. For the authoritative flag surface, see
`generate.cjs --help`. For conceptual guidance on how to invoke the
skill, see `SKILL.md`.*
