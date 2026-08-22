#!/usr/bin/env node
// audiogen — generate game audio (music, voices, sound effects) via ElevenLabs.
//
// Phase 1: scaffold + shared core. Endpoint logic (runMusic / runTTS / runSFX
// / runVoicesList) is filled in phases 2-4; each currently throws
// "not yet implemented" when reached.
//
// Zero npm deps. Node >= 20.14 required (for process.loadEnvFile).

'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { Readable } = require('node:stream');
const { pipeline } = require('node:stream/promises');

// ────────────────────────────────────────────────────────────────────
// Errors
// ────────────────────────────────────────────────────────────────────

/**
 * Print an error to stderr in the audiogen format and exit 1.
 * Structured details are indented under the summary line.
 *
 * @param {string} msg  One-line summary.
 * @param {object} [details]  Optional key/value lines to print below.
 */
function fail(msg, details) {
  process.stderr.write(`audiogen: ${msg}\n`);
  if (details && typeof details === 'object') {
    for (const [k, v] of Object.entries(details)) {
      if (v === undefined || v === null || v === '') continue;
      process.stderr.write(`  ${k}: ${v}\n`);
    }
  }
  process.exit(1);
}

// ────────────────────────────────────────────────────────────────────
// Env loader
// ────────────────────────────────────────────────────────────────────

/**
 * Locate and load a `.env` file. Mirrors imagegen's env walker verbatim.
 *
 * Candidate list:
 *   1. process.cwd()  (single candidate, NO walk-up from cwd)
 *   2. Every ancestor of __dirname, from __dirname itself up to '/'.
 *
 * Duplicates (cwd may equal an ancestor of __dirname) are deduped.
 * For each candidate `d`, if `<d>/.env` exists, call `process.loadEnvFile`
 * on it in try/catch and return on success (stop walking).
 *
 * Overwrite semantics: Node's `process.loadEnvFile` gives SHELL-EXPORTED
 * values precedence over file values. `ELEVENLABS_API_KEY=X` in the shell
 * overrides `ELEVENLABS_API_KEY=Y` in `.env`. This is Node's default; we
 * do NOT invert it.
 *
 * Node floor: requires Node >= 20.14 (process.loadEnvFile availability).
 * Callers should assert this before invoking loadEnv.
 */
function loadEnv() {
  if (typeof process.loadEnvFile !== 'function') return;

  const candidates = [process.cwd()];
  let d = path.dirname(__filename);
  while (true) {
    candidates.push(d);
    const parent = path.dirname(d);
    if (parent === d) break; // hit filesystem root
    d = parent;
  }
  const seen = new Set();
  for (const c of candidates) {
    if (seen.has(c)) continue;
    seen.add(c);
    const envPath = path.join(c, '.env');
    if (!fs.existsSync(envPath)) continue;
    try {
      process.loadEnvFile(envPath);
      return;
    } catch (_e) {
      // try next candidate; .env may be malformed or unreadable
    }
  }
}

function assertNodeVersion() {
  if (typeof process.loadEnvFile !== 'function') {
    fail(
      `Node.js >= 20.14 required (process.loadEnvFile unavailable on ${process.version})`
    );
  }
}

function assertApiKey() {
  const k = process.env.ELEVENLABS_API_KEY;
  if (!k) {
    fail(
      'ELEVENLABS_API_KEY is not set. Create one at https://elevenlabs.io/app/settings/api-keys and export it, or add it to a .env file in the project root.'
    );
  }
  return k;
}

// ────────────────────────────────────────────────────────────────────
// Slugify + output path
// ────────────────────────────────────────────────────────────────────

function timestampSlug(tz) {
  // YYYYMMDD-HHMMSS in the given IANA timezone (default America/New_York).
  const d = new Date();
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: tz || 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(d);
  const get = (t) => parts.find((p) => p.type === t)?.value ?? '';
  let hh = get('hour');
  if (hh === '24') hh = '00'; // hour12:false can yield 24
  return `audio-${get('year')}${get('month')}${get('day')}-${hh}${get('minute')}${get('second')}`;
}

/**
 * slugify(prompt): first 40 chars → lowercase → collapse non-alphanumeric
 * to `-` → trim leading/trailing `-`. Empty result (common for non-Latin
 * prompts) falls back to `audio-<YYYYMMDD-HHMMSS>`.
 *
 * @param {string} prompt
 * @param {string} [tz]  IANA timezone for empty-slug fallback.
 */
function slugify(prompt, tz) {
  const head = (prompt || '').slice(0, 40).toLowerCase();
  const s = head.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  if (s.length === 0) return timestampSlug(tz);
  return s;
}

function extFromOutputFormat(fmt) {
  if (!fmt || typeof fmt !== 'string') return 'bin';
  if (fmt.startsWith('mp3_')) return 'mp3';
  if (fmt.startsWith('pcm_') || fmt.startsWith('wav_')) return 'wav';
  if (fmt.startsWith('opus_')) return 'opus';
  if (fmt.startsWith('ulaw_') || fmt.startsWith('alaw_')) return 'raw';
  return 'bin';
}

/**
 * resolveOutputPath — picks where to write the generated file.
 *
 * - If `outputOption` is set and names an existing directory (or ends in `/`):
 *       base = <outputOption>/<slug>.<ext>
 * - If `outputOption` is set and is not a directory:
 *       base = <outputOption> verbatim (extension honored as given).
 * - Otherwise:
 *       base = assets/audio/<type>/<slug>.<ext>
 *
 * If `base` does not exist OR `force` is true, return base. Otherwise
 * auto-bump through <prefix>-v2.<ext> … <prefix>-v999.<ext> and return
 * the first non-existent path. If all 999 are taken, fail().
 *
 * @param {object} opts
 * @param {string} opts.type  music | voice | sfx | voices
 * @param {string} opts.prompt
 * @param {string} [opts.outputOption]
 * @param {string} opts.outputFormat
 * @param {boolean} [opts.force]
 * @param {string} [opts.tz]
 */
function resolveOutputPath({ type, prompt, outputOption, outputFormat, force, tz }) {
  const ext = extFromOutputFormat(outputFormat);
  const slug = slugify(prompt, tz);

  let base;
  if (outputOption) {
    const looksLikeDir =
      outputOption.endsWith('/') ||
      (fs.existsSync(outputOption) && fs.statSync(outputOption).isDirectory());
    if (looksLikeDir) {
      base = path.join(outputOption.replace(/\/+$/, ''), `${slug}.${ext}`);
    } else {
      base = outputOption;
    }
  } else {
    base = path.join('assets', 'audio', type, `${slug}.${ext}`);
  }

  if (force || !fs.existsSync(base)) return base;

  // Auto-version: split extension off of `base`.
  const dir = path.dirname(base);
  const baseName = path.basename(base);
  const dot = baseName.lastIndexOf('.');
  const stem = dot > 0 ? baseName.slice(0, dot) : baseName;
  const extOnFile = dot > 0 ? baseName.slice(dot) : '';

  for (let v = 2; v <= 999; v++) {
    const cand = path.join(dir, `${stem}-v${v}${extOnFile}`);
    if (!fs.existsSync(cand)) return cand;
  }
  fail(
    `too many versions for ${base} — clean up ${dir}/ or pass --output explicitly.`
  );
}

function mkdirpParent(outputPath) {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
}

// ────────────────────────────────────────────────────────────────────
// History
// ────────────────────────────────────────────────────────────────────

/**
 * Append one JSON line to `${cwd}/.audiogen-history.jsonl`.
 *
 * On failure, emits a stderr warning and returns. Never throws — history
 * is best-effort and must not abort the generation.
 *
 * @param {object} record
 * @param {(path: string, data: string) => void} [writeFn]  Injectable for tests.
 */
function appendHistory(record, writeFn = fs.appendFileSync) {
  const line = JSON.stringify(record) + '\n';
  const target = path.join(process.cwd(), '.audiogen-history.jsonl');
  try {
    writeFn(target, line);
  } catch (e) {
    process.stderr.write(
      `audiogen: warning — failed to append history (${e && e.message ? e.message : e}); continuing.\n`
    );
  }
}

// ────────────────────────────────────────────────────────────────────
// CLI arg parser
// ────────────────────────────────────────────────────────────────────

const SUBCOMMANDS = new Set(['music', 'voice', 'sfx', 'voices']);

// Flag registry. For each flag: { value: true } means it consumes the next
// token; { value: false } is boolean (no value).
const FLAG_SPECS = {
  // Common
  '--output': { value: true, key: 'output' },
  '--output-format': { value: true, key: 'outputFormat' },
  '--seed': { value: true, key: 'seed' },
  '--model-id': { value: true, key: 'modelId' },
  '--dry-run': { value: false, key: 'dryRun' },
  '--force': { value: false, key: 'force' },
  '--history-id': { value: true, key: 'historyId' },
  '--history-parent': { value: true, key: 'historyParent' },
  '--help': { value: false, key: 'help' },
  // Music
  '--length-ms': { value: true, key: 'lengthMs' },
  '--force-instrumental': { value: false, key: 'forceInstrumental' },
  // Voice
  '--voice-id': { value: true, key: 'voiceId' },
  '--language-code': { value: true, key: 'languageCode' },
  '--stability': { value: true, key: 'stability' },
  '--similarity-boost': { value: true, key: 'similarityBoost' },
  '--style': { value: true, key: 'style' },
  '--speed': { value: true, key: 'speed' },
  // SFX
  '--duration': { value: true, key: 'duration' },
  '--loop': { value: false, key: 'loop' },
  '--prompt-influence': { value: true, key: 'promptInfluence' },
  // Voices
  '--language': { value: true, key: 'language' },
  '--gender': { value: true, key: 'gender' },
  '--accent': { value: true, key: 'accent' },
  '--category': { value: true, key: 'category' },
  '--json': { value: false, key: 'json' },
  '--refresh': { value: false, key: 'refresh' },
  '--page-size': { value: true, key: 'pageSize' },
  '--limit': { value: true, key: 'limit' },
};

/**
 * Parse argv (already sliced past `node generate.cjs`).
 *
 * Throws {message, exitCode} for usage errors so callers may print usage.
 * Does not read env or touch disk.
 *
 * Result shape:
 *   { subcommand, positionals: [...], flags: {...}, help: bool }
 *
 * If `--help` appears anywhere, returns { help: true } (subcommand is
 * optional).
 *
 * @param {string[]} argv
 */
function parseArgs(argv) {
  const flags = {};
  const positionals = [];
  const tokens = argv.slice();

  // --help first-pass: allow anywhere.
  if (tokens.includes('--help')) {
    return { help: true, subcommand: null, positionals: [], flags: { help: true } };
  }

  while (tokens.length > 0) {
    const t = tokens.shift();
    if (t === '--') {
      // remaining tokens are positional
      for (const rest of tokens) positionals.push(rest);
      break;
    }
    if (t.startsWith('--')) {
      const spec = FLAG_SPECS[t];
      if (!spec) {
        const err = new Error(`unknown flag: ${t}`);
        err.usage = true;
        throw err;
      }
      if (spec.value) {
        if (tokens.length === 0) {
          const err = new Error(`flag ${t} requires a value`);
          err.usage = true;
          throw err;
        }
        flags[spec.key] = tokens.shift();
      } else {
        flags[spec.key] = true;
      }
    } else {
      positionals.push(t);
    }
  }

  if (positionals.length === 0) {
    const err = new Error('missing subcommand (expected one of music|voice|sfx|voices)');
    err.usage = true;
    throw err;
  }

  const subcommand = positionals.shift();
  if (!SUBCOMMANDS.has(subcommand)) {
    const err = new Error(
      `unknown subcommand: ${subcommand} (expected one of music|voice|sfx|voices)`
    );
    err.usage = true;
    throw err;
  }

  return { help: false, subcommand, positionals, flags };
}

// ────────────────────────────────────────────────────────────────────
// Help
// ────────────────────────────────────────────────────────────────────

const HELP_TEXT = `audiogen — generate game audio via ElevenLabs

Usage:
  node generate.cjs <subcommand> [prompt_or_query_words...] [options]

Subcommands:
  music  <prompt...>         Generate a music track.
  voice  <text...>           Generate TTS audio; requires --voice-id.
  sfx    <prompt...>         Generate a sound effect.
  voices [query...]          List/search voices; populates local cache.

Common options:
  --output PATH              Explicit output path or directory.
  --output-format FMT        Default mp3_44100_128.
  --seed N                   Integer seed (where supported).
  --model-id ID              Override the endpoint's default model.
  --dry-run                  Print resolved request + output path; no network.
  --force                    Overwrite existing output file (disables auto-version).
  --history-id ID            Group-tag for iteration threads.
  --history-parent ID        Parent record's id; marks this as a derivative.
  --help                     Show usage.

Music-only:
  --length-ms MS             3000-600000. Default 30000.
  --force-instrumental       No vocals.

Voice-only:
  --voice-id ID_OR_NAME      Required. Exact name in cache (case-insensitive),
                              or 20-char alphanumeric voice-id passthrough.
  --language-code CODE       e.g. en, ja.
  --stability N              0-1.
  --similarity-boost N       0-1.
  --style N                  0-1.
  --speed N                  0.5-2.

SFX-only:
  --duration N               0.5-30 seconds. Optional (API auto-derives).
  --loop                     Native API flag (v2 model only).
  --prompt-influence N       0-1. Default 0.3.

Voices-only:
  --language CODE            Filter by language.
  --gender male|female       Filter.
  --accent STR               Substring match on accent labels.
  --category STR             e.g. premade, cloned, professional.
  --json                     Emit raw JSON instead of table.
  --refresh                  Ignore cache, re-fetch.
  --page-size N              Override pagination page size (default 100, max 100).
  --limit N                  Cap table output rows (default 50, JSON ignores).
`;

function printHelp() {
  process.stdout.write(HELP_TEXT);
}

// ────────────────────────────────────────────────────────────────────
// HTTP helper (ElevenLabs)
// ────────────────────────────────────────────────────────────────────

const RETRY_STATUSES = new Set([429, 500, 502, 503]);
const BASE_URL = 'https://api.elevenlabs.io';

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function parseRetryAfter(header) {
  if (!header) return null;
  const n = Number(header);
  if (Number.isFinite(n) && n >= 0) return Math.min(n, 30) * 1000;
  // HTTP-date form
  const dateMs = Date.parse(header);
  if (!Number.isNaN(dateMs)) {
    const wait = Math.max(0, dateMs - Date.now());
    return Math.min(wait, 30_000);
  }
  return null;
}

async function parseErrorBody(response) {
  const raw = await response.text();
  let message = raw;
  try {
    const obj = JSON.parse(raw);
    message =
      (obj && obj.detail && typeof obj.detail === 'object' && obj.detail.message) ||
      (obj && typeof obj.detail === 'string' && obj.detail) ||
      (obj && obj.message) ||
      raw;
  } catch (_e) {
    // leave as raw
  }
  return { message: (message || '').slice(0, 2000), raw };
}

/**
 * callElevenLabs — central HTTP helper.
 *
 * Retry: 3 attempts on 429/500/502/503. Backoff 1000ms * 2^(n-1) + up to
 * 500ms jitter. 429 honors Retry-After (clamped to 30s). 120s abort
 * per attempt via AbortSignal.timeout.
 *
 * Non-retryable (400/401/402/403/404/413/422) goes through fail(); 422
 * mentioning `output_format` appends the free-tier hint.
 *
 * responseType:
 *   'binary' — stream body to outputPath; fail on 0-byte response.
 *   'json'   — parse and return the object; outputPath ignored.
 *
 * @param {object} opts
 * @param {string} [opts.method]  default 'POST'
 * @param {string} opts.path
 * @param {Record<string,string>} [opts.query]
 * @param {object} [opts.body]
 * @param {string} [opts.outputPath]
 * @param {'binary'|'json'} [opts.responseType]  default 'binary'
 * @param {typeof fetch} [opts.fetchImpl]  injectable for tests
 * @returns {Promise<{ requestId?: string, bytesWritten?: number, json?: any }>}
 */
async function callElevenLabs(opts) {
  const {
    method = 'POST',
    path: urlPath,
    query,
    body,
    outputPath,
    responseType = 'binary',
    fetchImpl = fetch,
  } = opts;

  assertApiKey();
  const key = process.env.ELEVENLABS_API_KEY;

  const qs = query
    ? '?' +
      Object.entries(query)
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
        .join('&')
    : '';
  const url = `${BASE_URL}${urlPath}${qs}`;

  const init = {
    method,
    headers: {
      'xi-api-key': key,
      'content-type': 'application/json',
    },
  };
  if (body !== undefined) init.body = JSON.stringify(body);

  let lastErr = null;
  for (let attempt = 1; attempt <= 3; attempt++) {
    const signal = AbortSignal.timeout(120_000);
    let response;
    try {
      response = await fetchImpl(url, { ...init, signal });
    } catch (e) {
      lastErr = e;
      if (attempt >= 3) {
        fail(`network error after 3 attempts: ${e && e.message ? e.message : e}`, {
          endpoint: `${method} ${url}`,
        });
      }
      await sleep(1000 * 2 ** (attempt - 1) + Math.floor(Math.random() * 500));
      continue;
    }

    if (RETRY_STATUSES.has(response.status) && attempt < 3) {
      const retryAfter =
        response.status === 429 ? parseRetryAfter(response.headers.get('retry-after')) : null;
      const backoff =
        retryAfter !== null
          ? retryAfter
          : 1000 * 2 ** (attempt - 1) + Math.floor(Math.random() * 500);
      // drain body to free connection
      try {
        await response.text();
      } catch (_e) {}
      await sleep(backoff);
      continue;
    }

    const requestId = response.headers.get('xi-request-id') || undefined;

    if (!response.ok) {
      const { message } = await parseErrorBody(response);
      const details = {
        endpoint: `${method} ${url}`,
        status: `${response.status} ${response.statusText || ''}`.trim(),
        detail: message,
        'request-id': requestId,
      };
      if (
        response.status === 422 &&
        typeof message === 'string' &&
        /output_format/i.test(message)
      ) {
        details.hint =
          'Free-tier accounts are restricted to mp3_44100_64. Try --output-format mp3_44100_64.';
      }
      fail(`ElevenLabs request failed (${response.status})`, details);
    }

    if (responseType === 'json') {
      const raw = await response.text();
      try {
        return { requestId, json: JSON.parse(raw) };
      } catch (e) {
        fail(`unexpected non-JSON success body: ${raw.slice(0, 500)}`, {
          endpoint: `${method} ${url}`,
          'request-id': requestId,
          parse: e && e.message,
        });
      }
    }

    // binary
    const ct = response.headers.get('content-type') || '';
    if (/application\/json/i.test(ct)) {
      const raw = await response.text();
      fail(`unexpected JSON success body: ${raw.slice(0, 500)}`, {
        endpoint: `${method} ${url}`,
        'request-id': requestId,
      });
    }
    if (!outputPath) {
      fail('internal error: binary response requires outputPath');
    }
    mkdirpParent(outputPath);
    const ws = fs.createWriteStream(outputPath);
    await pipeline(Readable.fromWeb(response.body), ws);
    const stat = fs.statSync(outputPath);
    if (stat.size === 0) {
      try {
        fs.unlinkSync(outputPath);
      } catch (_e) {}
      fail('empty audio response; refine prompt or retry.', {
        endpoint: `${method} ${url}`,
        'request-id': requestId,
      });
    }
    return { requestId, bytesWritten: stat.size };
  }

  // Exhausted retries with retryable statuses.
  fail(`request failed after 3 attempts`, {
    endpoint: `${method} ${url}`,
    detail: lastErr && lastErr.message,
  });
}

// ────────────────────────────────────────────────────────────────────
// Music subcommand
// ────────────────────────────────────────────────────────────────────

// Music endpoint supports mp3_*, pcm_*, opus_*, ulaw_8000, alaw_8000.
// Explicitly excludes wav_*.
const MUSIC_OUTPUT_FORMAT_RE =
  /^(mp3_\d+_\d+|pcm_\d+|opus_\d+_\d+|ulaw_8000|alaw_8000)$/;

const MUSIC_LENGTH_MIN_MS = 3000;
const MUSIC_LENGTH_MAX_MS = 600000;
const MUSIC_LENGTH_DEFAULT_MS = 30000;

const MUSIC_LOOP_REJECT_MSG =
  'Music loops are not supported. Loop playback in your engine / HTML audio.';
const MUSIC_WAV_REJECT_MSG =
  'Music endpoint does not support WAV output. Use mp3_* or pcm_*.';

/**
 * Validate and normalize music-subcommand options. Throws via fail() on any
 * pre-network error. Returns an object with resolved inputs.
 *
 * @param {object} parsed  Output of parseArgs.
 * @returns {{prompt: string, outputFormat: string, musicLengthMs: number,
 *           forceInstrumental: boolean, seed: number|undefined}}
 */
function validateMusicOptions(parsed) {
  const { flags, positionals } = parsed;

  // --loop: reject music-side loops before anything else.
  if (flags.loop) {
    fail(MUSIC_LOOP_REJECT_MSG);
  }

  // --output-format: validate against music regex, reject wav explicitly.
  const outputFormat = flags.outputFormat || 'mp3_44100_128';
  if (typeof outputFormat === 'string' && /^wav_/i.test(outputFormat)) {
    fail(MUSIC_WAV_REJECT_MSG);
  }
  if (!MUSIC_OUTPUT_FORMAT_RE.test(outputFormat)) {
    fail(
      `invalid --output-format "${outputFormat}" for music. Expected mp3_<rate>_<br>, pcm_<rate>, opus_<rate>_<br>, ulaw_8000, or alaw_8000.`
    );
  }

  // --length-ms: integer in [3000, 600000]; default 30000.
  let musicLengthMs = MUSIC_LENGTH_DEFAULT_MS;
  if (flags.lengthMs !== undefined) {
    const raw = String(flags.lengthMs);
    if (!/^-?\d+$/.test(raw)) {
      fail(`--length-ms must be an integer; got "${flags.lengthMs}".`);
    }
    musicLengthMs = Number(raw);
    if (!Number.isFinite(musicLengthMs)) {
      fail(`--length-ms must be an integer; got "${flags.lengthMs}".`);
    }
  }
  if (
    musicLengthMs < MUSIC_LENGTH_MIN_MS ||
    musicLengthMs > MUSIC_LENGTH_MAX_MS
  ) {
    fail(
      `music_length_ms must be in [${MUSIC_LENGTH_MIN_MS}, ${MUSIC_LENGTH_MAX_MS}]; got ${musicLengthMs}.`
    );
  }

  // --seed: optional integer.
  let seed;
  if (flags.seed !== undefined) {
    const raw = String(flags.seed);
    if (!/^-?\d+$/.test(raw)) {
      fail(`--seed must be an integer; got "${flags.seed}".`);
    }
    seed = Number(raw);
    if (!Number.isFinite(seed)) {
      fail(`--seed must be an integer; got "${flags.seed}".`);
    }
  }

  // prompt: non-empty after trim.
  const prompt = positionals.join(' ').trim();
  if (prompt.length === 0) {
    fail('music subcommand requires a non-empty prompt.');
  }

  return {
    prompt,
    outputFormat,
    musicLengthMs,
    forceInstrumental: !!flags.forceInstrumental,
    seed,
  };
}

/**
 * Build the music request URL + body. Pure function (no fs, no network).
 *
 * @param {object} opts
 * @param {string} opts.prompt
 * @param {string} opts.outputFormat
 * @param {number} opts.musicLengthMs
 * @param {boolean} opts.forceInstrumental
 * @param {number} [opts.seed]
 * @returns {{url: string, body: object}}
 */
function buildMusicRequest({
  prompt,
  outputFormat,
  musicLengthMs,
  forceInstrumental,
  seed,
}) {
  const url = `${BASE_URL}/v1/music?output_format=${encodeURIComponent(outputFormat)}`;
  const body = {
    prompt,
    music_length_ms: musicLengthMs,
  };
  if (forceInstrumental) body.force_instrumental = true;
  if (seed !== undefined) body.seed = seed;
  return { url, body };
}

/**
 * runMusic — implement the `music` subcommand end-to-end.
 *
 * Validates flags (pre-network), builds the request, resolves the output
 * path, and either prints a dry-run block or POSTs to /v1/music and streams
 * the response to disk. On success, appends one history record and prints
 * the output path.
 *
 * @param {object} parsed  parseArgs result.
 * @param {object} [deps]  Injectable dependencies for tests.
 * @param {typeof fetch} [deps.fetchImpl]
 * @param {(record: object, writeFn?: Function) => void} [deps.appendHistoryFn]
 * @param {(path: string, data: string) => void} [deps.writeHistoryFn]
 * @param {NodeJS.WritableStream} [deps.stdout]
 */
async function runMusic(parsed, deps = {}) {
  const {
    fetchImpl,
    appendHistoryFn = appendHistory,
    writeHistoryFn,
    stdout = process.stdout,
  } = deps;

  const { flags } = parsed;
  const opts = validateMusicOptions(parsed);

  const { url, body } = buildMusicRequest(opts);

  const outputPath = resolveOutputPath({
    type: 'music',
    prompt: opts.prompt,
    outputOption: flags.output,
    outputFormat: opts.outputFormat,
    force: !!flags.force,
    tz: 'America/New_York',
  });

  if (flags.dryRun) {
    stdout.write('audiogen dry-run (music)\n');
    stdout.write(`  url: ${url}\n`);
    stdout.write(`  body: ${JSON.stringify(body)}\n`);
    stdout.write(`  output: ${outputPath}\n`);
    return { url, body, outputPath, dryRun: true };
  }

  // Live call.
  const callOpts = {
    method: 'POST',
    path: '/v1/music',
    query: { output_format: opts.outputFormat },
    body,
    outputPath,
    responseType: 'binary',
  };
  if (fetchImpl) callOpts.fetchImpl = fetchImpl;

  const result = await callElevenLabs(callOpts);

  // History record — best-effort; failures surface as stderr warnings only.
  const record = {
    ts: new Date().toISOString(),
    type: 'music',
    phase: 'music',
    prompt: opts.prompt,
    music_length_ms: opts.musicLengthMs,
    output_format: opts.outputFormat,
    output_path: outputPath,
    model_id: flags.modelId || 'music_v1 (server default)',
  };
  if (opts.forceInstrumental) record.force_instrumental = true;
  if (opts.seed !== undefined) record.seed = opts.seed;
  if (flags.historyId) record.history_id = flags.historyId;
  if (flags.historyParent) record.parent_id = flags.historyParent;
  if (result && result.requestId) record.request_id = result.requestId;
  if (result && result.bytesWritten) record.bytes = result.bytesWritten;

  if (writeHistoryFn) {
    appendHistoryFn(record, writeHistoryFn);
  } else {
    appendHistoryFn(record);
  }

  stdout.write(`${outputPath}\n`);
  return { url, body, outputPath, dryRun: false, result };
}

// ────────────────────────────────────────────────────────────────────
// Voice (TTS) subcommand
// ────────────────────────────────────────────────────────────────────

const VOICE_ID_RE = /^[A-Za-z0-9]{20}$/;
const VOICE_TEXT_MAX_LEN = 40000;
const VOICE_DEFAULT_MODEL_ID = 'eleven_multilingual_v2';
const VOICE_DEFAULT_OUTPUT_FORMAT = 'mp3_44100_128';

// Voice accepts any of the standard audio output-format families, including WAV.
const VOICE_OUTPUT_FORMAT_RE =
  /^(mp3_\d+_\d+|pcm_\d+|opus_\d+_\d+|ulaw_\d+|alaw_\d+|wav_\d+)$/;

/**
 * Resolve a `--voice` / `--voice-id` input to a concrete ElevenLabs
 * voice_id. Cache-first lookup by name (case-insensitive exact match),
 * then ID passthrough.
 *
 * Throws {code, message, matches?} — callers translate to fail() or warn.
 * On success, returns `{ voiceId, voiceName, shadowWarning? }`.
 *
 *   rawInput      - user input (trimmed inside).
 *   cachePath     - absolute path to `.audiogen-voices.json`.
 *   readFileFn    - injectable fs.readFileSync (defaults to real fs).
 *   existsFn      - injectable fs.existsSync.
 *
 * Spec:
 *   0. input = rawInput.trim()
 *   1. undefined/empty → fail "Voice generation requires --voice-id…"
 *   2. If cache missing AND not a plausible voice-id (/^[A-Za-z0-9]{20}$/)
 *      → fail "No voice cache. Run: node generate.cjs voices"
 *   3. If cache readable, find voices whose name equals input
 *      (case-insensitive):
 *       - 1 match → return its voice_id. If input also matches ID regex,
 *         include a `shadowWarning` describing the cache-first
 *         precedence.
 *       - multiple matches → fail with disambiguation block.
 *       - 0 matches → step 3b.
 *   3b. Prefix match against names (case-insensitive), requiring a
 *       word-boundary follower (space / dash / comma) so "Alice" matches
 *       "Alice - Clear, Engaging Educator" but "Ali" doesn't match "Alice":
 *       - 1 match → return its voice_id (with shadowWarning if input is
 *         also ID-shaped).
 *       - multiple matches → fail with disambiguation block.
 *       - 0 matches → step 4.
 *   4. If input matches ID regex → return input verbatim.
 *      Else → fail "No voice named '<input>' in cache…"
 */
function resolveVoiceId(rawInput, cachePath, deps = {}) {
  const readFileFn = deps.readFileFn || ((p) => fs.readFileSync(p, 'utf8'));
  const existsFn = deps.existsFn || ((p) => fs.existsSync(p));

  const input = typeof rawInput === 'string' ? rawInput.trim() : '';
  if (!input) {
    const err = new Error(
      'Voice generation requires --voice-id. Browse: node generate.cjs voices [query]'
    );
    err.code = 'VOICE_ID_REQUIRED';
    throw err;
  }

  let cache = null;
  if (existsFn(cachePath)) {
    let raw;
    try {
      raw = readFileFn(cachePath);
    } catch (_e) {
      raw = null;
    }
    if (raw != null) {
      try {
        cache = JSON.parse(raw);
      } catch (_e) {
        cache = null;
      }
    }
  }

  const isIdPattern = VOICE_ID_RE.test(input);

  if (!cache || !Array.isArray(cache.voices)) {
    if (!isIdPattern) {
      const err = new Error('No voice cache. Run: node generate.cjs voices');
      err.code = 'NO_CACHE';
      throw err;
    }
    // cache missing + ID passthrough
    return { voiceId: input, voiceName: undefined };
  }

  const lower = input.toLowerCase();
  const matches = cache.voices.filter(
    (v) => v && typeof v.name === 'string' && v.name.toLowerCase() === lower
  );

  if (matches.length === 1) {
    const hit = matches[0];
    const out = { voiceId: hit.voice_id, voiceName: hit.name };
    if (isIdPattern) {
      out.shadowWarning =
        `audiogen: '${input}' matches both a voice-id pattern and a cached voice name; ` +
        `resolving as the cached name's voice_id. If you intended the raw ID, rename the ` +
        `conflicting voice or pass a different voice.`;
    }
    return out;
  }

  if (matches.length > 1) {
    const err = new Error(
      `Multiple cached voices named "${input}". Pass the ID directly: --voice-id <id>`
    );
    err.code = 'DISAMBIGUATION';
    err.matches = matches.map((v) => ({
      voice_id: v.voice_id,
      name: v.name,
      category: v.category,
      labels: v.labels || {},
    }));
    throw err;
  }

  // Prefix match fallback — ElevenLabs names are "FirstName - Description",
  // so exact match on "Alice" never hits. Require a word-boundary follower
  // (space / dash / comma) so "Ali" doesn't greedily match "Alice".
  const prefixMatches = cache.voices.filter((v) => {
    if (!v || typeof v.name !== 'string') return false;
    const nameLower = v.name.toLowerCase();
    if (nameLower === lower) return false; // handled above
    if (!nameLower.startsWith(lower)) return false;
    const next = nameLower.charAt(lower.length);
    return next === ' ' || next === '-' || next === ',';
  });

  if (prefixMatches.length === 1) {
    const hit = prefixMatches[0];
    const out = { voiceId: hit.voice_id, voiceName: hit.name };
    if (isIdPattern) {
      out.shadowWarning =
        `audiogen: '${input}' matches both a voice-id pattern and a cached voice name prefix; ` +
        `resolving as '${hit.name}'. If you intended the raw ID, rename the conflicting voice.`;
    }
    return out;
  }

  if (prefixMatches.length > 1) {
    const err = new Error(
      `Multiple cached voices match prefix "${input}". Pass the full name or ID: --voice-id <id>`
    );
    err.code = 'DISAMBIGUATION';
    err.matches = prefixMatches.map((v) => ({
      voice_id: v.voice_id,
      name: v.name,
      category: v.category,
      labels: v.labels || {},
    }));
    throw err;
  }

  // zero exact + zero prefix matches
  if (isIdPattern) {
    return { voiceId: input, voiceName: undefined };
  }
  const err = new Error(
    `No voice named '${input}' in cache and input is not a 20-char voice-id. Try --refresh.`
  );
  err.code = 'NO_MATCH';
  throw err;
}

/**
 * Validate and normalize voice-subcommand options. Uses fail() on any
 * pre-network error.
 *
 * Returns:
 *   { text, voiceId, voiceName?, shadowWarning?, outputFormat, modelId,
 *     languageCode?, voiceSettings?, seed?, rawVoiceInput }
 */
function validateVoiceOptions(parsed, deps = {}) {
  const { flags, positionals } = parsed;

  // Output format: default mp3; WAV allowed for voice.
  const outputFormat = flags.outputFormat || VOICE_DEFAULT_OUTPUT_FORMAT;
  if (!VOICE_OUTPUT_FORMAT_RE.test(outputFormat)) {
    fail(
      `invalid --output-format "${outputFormat}" for voice. Expected mp3_<rate>_<br>, pcm_<rate>, wav_<rate>, opus_<rate>_<br>, ulaw_<rate>, or alaw_<rate>.`
    );
  }

  // Text: join positionals, trim, enforce length cap.
  const text = positionals.join(' ').trim();
  if (text.length === 0) {
    fail('voice subcommand requires non-empty text.');
  }
  if (text.length > VOICE_TEXT_MAX_LEN) {
    fail(
      `voice text is ${text.length} chars; max is ${VOICE_TEXT_MAX_LEN}. Split into smaller requests.`
    );
  }

  // Voice id/name resolution.
  const rawVoiceInput = flags.voiceId;
  const cachePath = deps.cachePath || path.join(process.cwd(), '.audiogen-voices.json');
  let resolved;
  try {
    resolved = resolveVoiceId(rawVoiceInput, cachePath, deps.resolveDeps);
  } catch (e) {
    if (e && e.code === 'DISAMBIGUATION') {
      const details = {};
      for (const m of e.matches || []) {
        const lbl = m.labels || {};
        const lblParts = [];
        if (lbl.accent) lblParts.push(`accent=${lbl.accent}`);
        if (lbl.gender) lblParts.push(`gender=${lbl.gender}`);
        if (lbl.age) lblParts.push(`age=${lbl.age}`);
        if (lbl.language) lblParts.push(`language=${lbl.language}`);
        const cat = m.category ? ` [${m.category}]` : '';
        const labelSuffix = lblParts.length ? `  (${lblParts.join(', ')})` : '';
        details[m.voice_id] = `${m.name}${cat}${labelSuffix}`;
      }
      fail(e.message, details);
    }
    fail(e && e.message ? e.message : String(e));
  }

  // Optional integer seed.
  let seed;
  if (flags.seed !== undefined) {
    const raw = String(flags.seed);
    if (!/^-?\d+$/.test(raw)) {
      fail(`--seed must be an integer; got "${flags.seed}".`);
    }
    seed = Number(raw);
    if (!Number.isFinite(seed)) {
      fail(`--seed must be an integer; got "${flags.seed}".`);
    }
  }

  // Voice settings (only user-specified fields).
  const vs = {};
  const numericFlag = (flag, key, min, max) => {
    if (flags[flag] === undefined) return;
    const n = Number(flags[flag]);
    if (!Number.isFinite(n)) {
      fail(`--${flag.replace(/([A-Z])/g, '-$1').toLowerCase()} must be a number; got "${flags[flag]}".`);
    }
    if (n < min || n > max) {
      fail(`--${flag.replace(/([A-Z])/g, '-$1').toLowerCase()} must be in [${min}, ${max}]; got ${n}.`);
    }
    vs[key] = n;
  };
  numericFlag('stability', 'stability', 0, 1);
  numericFlag('similarityBoost', 'similarity_boost', 0, 1);
  numericFlag('style', 'style', 0, 1);
  numericFlag('speed', 'speed', 0.5, 2);

  const modelId = flags.modelId || VOICE_DEFAULT_MODEL_ID;

  const out = {
    text,
    voiceId: resolved.voiceId,
    voiceName: resolved.voiceName,
    shadowWarning: resolved.shadowWarning,
    outputFormat,
    modelId,
    rawVoiceInput: typeof rawVoiceInput === 'string' ? rawVoiceInput.trim() : rawVoiceInput,
  };
  if (flags.languageCode) out.languageCode = flags.languageCode;
  if (Object.keys(vs).length > 0) out.voiceSettings = vs;
  if (seed !== undefined) out.seed = seed;
  return out;
}

/**
 * Build the voice TTS request URL + body. Pure function.
 */
function buildVoiceRequest(opts) {
  const url =
    `${BASE_URL}/v1/text-to-speech/${encodeURIComponent(opts.voiceId)}` +
    `?output_format=${encodeURIComponent(opts.outputFormat)}`;
  const body = {
    text: opts.text,
    model_id: opts.modelId,
  };
  if (opts.languageCode) body.language_code = opts.languageCode;
  if (opts.voiceSettings) body.voice_settings = opts.voiceSettings;
  if (opts.seed !== undefined) body.seed = opts.seed;
  return { url, body };
}

async function runTTS(parsed, deps = {}) {
  const {
    fetchImpl,
    appendHistoryFn = appendHistory,
    writeHistoryFn,
    stdout = process.stdout,
    stderr = process.stderr,
    cachePath,
    resolveDeps,
  } = deps;

  const opts = validateVoiceOptions(parsed, { cachePath, resolveDeps });

  if (opts.shadowWarning) {
    stderr.write(`${opts.shadowWarning}\n`);
  }

  const { url, body } = buildVoiceRequest(opts);

  const { flags } = parsed;
  const outputPath = resolveOutputPath({
    type: 'voice',
    prompt: opts.text,
    outputOption: flags.output,
    outputFormat: opts.outputFormat,
    force: !!flags.force,
    tz: 'America/New_York',
  });

  if (flags.dryRun) {
    stdout.write('audiogen dry-run (voice)\n');
    stdout.write(`  url: ${url}\n`);
    stdout.write(`  body: ${JSON.stringify(body)}\n`);
    stdout.write(`  output: ${outputPath}\n`);
    return { url, body, outputPath, dryRun: true };
  }

  const callOpts = {
    method: 'POST',
    path: `/v1/text-to-speech/${encodeURIComponent(opts.voiceId)}`,
    query: { output_format: opts.outputFormat },
    body,
    outputPath,
    responseType: 'binary',
  };
  if (fetchImpl) callOpts.fetchImpl = fetchImpl;

  const result = await callElevenLabs(callOpts);

  const record = {
    ts: new Date().toISOString(),
    type: 'voice',
    phase: 'voice',
    voice_id: opts.voiceId,
    text: opts.text,
    model_id: opts.modelId,
    output_format: opts.outputFormat,
    output_path: outputPath,
  };
  if (opts.voiceName) record.voice_name = opts.voiceName;
  if (opts.languageCode) record.language_code = opts.languageCode;
  if (opts.voiceSettings) record.voice_settings = opts.voiceSettings;
  if (opts.seed !== undefined) record.seed = opts.seed;
  if (flags.historyId) record.history_id = flags.historyId;
  if (flags.historyParent) record.parent_id = flags.historyParent;
  if (result && result.requestId) record.request_id = result.requestId;
  if (result && result.bytesWritten) record.bytes = result.bytesWritten;

  if (writeHistoryFn) {
    appendHistoryFn(record, writeHistoryFn);
  } else {
    appendHistoryFn(record);
  }

  stdout.write(`${outputPath}\n`);
  return { url, body, outputPath, dryRun: false, result };
}

// ────────────────────────────────────────────────────────────────────
// SFX (sound-generation) subcommand
// ────────────────────────────────────────────────────────────────────

// Sound-generation endpoint supports mp3_*, pcm_*, opus_*, ulaw_8000, alaw_8000.
// Explicitly excludes wav_* (matches music endpoint's family support).
const SFX_OUTPUT_FORMAT_RE =
  /^(mp3_\d+_\d+|pcm_\d+|opus_\d+_\d+|ulaw_8000|alaw_8000)$/;

const SFX_DURATION_MIN_S = 0.5;
const SFX_DURATION_MAX_S = 30;
const SFX_PROMPT_INFLUENCE_DEFAULT = 0.3;
const SFX_PROMPT_INFLUENCE_MIN = 0;
const SFX_PROMPT_INFLUENCE_MAX = 1;
const SFX_DEFAULT_MODEL_ID = 'eleven_text_to_sound_v2';
const SFX_DEFAULT_OUTPUT_FORMAT = 'mp3_44100_128';

const SFX_WAV_REJECT_MSG =
  'Sound-generation endpoint does not support WAV output. Use mp3_* or pcm_*.';
const SFX_LOOP_MODEL_REJECT_MSG =
  '--loop is only supported by eleven_text_to_sound_v2.';

/**
 * Validate and normalize sfx-subcommand options. Uses fail() on any
 * pre-network error. Returns an object with resolved inputs.
 *
 * @param {object} parsed  parseArgs result.
 * @returns {{text: string, outputFormat: string, modelId: string,
 *           promptInfluence: number, loop: boolean,
 *           durationSeconds?: number}}
 */
function validateSFXOptions(parsed) {
  const { flags, positionals } = parsed;

  // --output-format: default mp3; reject wav_*; validate family.
  const outputFormat = flags.outputFormat || SFX_DEFAULT_OUTPUT_FORMAT;
  if (typeof outputFormat === 'string' && /^wav_/i.test(outputFormat)) {
    fail(SFX_WAV_REJECT_MSG);
  }
  if (!SFX_OUTPUT_FORMAT_RE.test(outputFormat)) {
    fail(
      `invalid --output-format "${outputFormat}" for sfx. Expected mp3_<rate>_<br>, pcm_<rate>, opus_<rate>_<br>, ulaw_8000, or alaw_8000.`
    );
  }

  // text: non-empty after trim (required by the endpoint).
  const text = positionals.join(' ').trim();
  if (text.length === 0) {
    fail('sfx subcommand requires non-empty text.');
  }

  // --duration: optional finite number in [0.5, 30].
  let durationSeconds;
  if (flags.duration !== undefined) {
    const n = Number(flags.duration);
    if (!Number.isFinite(n)) {
      fail(
        `--duration must be a number in [${SFX_DURATION_MIN_S}, ${SFX_DURATION_MAX_S}]; got "${flags.duration}".`
      );
    }
    if (n < SFX_DURATION_MIN_S || n > SFX_DURATION_MAX_S) {
      fail(
        `--duration must be in [${SFX_DURATION_MIN_S}, ${SFX_DURATION_MAX_S}]; got ${n}.`
      );
    }
    durationSeconds = n;
  }

  // --prompt-influence: optional finite number in [0, 1]; default 0.3.
  let promptInfluence = SFX_PROMPT_INFLUENCE_DEFAULT;
  if (flags.promptInfluence !== undefined) {
    const n = Number(flags.promptInfluence);
    if (!Number.isFinite(n)) {
      fail(
        `--prompt-influence must be a number in [${SFX_PROMPT_INFLUENCE_MIN}, ${SFX_PROMPT_INFLUENCE_MAX}]; got "${flags.promptInfluence}".`
      );
    }
    if (n < SFX_PROMPT_INFLUENCE_MIN || n > SFX_PROMPT_INFLUENCE_MAX) {
      fail(
        `--prompt-influence must be in [${SFX_PROMPT_INFLUENCE_MIN}, ${SFX_PROMPT_INFLUENCE_MAX}]; got ${n}.`
      );
    }
    promptInfluence = n;
  }

  // --model-id: default to v2.
  const modelId = flags.modelId || SFX_DEFAULT_MODEL_ID;

  // --loop + non-v2 model combination is rejected.
  const loop = !!flags.loop;
  if (loop && modelId !== SFX_DEFAULT_MODEL_ID) {
    fail(SFX_LOOP_MODEL_REJECT_MSG);
  }

  const out = {
    text,
    outputFormat,
    modelId,
    promptInfluence,
    loop,
  };
  if (durationSeconds !== undefined) out.durationSeconds = durationSeconds;
  return out;
}

/**
 * Build the sfx request URL + body. Pure function (no fs, no network).
 *
 * Body always includes: text, model_id, prompt_influence.
 * Body conditionally includes: duration_seconds (if set), loop (if true).
 *
 * @param {object} opts
 * @returns {{url: string, body: object}}
 */
function buildSFXRequest({ text, outputFormat, modelId, promptInfluence, loop, durationSeconds }) {
  const url =
    `${BASE_URL}/v1/sound-generation?output_format=${encodeURIComponent(outputFormat)}`;
  const body = {
    text,
    model_id: modelId,
    prompt_influence: promptInfluence,
  };
  if (durationSeconds !== undefined) body.duration_seconds = durationSeconds;
  if (loop) body.loop = true;
  return { url, body };
}

/**
 * runSFX — implement the `sfx` subcommand end-to-end.
 *
 * Validates flags (pre-network, fires even for --dry-run), builds the
 * request, resolves the output path, and either prints a dry-run block
 * or POSTs to /v1/sound-generation and streams the response to disk.
 * On success, appends one history record and prints the output path.
 *
 * @param {object} parsed  parseArgs result.
 * @param {object} [deps]  Injectable dependencies for tests.
 */
async function runSFX(parsed, deps = {}) {
  const {
    fetchImpl,
    appendHistoryFn = appendHistory,
    writeHistoryFn,
    stdout = process.stdout,
  } = deps;

  const { flags } = parsed;
  const opts = validateSFXOptions(parsed);

  const { url, body } = buildSFXRequest(opts);

  const outputPath = resolveOutputPath({
    type: 'sfx',
    prompt: opts.text,
    outputOption: flags.output,
    outputFormat: opts.outputFormat,
    force: !!flags.force,
    tz: 'America/New_York',
  });

  if (flags.dryRun) {
    stdout.write('audiogen dry-run (sfx)\n');
    stdout.write(`  url: ${url}\n`);
    stdout.write(`  body: ${JSON.stringify(body)}\n`);
    stdout.write(`  output: ${outputPath}\n`);
    return { url, body, outputPath, dryRun: true };
  }

  // Live call.
  const callOpts = {
    method: 'POST',
    path: '/v1/sound-generation',
    query: { output_format: opts.outputFormat },
    body,
    outputPath,
    responseType: 'binary',
  };
  if (fetchImpl) callOpts.fetchImpl = fetchImpl;

  const result = await callElevenLabs(callOpts);

  // History record — best-effort; failures surface as stderr warnings only.
  const record = {
    ts: new Date().toISOString(),
    type: 'sfx',
    phase: 'sfx',
    text: opts.text,
    model_id: opts.modelId,
    prompt_influence: opts.promptInfluence,
    loop: opts.loop,
    output_format: opts.outputFormat,
    output_path: outputPath,
  };
  if (opts.durationSeconds !== undefined) record.duration_seconds = opts.durationSeconds;
  if (flags.historyId) record.history_id = flags.historyId;
  if (flags.historyParent) record.parent_id = flags.historyParent;
  if (result && result.requestId) record.request_id = result.requestId;
  if (result && result.bytesWritten) record.bytes = result.bytesWritten;

  if (writeHistoryFn) {
    appendHistoryFn(record, writeHistoryFn);
  } else {
    appendHistoryFn(record);
  }

  stdout.write(`${outputPath}\n`);
  return { url, body, outputPath, dryRun: false, result };
}

// ────────────────────────────────────────────────────────────────────
// Voices (catalog list) subcommand
// ────────────────────────────────────────────────────────────────────

const VOICES_CACHE_TTL_MS = 24 * 60 * 60 * 1000;
const VOICES_CACHE_FILENAME = '.audiogen-voices.json';
const VOICES_CACHE_TMP_FILENAME = '.audiogen-voices.json.tmp';
const VOICES_TABLE_ROW_CAP = 50;
const VOICES_PAGE_SIZE_DEFAULT = 100;

/**
 * Fetch the full voice catalog from v2/voices, paginating until
 * `has_more: false` (or `next_page_token` absent). Accumulates into
 * a single array.
 *
 * Returns the concatenated voices array. Uses
 * `callElevenLabs({ responseType: 'json' })`.
 */
async function fetchAllVoices({ pageSize, fetchImpl } = {}) {
  const limit = pageSize || VOICES_PAGE_SIZE_DEFAULT;
  const out = [];
  let nextPageToken = null;
  // Safety rail: 1000 pages * 100 voices = 100k voices — far above reality.
  for (let i = 0; i < 1000; i++) {
    const query = {
      page_size: String(limit),
      include_total_count: 'false',
    };
    if (nextPageToken) query.next_page_token = nextPageToken;

    const callOpts = {
      method: 'GET',
      path: '/v2/voices',
      query,
      responseType: 'json',
    };
    if (fetchImpl) callOpts.fetchImpl = fetchImpl;
    const { json } = await callElevenLabs(callOpts);

    if (json && Array.isArray(json.voices)) {
      for (const v of json.voices) out.push(v);
    }

    const hasMore = !!(json && json.has_more);
    const token = json && json.next_page_token;
    if (!hasMore || !token) break;
    nextPageToken = token;
  }
  return out;
}

/**
 * Read + parse the cache file. Returns {voices, fetched_at, mtimeMs} on
 * success. On any error (missing, unreadable, JSON parse fail), returns
 * null. When the file exists but parses invalid, writes a stderr warning
 * via `onParseError(path)`.
 */
function readVoicesCache(cachePath, { onParseError } = {}) {
  if (!fs.existsSync(cachePath)) return null;
  let stat;
  try {
    stat = fs.statSync(cachePath);
  } catch (_e) {
    return null;
  }
  let raw;
  try {
    raw = fs.readFileSync(cachePath, 'utf8');
  } catch (_e) {
    return null;
  }
  let obj;
  try {
    obj = JSON.parse(raw);
  } catch (_e) {
    if (onParseError) onParseError(cachePath);
    return null;
  }
  if (!obj || !Array.isArray(obj.voices)) return null;
  return {
    voices: obj.voices,
    fetched_at: obj.fetched_at,
    mtimeMs: stat.mtimeMs,
  };
}

/**
 * Atomic cache write: write to `.audiogen-voices.json.tmp`, then rename
 * over `.audiogen-voices.json`. Returns the final cache path on success.
 */
function writeVoicesCache(cachePath, voices, { now } = {}) {
  const dir = path.dirname(cachePath);
  const tmp = path.join(dir, VOICES_CACHE_TMP_FILENAME);
  const payload = {
    fetched_at: (now || new Date()).toISOString(),
    voices,
  };
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(tmp, JSON.stringify(payload, null, 2));
  fs.renameSync(tmp, cachePath);
  return cachePath;
}

function matchesSubstring(haystack, needle) {
  if (haystack == null) return false;
  return String(haystack).toLowerCase().includes(String(needle).toLowerCase());
}

/**
 * Filter voices client-side. All filters are optional. An absent label
 * field yields no-match for that specific filter; if no filters are
 * active, every voice is retained.
 */
function filterVoices(voices, { query, language, gender, accent, category }) {
  return voices.filter((v) => {
    if (!v || typeof v !== 'object') return false;
    const labels = v.labels || {};

    if (query) {
      const q = String(query).toLowerCase();
      let matched = false;
      if (typeof v.name === 'string' && v.name.toLowerCase().includes(q)) matched = true;
      if (!matched) {
        for (const val of Object.values(labels)) {
          if (typeof val === 'string' && val.toLowerCase().includes(q)) {
            matched = true;
            break;
          }
        }
      }
      if (!matched) return false;
    }

    if (language) {
      const candidates = [];
      if (typeof labels.language === 'string') candidates.push(labels.language);
      if (v.fine_tuning && typeof v.fine_tuning.language === 'string') {
        candidates.push(v.fine_tuning.language);
      }
      if (Array.isArray(v.verified_languages)) {
        for (const vl of v.verified_languages) {
          if (vl && typeof vl.language === 'string') candidates.push(vl.language);
        }
      }
      const lang = String(language).toLowerCase();
      if (!candidates.some((c) => c.toLowerCase().includes(lang))) return false;
    }

    if (gender) {
      if (typeof labels.gender !== 'string') return false;
      if (labels.gender.toLowerCase() !== String(gender).toLowerCase()) return false;
    }

    if (accent) {
      if (!matchesSubstring(labels.accent, accent)) return false;
    }

    if (category) {
      if (typeof v.category !== 'string') return false;
      if (v.category !== category) return false;
    }

    return true;
  });
}

function padRight(s, n) {
  s = s == null ? '' : String(s);
  if (s.length >= n) return s.slice(0, n);
  return s + ' '.repeat(n - s.length);
}

function formatVoicesTable(voices, { rowCap = VOICES_TABLE_ROW_CAP } = {}) {
  // Sort alphabetically by name for deterministic output.
  const sorted = voices
    .slice()
    .sort((a, b) => {
      const an = (a && a.name) || '';
      const bn = (b && b.name) || '';
      return an.localeCompare(bn);
    });
  const truncated = sorted.slice(0, rowCap);
  const overflow = sorted.length - truncated.length;

  const cols = [
    { key: 'name', header: 'NAME', width: 24 },
    { key: 'voice_id', header: 'ID', width: 22 },
    { key: 'category', header: 'CATEGORY', width: 14 },
    { key: 'language', header: 'LANG', width: 10 },
    { key: 'gender', header: 'GENDER', width: 8 },
    { key: 'accent', header: 'ACCENT', width: 14 },
    { key: 'preview', header: 'PREVIEW', width: 40 },
  ];

  const rowFor = (v) => {
    const labels = (v && v.labels) || {};
    return {
      name: v && v.name,
      voice_id: v && v.voice_id,
      category: v && v.category,
      language:
        (labels && labels.language) ||
        (v && v.fine_tuning && v.fine_tuning.language) ||
        '',
      gender: labels && labels.gender,
      accent: labels && labels.accent,
      preview: v && v.preview_url,
    };
  };

  const lines = [];
  lines.push(cols.map((c) => padRight(c.header, c.width)).join(' '));
  for (const v of truncated) {
    const row = rowFor(v);
    lines.push(cols.map((c) => padRight(row[c.key], c.width)).join(' '));
  }
  if (overflow > 0) {
    lines.push(`(+${overflow} more — refine query or use --json)`);
  }
  return lines.join('\n') + '\n';
}

async function runVoicesList(parsed, deps = {}) {
  const {
    fetchImpl,
    stdout = process.stdout,
    stderr = process.stderr,
    cachePath = path.join(process.cwd(), VOICES_CACHE_FILENAME),
    now = new Date(),
    ttlMs = VOICES_CACHE_TTL_MS,
  } = deps;

  const { flags, positionals } = parsed;
  const query = positionals.join(' ').trim();

  // --page-size: integer in [1, 100]; default 100.
  let pageSize = VOICES_PAGE_SIZE_DEFAULT;
  if (flags.pageSize !== undefined) {
    const raw = String(flags.pageSize);
    if (!/^\d+$/.test(raw)) {
      fail(`--page-size must be an integer; got "${flags.pageSize}".`);
    }
    pageSize = Number(raw);
    if (pageSize < 1 || pageSize > 100) {
      fail(`--page-size must be in [1, 100]; got ${pageSize}.`);
    }
  }

  const filterSpec = {
    query: query || undefined,
    language: flags.language,
    gender: flags.gender,
    accent: flags.accent,
    category: flags.category,
  };

  if (flags.dryRun) {
    const q = {
      page_size: String(pageSize),
      include_total_count: 'false',
    };
    const qs = Object.entries(q)
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
      .join('&');
    const url = `${BASE_URL}/v2/voices?${qs}`;
    stdout.write('audiogen dry-run (voices)\n');
    stdout.write(`  url: ${url}\n`);
    stdout.write(`  page_size: ${pageSize}\n`);
    stdout.write(`  filters: ${JSON.stringify(filterSpec)}\n`);
    stdout.write(`  cache: ${cachePath}\n`);
    return { url, pageSize, filters: filterSpec, dryRun: true };
  }

  let voices = null;
  const cache = readVoicesCache(cachePath, {
    onParseError: (p) =>
      stderr.write(`audiogen: cache parse error at ${p}; refetching\n`),
  });
  const cacheFresh =
    cache &&
    typeof cache.mtimeMs === 'number' &&
    now.getTime() - cache.mtimeMs < ttlMs;

  if (cache && cacheFresh && !flags.refresh) {
    voices = cache.voices;
  } else {
    voices = await fetchAllVoices({ pageSize, fetchImpl });
    writeVoicesCache(cachePath, voices, { now });
  }

  const filtered = filterVoices(voices, filterSpec);

  if (flags.json) {
    stdout.write(JSON.stringify(filtered) + '\n');
    return { voices: filtered, dryRun: false, cacheHit: !!cache && cacheFresh && !flags.refresh };
  }

  const rowCap = flags.limit ? Math.max(1, Number(flags.limit)) : VOICES_TABLE_ROW_CAP;
  stdout.write(formatVoicesTable(filtered, { rowCap }));
  return {
    voices: filtered,
    dryRun: false,
    cacheHit: !!cache && cacheFresh && !flags.refresh,
  };
}

// ────────────────────────────────────────────────────────────────────
// Main entry
// ────────────────────────────────────────────────────────────────────

async function main(argv) {
  assertNodeVersion();
  loadEnv();

  let parsed;
  try {
    parsed = parseArgs(argv);
  } catch (e) {
    if (e && e.usage) {
      process.stderr.write(`audiogen: ${e.message}\n\n`);
      process.stderr.write(HELP_TEXT);
      process.exit(1);
    }
    throw e;
  }

  if (parsed.help) {
    printHelp();
    process.exit(0);
  }

  const { subcommand, flags } = parsed;

  // Music has its own validation + dry-run + live path. Route here so
  // pre-network validation (--loop, --output-format wav, --length-ms bounds)
  // fires even for --dry-run.
  if (subcommand === 'music') {
    try {
      await runMusic(parsed);
    } catch (e) {
      fail(e && e.message ? e.message : String(e));
    }
    return;
  }

  // Voice: routes through runTTS (pre-network validation + dry-run + live).
  if (subcommand === 'voice') {
    try {
      if (!flags.dryRun) assertApiKey();
      await runTTS(parsed);
    } catch (e) {
      fail(e && e.message ? e.message : String(e));
    }
    return;
  }

  // Voices: routes through runVoicesList. Dry-run does not fetch or touch
  // the cache; live uses the cache-TTL path.
  if (subcommand === 'voices') {
    try {
      if (!flags.dryRun) assertApiKey();
      await runVoicesList(parsed);
    } catch (e) {
      fail(e && e.message ? e.message : String(e));
    }
    return;
  }

  // SFX: routes through runSFX (pre-network validation + dry-run + live).
  if (subcommand === 'sfx') {
    try {
      if (!flags.dryRun) assertApiKey();
      await runSFX(parsed);
    } catch (e) {
      fail(e && e.message ? e.message : String(e));
    }
    return;
  }
}

// ────────────────────────────────────────────────────────────────────
// Exports for tests (when required, not run as CLI)
// ────────────────────────────────────────────────────────────────────

module.exports = {
  // core
  fail,
  loadEnv,
  assertNodeVersion,
  assertApiKey,
  // slug + paths
  slugify,
  timestampSlug,
  extFromOutputFormat,
  resolveOutputPath,
  mkdirpParent,
  // history
  appendHistory,
  // args
  parseArgs,
  FLAG_SPECS,
  SUBCOMMANDS,
  // http
  callElevenLabs,
  parseRetryAfter,
  // help
  HELP_TEXT,
  printHelp,
  // music subcommand
  runMusic,
  validateMusicOptions,
  buildMusicRequest,
  MUSIC_OUTPUT_FORMAT_RE,
  MUSIC_LENGTH_MIN_MS,
  MUSIC_LENGTH_MAX_MS,
  MUSIC_LENGTH_DEFAULT_MS,
  MUSIC_LOOP_REJECT_MSG,
  MUSIC_WAV_REJECT_MSG,
  // voice subcommand
  runTTS,
  resolveVoiceId,
  validateVoiceOptions,
  buildVoiceRequest,
  VOICE_ID_RE,
  VOICE_TEXT_MAX_LEN,
  VOICE_DEFAULT_MODEL_ID,
  VOICE_DEFAULT_OUTPUT_FORMAT,
  VOICE_OUTPUT_FORMAT_RE,
  // voices subcommand
  runVoicesList,
  fetchAllVoices,
  readVoicesCache,
  writeVoicesCache,
  filterVoices,
  formatVoicesTable,
  VOICES_CACHE_FILENAME,
  VOICES_CACHE_TMP_FILENAME,
  VOICES_CACHE_TTL_MS,
  VOICES_PAGE_SIZE_DEFAULT,
  VOICES_TABLE_ROW_CAP,
  // sfx subcommand
  runSFX,
  validateSFXOptions,
  buildSFXRequest,
  SFX_OUTPUT_FORMAT_RE,
  SFX_DURATION_MIN_S,
  SFX_DURATION_MAX_S,
  SFX_PROMPT_INFLUENCE_DEFAULT,
  SFX_PROMPT_INFLUENCE_MIN,
  SFX_PROMPT_INFLUENCE_MAX,
  SFX_DEFAULT_MODEL_ID,
  SFX_DEFAULT_OUTPUT_FORMAT,
  SFX_WAV_REJECT_MSG,
  SFX_LOOP_MODEL_REJECT_MSG,
  // main (for integration tests)
  main,
};

if (require.main === module) {
  main(process.argv.slice(2)).catch((e) => {
    fail(e && e.message ? e.message : String(e));
  });
}
