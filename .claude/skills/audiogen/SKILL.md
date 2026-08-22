---
name: audiogen
description: Generate game audio (music, voices, sound effects) via ElevenLabs.
disable-model-invocation: false
allowed-tools: "Bash(node */generate.cjs *)"
argument-hint: "<music|voice|sfx|voices> <description> [--voice-id ID] [--length-ms MS] [--duration SEC] [--output PATH]"
---

# /audiogen — Game Audio Generation via ElevenLabs

Generate background music, character voice lines, and sound effects for games
via the ElevenLabs REST API. One CLI (`generate.cjs`), three modalities,
zero npm deps. Usable both as a Claude Code skill and as a standalone shell
CLI (e.g. from CI).

## Prerequisites

- **Node.js >= 20.14** — required for the built-in `process.loadEnvFile`.
  The CLI asserts this at entry and fails with a clear message on older
  Node.
- **`ELEVENLABS_API_KEY`** — get one at
  <https://elevenlabs.io/app/settings/api-keys>. Either export it in your
  shell, or add `ELEVENLABS_API_KEY=...` to a `.env` file at the project
  root. The CLI walks up from cwd and from the script directory looking
  for a `.env`, loading the first one found. **Shell-exported values take
  precedence over `.env` values** (Node's default; not an audiogen
  choice).
- **ElevenLabs tier** — the API works on any paid tier. Free-tier
  accounts are restricted to `output_format=mp3_44100_64`; see Edge
  Cases. Free-tier output requires attribution; paid-tier output comes
  with perpetual commercial rights.

## Quick Start

```bash
# Background music — 30 seconds of orchestral tension
/audiogen music tense orchestral battle cue --length-ms 30000

# Voice line — must specify a voice
/audiogen voice "Halt, traveller! What brings you here?" --voice-id Rachel

# Sound effect — 2 seconds
/audiogen sfx heavy wooden door slam with reverb --duration 2

# Voice catalog browse
/audiogen voices --gender female --language en
```

All outputs default to `assets/audio/{music,voice,sfx}/<slug>.mp3` in the
current working directory.

## Handling No Arguments

If the user invokes `/audiogen` with nothing after it, ask what they want
to generate before calling the CLI. Don't guess — the three modalities
are priced and shaped very differently. A good clarification: "Music
(background track), a voice line, or a sound effect? And how long should
it be?"

## Arguments — Subcommand Dispatch

The first positional word is always a subcommand:

    /audiogen music|voice|sfx|voices <rest...>

When the user's phrasing makes intent obvious, pick the subcommand
yourself:

- "boss battle music", "title screen theme", "tavern loop" → `music`
- "goblin says ...", "narrator line", "NPC dialogue" → `voice`
- "door slam", "coin pickup", "spell cast" → `sfx`
- "find a female British voice", "list premade voices" → `voices`

When the phrasing is ambiguous (e.g. "a scream" — voice or sfx?), ask.
`voices` is the catalog-browse command, not a generator.

## Subcommand Reference

### `music` — background tracks

    /audiogen music <prompt...> [--length-ms MS] [--seed N]
                                [--force-instrumental]
                                [--output-format FMT] [--output PATH]

Generates one music clip via `POST /v1/music`.

- `--length-ms` — 3000–600000. Default `30000` (30 s). Max 5 minutes.
- `--seed` — integer seed for reproducibility.
- `--force-instrumental` — suppress vocals.
- `--output-format` — `mp3_*`, `pcm_*`, `opus_*`, `ulaw_8000`,
  `alaw_8000`. Default `mp3_44100_128`. **WAV formats (`wav_*`) are
  rejected** — the music endpoint does not accept them.

**Loop caveat.** There is no native "seamless loop" flag for music. For
looping game BGM, loop in the engine / HTML, or build a
`composition_plan` (not exposed in this CLI). See **Loop Caveat** below.

### `voice` — TTS (text-to-speech)

    /audiogen voice <text...> --voice-id <NAME_OR_ID>
                              [--language-code CODE]
                              [--stability N] [--similarity-boost N]
                              [--style N] [--speed N]
                              [--model-id ID] [--seed N]
                              [--output-format FMT] [--output PATH]

Generates one TTS clip via `POST /v1/text-to-speech/{voice_id}`.

- `--voice-id` — **required**. Accepts either an exact voice name from
  the local cache (case-insensitive), or a 20-char alphanumeric voice
  ID. If the name isn't cached, fall back to `audiogen voices <query>`
  to discover one.
- Input cap: **40,000 characters** (enforced client-side).
- `--model-id` — default `eleven_multilingual_v2`. Others:
  `eleven_flash_v2_5` (fast/cheap), `eleven_turbo_v2_5`, `eleven_v3`
  (expressive — best for emotional lines).
- `--stability`, `--similarity-boost`, `--style`, `--speed` — all
  optional `voice_settings` fields. Ranges 0–1 except `--speed` (0.5–2).
- `--output-format` — includes `wav_*` in addition to the usual set
  (WAV is supported for TTS but not for music or sfx).

### `sfx` — sound effects

    /audiogen sfx <prompt...> [--duration N] [--loop]
                              [--prompt-influence N]
                              [--output-format FMT] [--output PATH]

Generates one sound effect via `POST /v1/sound-generation`.

- `--duration` — **0.5 to 30 seconds**. Optional — omit to let the API
  auto-pick a duration. The 30-second ceiling is a hard API limit; for
  longer ambience, generate a loopable clip and repeat in-engine.
- `--loop` — native API flag (requires the `eleven_text_to_sound_v2`
  model, which is the default). Produces a seamlessly loopable
  waveform.
- `--prompt-influence` — 0–1. Default `0.3`. Higher = closer adherence
  to the prompt; lower = more creative latitude.
- `--output-format` — `mp3_*`, `pcm_*`, `opus_*`, `ulaw_*`, `alaw_*`.
  **WAV rejected**, same as music.

### `voices` — browse the voice catalog

    /audiogen voices [query...] [--accent STR] [--gender male|female]
                                [--language CODE] [--category STR]
                                [--limit N] [--page-size N]
                                [--json] [--refresh]

Lists voices from `GET /v2/voices` with client-side filters. Results
are cached at `.audiogen-voices.json` in the project root with a
**24-hour TTL**; stale caches are refreshed automatically. Use
`--refresh` to force a re-fetch.

- `query` (optional positional) — substring match on voice name,
  description, and labels.
- `--accent` — substring match on accent labels (e.g. `british`,
  `american`).
- `--gender` — `male` or `female`.
- `--language` — ISO code (`en`, `ja`, `es`, …).
- `--category` — e.g. `premade`, `cloned`, `professional`.
- `--limit` — cap the number of rows in the table view (default 50).
  `--json` ignores this.
- `--json` — emit raw JSON for scripting; table view otherwise.

The cache file is gitignored. It is not a source of truth — the
ElevenLabs catalog is — but is the canonical resolver for `--voice-id
<name>`.

## How to Compose Prompts

Music and SFX prompts are free-form natural language. Write like you
are briefing a human foley artist or composer:

- **Be specific about instrumentation, tempo, mood.** "Sorrowful
  string quartet, 60 BPM, dry room tone" beats "sad music."
- **Name the genre or era.** "NES chiptune", "Sega Genesis FM
  synthesis", "1950s noir jazz combo" all land recognizably.
- **Describe the scene.** "Heavy iron portcullis slamming shut in a
  stone corridor, long reverb tail" beats "door sound."
- **Stack adjectives for SFX.** The model responds well to three or
  four descriptors chained ("crunchy, wet, low-frequency, metallic").

For quick starting points, see **`reference.md`** — it contains ~20
music presets, ~15 voice archetypes, and ~25 SFX presets. Presets are
templates, not literal prompts: expand them with any additional cues
from the user's phrasing.

## Choosing a Voice

1. If the user names a voice ("use Rachel", "use JBFqn..."), pass
   that to `--voice-id` directly. 20-char alphanumeric strings are
   treated as IDs; anything else is matched against the cache by
   name (case-insensitive).
2. If the user describes what they want ("gruff old wizard",
   "young American female"), run `/audiogen voices <query>` first
   — possibly with `--gender`, `--accent`, or `--language`. Pick a
   candidate by name, then call `voice` with that name.
3. The voice cache auto-refreshes after 24 hours. Use `--refresh` if
   the user says "new voices were added" or you hit a "voice not
   found" error.
4. See `reference.md` for archetype-to-search-query guidance (e.g.
   "Arcane Scholar → `voices wise old male english`").

## Output Organization

Default layout in the current working directory:

    assets/audio/
      music/   — background tracks
      voice/   — TTS lines
      sfx/     — sound effects

- **Filename** is derived from the prompt (lowercased, non-alphanumerics
  collapsed to `-`, first 40 chars). Non-Latin prompts fall back to
  `audio-YYYYMMDD-HHMMSS`.
- **Auto-versioning on collision.** If `assets/audio/music/foo.mp3`
  exists, the next call becomes `foo-v2.mp3`, then `-v3`, up to
  `-v999`. Pass `--force` to overwrite in place.
- **`--output PATH`** overrides everything:
  - If `PATH` is an existing directory (or ends with `/`), the slug is
    written inside it.
  - Otherwise `PATH` is the literal output filename (auto-versioning
    still applies unless `--force`).

**Filenames are a collision-avoidance mechanism, not a version
manifest.** If the user wants to track iterations ("go back to v1",
"that was better than v2"), use `--history-parent <id>` against
`.audiogen-history.jsonl` — see **Regeneration & Iteration**.

## Confirmation Policy

- **Single generation:** run without asking. The user asked for one
  thing; deliver it.
- **Batch of 3+ generations in one turn:** before starting, quote the
  estimated cost (see **Cost**) and confirm. Example: "That's 5 music
  clips at ~$0.15 each = ~$0.75. OK to proceed?"
- **Voice cloning (IVC/PVC) is out of scope** — ElevenLabs requires
  explicit consent-recording workflows that belong in their UI, not a
  CLI. Direct the user to <https://elevenlabs.io/voice-lab>.

## Handling Errors

The CLI prints every failure as `audiogen: <message>` on stderr and
exits 1. Common patterns:

- **401 / 402** — API key invalid, out of credits, or tier
  restriction. Check the key and billing page.
- **422 with `output_format` in the detail** — typically a free-tier
  restriction. The CLI appends the hint "Free-tier accounts are
  restricted to `mp3_44100_64`. Try `--output-format mp3_44100_64`."
- **422 other** — prompt rejected (content policy, unsupported
  parameter combo, …). Refine the prompt and retry.
- **429** — concurrency limit hit (Free 2, Creator 5, Pro 10,
  Business 15). The CLI retries 3x with backoff; after that, the
  user should wait or upgrade.
- **`empty audio response`** — a 200 with zero bytes; the CLI deletes
  the empty file and reports. Refine the prompt and retry.
- **`voice not found` / duplicate name** — the cache has no match, or
  two cached voices share a name. The error lists the candidate IDs;
  pass one directly via `--voice-id <ID>`.

Every error block includes the HTTP status and, when available, the
`xi-request-id` header — include that when filing issues with
ElevenLabs support.

## Regeneration & Iteration

Every successful generation appends one JSON line to
`.audiogen-history.jsonl` in the working directory. Schema:

    {ts, id, parent_id?, type, prompt, model_id, output_path,
     output_format, request_body, request_id?}

- `--history-id ID` — tag a generation with an explicit id (otherwise
  the CLI auto-generates one from the output path).
- `--history-parent ID` — mark this generation as a derivative of a
  prior record. Use for "make that goblin voice gruffer", "same track
  with more brass", etc.

History-file write failures are logged to stderr but **never abort the
generation** — you got the audio, the bookkeeping is best-effort.

## Loop Caveat

- **Music has no native loop flag.** Generate the track, then loop in
  the game engine or HTML `<audio loop>`. For a natively seamless
  loop, you need to craft a `composition_plan` (not exposed in this
  CLI — use the raw ElevenLabs API or their web UI).
- **SFX has native `--loop`** on the default `eleven_text_to_sound_v2`
  model. Produces a clip with matching start/end so it can repeat
  seamlessly in-engine.

## Cost

**The live pricing page at <https://elevenlabs.io/pricing/api> is
authoritative — the numbers below may lag.** Approximate API-tier rates
as of April 2026:

- **Music:** ~$0.30 per minute of output.
- **TTS:** Flash / Turbo ~$0.05 per 1,000 characters; Multilingual v2
  and v3 ~$0.10 per 1,000 characters.
- **SFX:** ~$0.12 per generation, flat (1 second and 30 seconds cost
  the same).
- **Free tier:** 10,000 credits/month — roughly 60 minutes of Flash
  TTS, or a handful of SFX.

Consult `reference.md` for a detailed cost table and worked examples.
When in doubt, quote from the live page, not from this file.

## Licensing

- **Paid-tier output** — user-owned, with **perpetual commercial
  rights that survive account cancellation**.
- **Free-tier output** — commercial use permitted, but attribution
  to ElevenLabs is required per their terms.
- **Voice cloning (IVC / PVC)** — requires explicit, recorded consent
  from the voice owner. **NEVER clone a public figure's voice.**
  Cloning flows live in the ElevenLabs UI; this skill does not expose
  them.

## Key Rules

- **NEVER** clone a public figure's voice — it is TOS-forbidden and
  legally hazardous.
- **ALWAYS** require explicit, recorded consent before cloning a real
  person's voice (IVC or PVC). Direct users to the ElevenLabs UI —
  this CLI does not implement cloning.
- **NEVER** pass `wav_*` formats to `music` or `sfx` — the API rejects
  them. TTS accepts WAV.
- **NEVER** call `sfx` without a text prompt — the endpoint will
  return 400.
- **ALWAYS** keep SFX durations in `[0.5, 30]` — the 30 s ceiling is a
  hard API limit.
- **ALWAYS** quote estimated cost before a batch of 3+ generations.
- **ALWAYS** treat filenames (`-v2`, `-v3`, …) as collision avoidance,
  not a version manifest. Use `--history-parent` for genuine iteration
  threading.
- **NEVER** edit `.audiogen-history.jsonl` by hand — it is append-only.

## Edge Cases

- **Free-tier 422 with `output_format`** — the CLI appends a hint
  suggesting `--output-format mp3_44100_64`. Follow it.
- **Music loops** — no native API flag. Use engine-side looping or
  craft a `composition_plan` out-of-band.
- **Duplicate voice names** — the cache may contain two "Adam"s (e.g.
  a premade and a cloned one). `--voice-id Adam` will fail with a
  disambiguation error listing both IDs; retry with an ID.
- **20-char voice name** — if a cached voice happens to have a 20-char
  alphanumeric name, the CLI treats it as an ID (passthrough). A
  warning is written to stderr. Rename the voice in ElevenLabs or
  pass the real ID.
- **0-byte 200 response** — the CLI deletes the empty file and
  reports `"empty audio response; refine prompt or retry."`. Treat as
  transient; refine and retry.
- **Non-Latin prompts** — the slug function strips non-`[a-z0-9]`
  characters; if nothing is left, the filename falls back to
  `audio-YYYYMMDD-HHMMSS` (local time zone).
- **Stale voice cache** — cache is 24 h; pass `--refresh` if a
  newly-added voice is not found.
- **`.env` precedence** — shell-exported `ELEVENLABS_API_KEY` wins
  over any `.env` value (Node's default). Unset shell variable if
  you want the `.env` value to take effect.

## Script Location

The CLI lives at `.claude/skills/audiogen/generate.cjs`. It is
dual-shape: as a skill backend (invoked via this SKILL.md), and as a
standalone CLI. Run it directly from any shell for scripting, CI, or
manual experimentation:

    node .claude/skills/audiogen/generate.cjs music "chiptune boss" \
      --length-ms 45000 --output-format mp3_44100_128

All flags work identically in both modes. Run `--help` for the
authoritative flag surface; this file is prose, `generate.cjs --help`
is canon.
