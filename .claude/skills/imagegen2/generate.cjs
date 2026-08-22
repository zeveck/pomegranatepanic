#!/usr/bin/env node

// generate.cjs - Thin OpenAI gpt-image-2 API wrapper for imagegen2.
// Zero external dependencies. Requires Node.js 20+ for built-in fetch().
//
// NOTE: gpt-image-2 always returns b64_json. Do NOT send `response_format`.
// Use `output_format` for the image encoding (png/jpeg/webp).
//
// Usage:
//   node generate.cjs --prompt "..." --output "./path/to/image.png" [options]

"use strict";

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const zlib = require("zlib");

// Load .env file if present (Node 20.12+ built-in, no dependencies).
// Search cwd first, then walk up from the script's own directory so the
// skill works regardless of where it's invoked from (worktrees, subdirs).
(function loadEnv() {
  const tried = new Set();
  const candidates = [process.cwd()];
  let dir = __dirname;
  while (dir && dir !== path.dirname(dir)) {
    candidates.push(dir);
    dir = path.dirname(dir);
  }
  for (const d of candidates) {
    const p = path.join(d, ".env");
    if (tried.has(p)) continue;
    tried.add(p);
    try {
      if (fs.existsSync(p)) {
        process.loadEnvFile(p);
        return;
      }
    } catch {}
  }
})();

// ---------------------------------------------------------------------------
// Early --help check (before argument parsing, so it works with any flags)
// ---------------------------------------------------------------------------

if (process.argv.includes("--help") || process.argv.includes("-h")) {
  console.log(`
generate.cjs - OpenAI gpt-image-2 API wrapper

Usage:
  node generate.cjs --prompt "..." --output "./path/to/image.png" [options]

Required:
  --prompt <string>       Image generation prompt
  --output <path>         Output file path (.png, .jpg, .jpeg, or .webp)

Options:
  --size <size>           auto or WxH. Each edge <=3840, multiples of 16,
                          ratio <=3:1, total pixels 655360..8294400.
                          Common: 1024x1024, 1536x1024, 1024x1536,
                          2048x2048, 2048x1152, 3840x2160, 2160x3840
                          (default: 1024x1024)
  --quality <quality>     low | medium | high | auto (default: low)
  --background <bg>       transparent | opaque | auto (default: auto)
                          transparent requires --transparent-mode.
  --transparent-mode <m>  reject | chroma-key | fallback-model (default: reject)
                          chroma-key keeps gpt-image-2, requests an opaque
                          solid key background, then removes it locally.
                          fallback-model uses gpt-image-1.5 for native alpha.
  --chroma-key <hex>      Chroma-key color for local removal (default: #00ff00)
  --chroma-tolerance <n>  Chroma-key RGB distance tolerance, 0-442 (default: 24)
  --output-compression <n> JPEG/WEBP compression, 0-100. Not valid for PNG.
  --model <model>         Model name (default: gpt-image-2)
  --client-request-id <id> Override generated request ID
  --dry-run               Validate and print request summary without API call
  --help, -h              Show this help message

Reference images (triggers /v1/images/edits endpoint):
  --image <path>          Input image file (repeatable, max 16). PNG/JPG/WEBP, <50 MB.
  --mask <path>           PNG mask with alpha channel for inpainting (<4 MB).
  --input-fidelity <val>  Not supported with gpt-image-2. Image inputs are
                          processed at high fidelity automatically.

History (automatic by default):
  --history-id <string>   Override auto-derived ID (default: from output path)
  --history-parent <str>  Parent generation ID (for iterations)
  --no-history            Disable history logging for this generation

Environment:
  OPENAI_API_KEY          Required. Your OpenAI API key.

Examples:
  node generate.cjs --prompt "A pixel art sword" --output "./sword.png"
  node generate.cjs --prompt "Forest scene" --output "./bg.png" --size 3840x2160 --quality high
  node generate.cjs --prompt "Icon on a plain background" --output "./icon.png" --background opaque
  node generate.cjs --prompt "Pixel sprite" --output "./sprite.png" --background transparent --transparent-mode chroma-key --chroma-key "#ff00ff"
  node generate.cjs --prompt "Native-alpha icon" --output "./icon.png" --background transparent --transparent-mode fallback-model
  node generate.cjs --prompt "Make it blue" --output "./edit.png" --image "./orig.png"
  node generate.cjs --prompt "Match this style" --output "./new.png" --image "./ref1.png" --image "./ref2.png"
`.trim());
  process.exit(0);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fail(message, extra = {}) {
  process.stdout.write(JSON.stringify({ success: false, error: message, ...extra }) + "\n");
  process.exit(1);
}

class Imagegen2Error extends Error {
  constructor(message, extra = {}) {
    super(message);
    this.name = "Imagegen2Error";
    this.extra = extra;
  }
}

function requireArgValue(flag, argv, index) {
  if (index >= argv.length || argv[index] === undefined) {
    fail(`${flag} requires a value.`);
  }
  return argv[index];
}

// ---------------------------------------------------------------------------
// Argument parsing
// ---------------------------------------------------------------------------

function parseArgs(argv) {
  const args = {
    prompt: null,
    output: null,
    size: "1024x1024",
    quality: "low",
    background: "auto",
    model: "gpt-image-2",
    fallbackModel: null,
    transparentMode: "reject",
    chromaKey: "#00ff00",
    chromaTolerance: "24",
    outputCompression: null,
    images: [],           // Reference images for edits endpoint
    mask: null,           // PNG mask for inpainting
    inputFidelity: null,  // Unsupported by gpt-image-2
    clientRequestId: null,
    dryRun: false,
    historyId: null,      // null = auto-derive from output filename
    historyParent: null,
    noHistory: false,
  };

  for (let i = 2; i < argv.length; i++) {
    const flag = argv[i];
    switch (flag) {
      case "--help":
      case "-h":
        break; // Already handled above
      case "--prompt":
        args.prompt = requireArgValue(flag, argv, ++i);
        break;
      case "--output":
        args.output = requireArgValue(flag, argv, ++i);
        break;
      case "--size":
        args.size = requireArgValue(flag, argv, ++i);
        break;
      case "--quality":
        args.quality = requireArgValue(flag, argv, ++i);
        break;
      case "--background":
        args.background = requireArgValue(flag, argv, ++i);
        break;
      case "--transparent-mode":
        args.transparentMode = requireArgValue(flag, argv, ++i);
        break;
      case "--chroma-key":
        args.chromaKey = requireArgValue(flag, argv, ++i);
        break;
      case "--chroma-tolerance":
        args.chromaTolerance = requireArgValue(flag, argv, ++i);
        break;
      case "--model":
        args.model = requireArgValue(flag, argv, ++i);
        break;
      case "--output-compression":
        args.outputCompression = requireArgValue(flag, argv, ++i);
        break;
      case "--image":
        args.images.push(requireArgValue(flag, argv, ++i));
        break;
      case "--mask":
        args.mask = requireArgValue(flag, argv, ++i);
        break;
      case "--input-fidelity":
        args.inputFidelity = requireArgValue(flag, argv, ++i);
        break;
      case "--client-request-id":
        args.clientRequestId = requireArgValue(flag, argv, ++i);
        break;
      case "--dry-run":
        args.dryRun = true;
        break;
      case "--history-id":
        args.historyId = requireArgValue(flag, argv, ++i);
        break;
      case "--history-parent":
        args.historyParent = requireArgValue(flag, argv, ++i);
        break;
      case "--no-history":
        args.noHistory = true;
        break;
      default:
        fail(`Unknown argument: ${flag}. Use --help for usage information.`);
    }
  }

  return args;
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

const VALID_QUALITIES = new Set(["low", "medium", "high", "auto"]);
const VALID_BACKGROUNDS = new Set(["transparent", "opaque", "auto"]);
const VALID_TRANSPARENT_MODES = new Set(["reject", "chroma-key", "fallback-model"]);
const VALID_EXTENSIONS = { ".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp" };
const VALID_IMAGE_EXTENSIONS = new Set([".png", ".jpg", ".jpeg", ".webp"]);
const MAX_IMAGES = 16;
const MAX_IMAGE_BYTES = 50 * 1024 * 1024;  // 50 MB
const MAX_MASK_BYTES = 4 * 1024 * 1024;    // 4 MB

const MIME_TYPES = { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp" };

const VALID_MASK_EXTENSIONS = new Set([".png"]);
const CHROMA_KEY_PROMPT_SUFFIX = "Solid flat {color} chroma-key background filling the canvas, no shadows, no gradients, no background objects.";

function validateSize(size) {
  if (size === "auto") return;
  const match = /^([1-9][0-9]*)x([1-9][0-9]*)$/.exec(size);
  if (!match) {
    fail(`Invalid --size "${size}". Use auto or WxH, for example 1024x1024.`);
  }
  const width = Number(match[1]);
  const height = Number(match[2]);
  const maxEdge = Math.max(width, height);
  const minEdge = Math.min(width, height);
  const pixels = width * height;
  if (width > 3840 || height > 3840) {
    fail(`Invalid --size "${size}". Each edge must be <= 3840 for gpt-image-2.`);
  }
  if (width % 16 !== 0 || height % 16 !== 0) {
    fail(`Invalid --size "${size}". Width and height must be multiples of 16 for gpt-image-2.`);
  }
  if (maxEdge / minEdge > 3) {
    fail(`Invalid --size "${size}". Long-edge to short-edge ratio must be <= 3:1 for gpt-image-2.`);
  }
  if (pixels < 655360 || pixels > 8294400) {
    fail(`Invalid --size "${size}". Total pixels must be between 655360 and 8294400 for gpt-image-2.`);
  }
}

function validateImageFile(filePath, label, { maxBytes, allowedExtensions } = {}) {
  const exts = allowedExtensions || VALID_IMAGE_EXTENSIONS;
  const limit = maxBytes || MAX_IMAGE_BYTES;
  const resolved = path.resolve(filePath);
  if (!fs.existsSync(resolved)) {
    fail(`${label} file not found: "${filePath}"`);
  }
  const ext = path.extname(resolved).toLowerCase();
  if (!exts.has(ext)) {
    const names = [...exts].join(", ");
    fail(`${label} has unsupported extension "${ext}". Must be: ${names}`);
  }
  const stat = fs.statSync(resolved);
  if (stat.size > limit) {
    fail(`${label} is ${(stat.size / 1024 / 1024).toFixed(1)} MB, exceeds ${limit / 1024 / 1024} MB limit.`);
  }
  return { resolved, ext, mime: MIME_TYPES[ext] };
}

function validate(args) {
  if (!args.prompt) fail("--prompt is required.");
  if (!args.output) fail("--output is required.");
  validateSize(args.size);
  if (!VALID_QUALITIES.has(args.quality))
    fail(`Invalid --quality "${args.quality}". Must be one of: ${[...VALID_QUALITIES].join(", ")}`);
  if (!VALID_BACKGROUNDS.has(args.background))
    fail(`Invalid --background "${args.background}". Must be one of: ${[...VALID_BACKGROUNDS].join(", ")}`);
  if (!VALID_TRANSPARENT_MODES.has(args.transparentMode))
    fail(`Invalid --transparent-mode "${args.transparentMode}". Must be one of: ${[...VALID_TRANSPARENT_MODES].join(", ")}`);
  if (!/^#[0-9a-fA-F]{6}$/.test(args.chromaKey)) {
    fail(`Invalid --chroma-key "${args.chromaKey}". Must be a hex color like #00ff00.`);
  }
  if (!/^[0-9]+$/.test(args.chromaTolerance)) {
    fail(`Invalid --chroma-tolerance "${args.chromaTolerance}". Must be an integer 0-442.`);
  }
  args.chromaTolerance = Number(args.chromaTolerance);
  if (args.chromaTolerance < 0 || args.chromaTolerance > 442) {
    fail(`Invalid --chroma-tolerance "${args.chromaTolerance}". Must be an integer 0-442.`);
  }

  const ext = path.extname(args.output).toLowerCase();
  if (!VALID_EXTENSIONS[ext]) {
    fail(`Unsupported file extension "${ext}". Use .png, .jpg, .jpeg, or .webp.`);
  }

  if (args.background === "transparent") {
    if (ext === ".jpg" || ext === ".jpeg") {
      fail("JPEG does not support transparency. Use .png or .webp with --background transparent.");
    }
    if (args.transparentMode === "reject") {
      fail('gpt-image-2 does not use native background "transparent" by default. Use --transparent-mode chroma-key for transparent PNG cleanup, or --transparent-mode fallback-model only when native alpha is required.');
    }
    if (args.transparentMode === "chroma-key") {
      if (ext !== ".png") {
        fail("--transparent-mode chroma-key currently requires PNG output. Use .png or --transparent-mode fallback-model.");
      }
      args.model = "gpt-image-2";
    }
    if (args.transparentMode === "fallback-model") {
      args.fallbackModel = "gpt-image-1.5";
      args.model = "gpt-image-1.5";
    }
  } else if (args.transparentMode !== "reject") {
    fail("--transparent-mode only applies when --background transparent is requested.");
  }

  if (args.outputCompression !== null) {
    if (!/^[0-9]+$/.test(args.outputCompression)) {
      fail(`Invalid --output-compression "${args.outputCompression}". Must be an integer 0-100.`);
    }
    const compression = Number(args.outputCompression);
    if (compression < 0 || compression > 100) {
      fail(`Invalid --output-compression "${args.outputCompression}". Must be an integer 0-100.`);
    }
    if (ext === ".png") {
      fail("--output-compression is only valid with JPEG or WEBP output, not PNG.");
    }
    args.outputCompression = compression;
  }

  if (args.clientRequestId !== null) {
    if (args.clientRequestId.length > 512 || !/^[\x20-\x7E]+$/.test(args.clientRequestId)) {
      fail("--client-request-id must contain only ASCII printable characters and be 512 characters or fewer.");
    }
  }

  // --- Reference image validation ---

  if (args.images.length > MAX_IMAGES) {
    fail(`Too many --image flags (${args.images.length}). Maximum is ${MAX_IMAGES}.`);
  }

  // Resolve image paths in place
  for (let i = 0; i < args.images.length; i++) {
    const info = validateImageFile(args.images[i], `--image "${args.images[i]}"`, {
      maxBytes: MAX_IMAGE_BYTES,
    });
    args.images[i] = info.resolved;
  }

  // Mask requires --image
  if (args.mask && args.images.length === 0) {
    fail("--mask requires at least one --image.");
  }

  if (args.mask) {
    const info = validateImageFile(args.mask, "--mask", {
      maxBytes: MAX_MASK_BYTES,
      allowedExtensions: VALID_MASK_EXTENSIONS,
    });
    args.mask = info.resolved;
  }

  if (args.inputFidelity) {
    fail("gpt-image-2 always uses high-fidelity image inputs; --input-fidelity is not supported.");
  }
}

// ---------------------------------------------------------------------------
// Retry logic with exponential backoff
// ---------------------------------------------------------------------------

const RETRYABLE_STATUS_CODES = new Set([429, 500, 502, 503]);
const MAX_RETRIES = 3;
const BASE_DELAY_MS = 1000;
const FETCH_TIMEOUT_MS = 120_000; // 2 minutes

// ---------------------------------------------------------------------------
// Minimal PNG chroma-key post-processing
// ---------------------------------------------------------------------------

const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
const MAX_CHROMA_KEY_PIXELS = 25_000_000;
let CRC_TABLE = null;

function crcTable() {
  if (CRC_TABLE) return CRC_TABLE;
  CRC_TABLE = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) {
      c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
    }
    CRC_TABLE[n] = c >>> 0;
  }
  return CRC_TABLE;
}

function crc32(buf) {
  const table = crcTable();
  let c = 0xffffffff;
  for (const byte of buf) {
    c = table[(c ^ byte) & 0xff] ^ (c >>> 8);
  }
  return (c ^ 0xffffffff) >>> 0;
}

function parseHexColor(hex) {
  const normalized = hex.toLowerCase();
  if (!/^#[0-9a-f]{6}$/.test(normalized)) {
    throw new Imagegen2Error(`Invalid chroma key "${hex}". Must be a hex color like #00ff00.`);
  }
  return {
    hex: normalized,
    r: Number.parseInt(normalized.slice(1, 3), 16),
    g: Number.parseInt(normalized.slice(3, 5), 16),
    b: Number.parseInt(normalized.slice(5, 7), 16),
  };
}

function paethPredictor(a, b, c) {
  const p = a + b - c;
  const pa = Math.abs(p - a);
  const pb = Math.abs(p - b);
  const pc = Math.abs(p - c);
  if (pa <= pb && pa <= pc) return a;
  if (pb <= pc) return b;
  return c;
}

function parsePng(buffer) {
  if (!Buffer.isBuffer(buffer)) {
    throw new Imagegen2Error("PNG parser expected a Buffer.");
  }
  if (buffer.length < PNG_SIGNATURE.length || !buffer.subarray(0, 8).equals(PNG_SIGNATURE)) {
    throw new Imagegen2Error("Unsupported PNG: missing PNG signature.");
  }

  let offset = 8;
  let ihdr = null;
  let seenIend = false;
  const idatChunks = [];
  while (offset < buffer.length) {
    if (offset + 12 > buffer.length) {
      throw new Imagegen2Error("Corrupt PNG: truncated chunk header.");
    }
    const length = buffer.readUInt32BE(offset);
    const type = buffer.toString("ascii", offset + 4, offset + 8);
    const dataStart = offset + 8;
    const dataEnd = dataStart + length;
    const crcEnd = dataEnd + 4;
    if (crcEnd > buffer.length) {
      throw new Imagegen2Error(`Corrupt PNG: truncated ${type} chunk.`);
    }
    const data = buffer.subarray(dataStart, dataEnd);
    const actualCrc = buffer.readUInt32BE(dataEnd);
    const expectedCrc = crc32(buffer.subarray(offset + 4, dataEnd));
    if (actualCrc !== expectedCrc) {
      throw new Imagegen2Error(`Corrupt PNG: CRC mismatch in ${type} chunk.`);
    }
    if (type === "IHDR") {
      if (length !== 13) throw new Imagegen2Error("Corrupt PNG: invalid IHDR length.");
      if (ihdr) throw new Imagegen2Error("Corrupt PNG: duplicate IHDR chunk.");
      ihdr = {
        width: data.readUInt32BE(0),
        height: data.readUInt32BE(4),
        bitDepth: data[8],
        colorType: data[9],
        compression: data[10],
        filter: data[11],
        interlace: data[12],
      };
    } else if (type === "IDAT") {
      idatChunks.push(data);
    } else if (type === "IEND") {
      seenIend = true;
      break;
    }
    offset = crcEnd;
  }

  if (!ihdr) throw new Imagegen2Error("Corrupt PNG: missing IHDR chunk.");
  if (!seenIend) throw new Imagegen2Error("Corrupt PNG: missing IEND chunk.");
  if (!idatChunks.length) throw new Imagegen2Error("Corrupt PNG: missing IDAT chunk.");
  if (ihdr.width === 0 || ihdr.height === 0) {
    throw new Imagegen2Error("Corrupt PNG: width and height must be greater than zero.");
  }
  const pixelCount = ihdr.width * ihdr.height;
  if (pixelCount > MAX_CHROMA_KEY_PIXELS) {
    throw new Imagegen2Error(`Unsupported PNG: ${pixelCount} pixels exceeds chroma-key limit of ${MAX_CHROMA_KEY_PIXELS}.`);
  }
  if (ihdr.bitDepth !== 8) {
    throw new Imagegen2Error(`Unsupported PNG: bit depth ${ihdr.bitDepth}; only 8-bit PNGs are supported.`);
  }
  if (![2, 6].includes(ihdr.colorType)) {
    throw new Imagegen2Error(`Unsupported PNG: color type ${ihdr.colorType}; only RGB and RGBA PNGs are supported.`);
  }
  if (ihdr.compression !== 0 || ihdr.filter !== 0 || ihdr.interlace !== 0) {
    throw new Imagegen2Error("Unsupported PNG: only standard non-interlaced PNGs are supported.");
  }

  const channels = ihdr.colorType === 6 ? 4 : 3;
  const bytesPerPixel = channels;
  const rowBytes = ihdr.width * channels;
  const expected = (rowBytes + 1) * ihdr.height;
  let inflated;
  try {
    inflated = zlib.inflateSync(Buffer.concat(idatChunks), { maxOutputLength: expected });
  } catch (err) {
    throw new Imagegen2Error(`Corrupt PNG: failed to inflate IDAT data: ${err.message}`);
  }
  if (inflated.length !== expected) {
    throw new Imagegen2Error(`Corrupt PNG: expected ${expected} inflated bytes, got ${inflated.length}.`);
  }

  const raw = Buffer.alloc(rowBytes * ihdr.height);
  let inOffset = 0;
  let outOffset = 0;
  for (let y = 0; y < ihdr.height; y++) {
    const filter = inflated[inOffset++];
    if (filter > 4) throw new Imagegen2Error(`Unsupported PNG filter type ${filter}.`);
    for (let x = 0; x < rowBytes; x++) {
      const rawByte = inflated[inOffset++];
      const left = x >= bytesPerPixel ? raw[outOffset + x - bytesPerPixel] : 0;
      const up = y > 0 ? raw[outOffset + x - rowBytes] : 0;
      const upLeft = y > 0 && x >= bytesPerPixel ? raw[outOffset + x - rowBytes - bytesPerPixel] : 0;
      let value;
      if (filter === 0) value = rawByte;
      else if (filter === 1) value = rawByte + left;
      else if (filter === 2) value = rawByte + up;
      else if (filter === 3) value = rawByte + Math.floor((left + up) / 2);
      else value = rawByte + paethPredictor(left, up, upLeft);
      raw[outOffset + x] = value & 0xff;
    }
    outOffset += rowBytes;
  }

  const rgba = Buffer.alloc(ihdr.width * ihdr.height * 4);
  for (let src = 0, dst = 0; src < raw.length; src += channels, dst += 4) {
    rgba[dst] = raw[src];
    rgba[dst + 1] = raw[src + 1];
    rgba[dst + 2] = raw[src + 2];
    rgba[dst + 3] = channels === 4 ? raw[src + 3] : 255;
  }

  return { width: ihdr.width, height: ihdr.height, rgba };
}

function pngChunk(type, data) {
  const typeBuf = Buffer.from(type, "ascii");
  const out = Buffer.alloc(12 + data.length);
  out.writeUInt32BE(data.length, 0);
  typeBuf.copy(out, 4);
  data.copy(out, 8);
  const crcInput = Buffer.concat([typeBuf, data]);
  out.writeUInt32BE(crc32(crcInput), 8 + data.length);
  return out;
}

function encodeRgbaPng({ width, height, rgba }) {
  if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) {
    throw new Imagegen2Error("Invalid PNG dimensions for encoding.");
  }
  if (!Buffer.isBuffer(rgba) || rgba.length !== width * height * 4) {
    throw new Imagegen2Error("Invalid RGBA buffer for PNG encoding.");
  }

  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // RGBA
  ihdr[10] = 0;
  ihdr[11] = 0;
  ihdr[12] = 0;

  const rowBytes = width * 4;
  const scanlines = Buffer.alloc((rowBytes + 1) * height);
  for (let y = 0; y < height; y++) {
    const rowStart = y * (rowBytes + 1);
    scanlines[rowStart] = 0; // no filter
    rgba.copy(scanlines, rowStart + 1, y * rowBytes, (y + 1) * rowBytes);
  }

  return Buffer.concat([
    PNG_SIGNATURE,
    pngChunk("IHDR", ihdr),
    pngChunk("IDAT", zlib.deflateSync(scanlines)),
    pngChunk("IEND", Buffer.alloc(0)),
  ]);
}

function alphaBleedTransparentPixels(parsed) {
  const { width, height, rgba } = parsed;
  const pixelCount = width * height;
  const nearest = new Int32Array(pixelCount);
  nearest.fill(-1);
  const queue = new Int32Array(pixelCount);
  let head = 0;
  let tail = 0;

  for (let pixel = 0, offset = 0; pixel < pixelCount; pixel++, offset += 4) {
    if (rgba[offset + 3] > 0) {
      nearest[pixel] = pixel;
      queue[tail++] = pixel;
    }
  }

  if (tail === 0 || tail === pixelCount) return 0;

  while (head < tail) {
    const pixel = queue[head++];
    const source = nearest[pixel];
    const x = pixel % width;
    const y = Math.floor(pixel / width);
    if (x > 0) {
      const next = pixel - 1;
      if (nearest[next] === -1) {
        nearest[next] = source;
        queue[tail++] = next;
      }
    }
    if (x + 1 < width) {
      const next = pixel + 1;
      if (nearest[next] === -1) {
        nearest[next] = source;
        queue[tail++] = next;
      }
    }
    if (y > 0) {
      const next = pixel - width;
      if (nearest[next] === -1) {
        nearest[next] = source;
        queue[tail++] = next;
      }
    }
    if (y + 1 < height) {
      const next = pixel + width;
      if (nearest[next] === -1) {
        nearest[next] = source;
        queue[tail++] = next;
      }
    }
  }

  let bledPixels = 0;
  for (let pixel = 0, offset = 0; pixel < pixelCount; pixel++, offset += 4) {
    if (rgba[offset + 3] !== 0) continue;
    const source = nearest[pixel];
    if (source < 0 || source === pixel) continue;
    const sourceOffset = source * 4;
    rgba[offset] = rgba[sourceOffset];
    rgba[offset + 1] = rgba[sourceOffset + 1];
    rgba[offset + 2] = rgba[sourceOffset + 2];
    bledPixels++;
  }
  return bledPixels;
}

const CHROMA_SPILL_SEARCH_RADIUS = 2;

function colorDistanceSq(r, g, b, key) {
  const dr = r - key.r;
  const dg = g - key.g;
  const db = b - key.b;
  return dr * dr + dg * dg + db * db;
}

function hasTransparentCardinalNeighbor(parsed, pixel) {
  const { width, height, rgba } = parsed;
  const x = pixel % width;
  const y = Math.floor(pixel / width);
  if (x > 0 && rgba[(pixel - 1) * 4 + 3] === 0) return true;
  if (x + 1 < width && rgba[(pixel + 1) * 4 + 3] === 0) return true;
  if (y > 0 && rgba[(pixel - width) * 4 + 3] === 0) return true;
  if (y + 1 < height && rgba[(pixel + width) * 4 + 3] === 0) return true;
  return false;
}

function isLikelyKeySpill(r, g, b, key, tolerance) {
  const spillDistance = Math.max(96, tolerance + 72);
  if (colorDistanceSq(r, g, b, key) > spillDistance * spillDistance) return false;

  const channels = [
    { pixel: r, key: key.r },
    { pixel: g, key: key.g },
    { pixel: b, key: key.b },
  ];
  let constrainedChannels = 0;
  let matchingChannels = 0;
  for (const channel of channels) {
    if (channel.key >= 192) {
      constrainedChannels++;
      if (channel.pixel >= 176) matchingChannels++;
    } else if (channel.key <= 63) {
      constrainedChannels++;
      if (channel.pixel <= 112) matchingChannels++;
    }
  }
  if (constrainedChannels > 0 && matchingChannels !== constrainedChannels) return false;

  return Math.max(r, g, b) - Math.min(r, g, b) >= 64;
}

function averageNearbyVisibleNonSpillColor(parsed, source, pixel, key, tolerance) {
  const { width, height } = parsed;
  const x = pixel % width;
  const y = Math.floor(pixel / width);
  let totalR = 0;
  let totalG = 0;
  let totalB = 0;
  let count = 0;

  for (let dy = -CHROMA_SPILL_SEARCH_RADIUS; dy <= CHROMA_SPILL_SEARCH_RADIUS; dy++) {
    const yy = y + dy;
    if (yy < 0 || yy >= height) continue;
    for (let dx = -CHROMA_SPILL_SEARCH_RADIUS; dx <= CHROMA_SPILL_SEARCH_RADIUS; dx++) {
      const xx = x + dx;
      if (xx < 0 || xx >= width || (dx === 0 && dy === 0)) continue;
      const offset = (yy * width + xx) * 4;
      if (source[offset + 3] === 0) continue;
      const nr = source[offset];
      const ng = source[offset + 1];
      const nb = source[offset + 2];
      if (colorDistanceSq(nr, ng, nb, key) <= tolerance * tolerance) continue;
      if (isLikelyKeySpill(nr, ng, nb, key, tolerance)) continue;
      totalR += nr;
      totalG += ng;
      totalB += nb;
      count++;
    }
  }

  if (count === 0) return null;
  return [
    Math.round(totalR / count),
    Math.round(totalG / count),
    Math.round(totalB / count),
  ];
}

function suppressKeySpillOnVisibleEdges(parsed, key, tolerance) {
  const { width, height, rgba } = parsed;
  const source = Buffer.from(rgba);
  const replacements = [];

  for (let pixel = 0, offset = 0; pixel < width * height; pixel++, offset += 4) {
    if (source[offset + 3] === 0) continue;
    if (!hasTransparentCardinalNeighbor(parsed, pixel)) continue;
    const r = source[offset];
    const g = source[offset + 1];
    const b = source[offset + 2];
    if (!isLikelyKeySpill(r, g, b, key, tolerance)) continue;
    const replacement = averageNearbyVisibleNonSpillColor(parsed, source, pixel, key, tolerance);
    if (!replacement) continue;
    replacements.push({ offset, replacement });
  }

  for (const { offset, replacement } of replacements) {
    rgba[offset] = replacement[0];
    rgba[offset + 1] = replacement[1];
    rgba[offset + 2] = replacement[2];
  }

  return replacements.length;
}

function chromaKeyPng(buffer, { chromaKey, tolerance }) {
  const key = parseHexColor(chromaKey);
  const parsed = parsePng(buffer);
  let removedPixels = 0;
  let opaquePixels = 0;
  for (let i = 0; i < parsed.rgba.length; i += 4) {
    const dr = parsed.rgba[i] - key.r;
    const dg = parsed.rgba[i + 1] - key.g;
    const db = parsed.rgba[i + 2] - key.b;
    const distance = Math.sqrt(dr * dr + dg * dg + db * db);
    if (distance <= tolerance) {
      parsed.rgba[i + 3] = 0;
      removedPixels++;
    } else if (parsed.rgba[i + 3] > 0) {
      opaquePixels++;
    }
  }
  if (removedPixels === 0) {
    throw new Imagegen2Error(`Chroma-key post-processing found no pixels matching ${key.hex} within tolerance ${tolerance}.`, {
      chromaKey: key.hex,
      tolerance,
    });
  }
  const alphaBleedPixels = alphaBleedTransparentPixels(parsed);
  const spillSuppressedPixels = suppressKeySpillOnVisibleEdges(parsed, key, tolerance);
  return {
    buffer: encodeRgbaPng(parsed),
    stats: {
      chromaKey: key.hex,
      tolerance,
      removedPixels,
      retainedVisiblePixels: opaquePixels,
      alphaBleedPixels,
      spillSuppressedPixels,
      width: parsed.width,
      height: parsed.height,
    },
  };
}

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchWithRetry(url, options, clientRequestId) {
  let lastError = null;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    if (attempt > 0) {
      const delay = BASE_DELAY_MS * Math.pow(2, attempt - 1);
      const jitter = Math.random() * delay * 0.5;
      await sleep(delay + jitter);
    }

    let response;
    try {
      response = await fetch(url, {
        ...options,
        signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
      });
    } catch (err) {
      if (err.name === "TimeoutError") {
        lastError = `Request timed out after ${FETCH_TIMEOUT_MS / 1000}s`;
      } else {
        lastError = `Network error: ${err.message}`;
      }
      if (attempt < MAX_RETRIES) continue;
      fail(lastError, { clientRequestId });
    }

    if (response.ok) return response;

    let body;
    try {
      body = await response.json();
    } catch {
      body = { error: { message: `HTTP ${response.status} ${response.statusText}` } };
    }

    const errorMessage = body?.error?.message || `HTTP ${response.status}`;

    // Content policy — do NOT retry
    if (response.status === 400 && errorMessage.toLowerCase().includes("content policy")) {
      fail(`Content policy violation: ${errorMessage}`, {
        clientRequestId,
        openaiRequestId: response.headers?.get?.("x-request-id") || null,
      });
    }

    // Auth errors — do NOT retry
    if (response.status === 401) {
      fail(`Authentication failed: ${errorMessage}. Check your OPENAI_API_KEY.`, {
        clientRequestId,
        openaiRequestId: response.headers?.get?.("x-request-id") || null,
      });
    }

    // Billing/quota/verification — do NOT retry
    if (response.status === 402 || response.status === 403) {
      fail(`Access denied (HTTP ${response.status}): ${errorMessage}`, {
        clientRequestId,
        openaiRequestId: response.headers?.get?.("x-request-id") || null,
      });
    }

    // Retryable errors
    if (RETRYABLE_STATUS_CODES.has(response.status)) {
      lastError = `HTTP ${response.status}: ${errorMessage}`;
      if (attempt < MAX_RETRIES) continue;
      fail(`Failed after ${MAX_RETRIES + 1} attempts. Last error: ${lastError}`, {
        clientRequestId,
        openaiRequestId: response.headers?.get?.("x-request-id") || null,
      });
    }

    // Any other error
    fail(`API error (HTTP ${response.status}): ${errorMessage}`, {
      clientRequestId,
      openaiRequestId: response.headers?.get?.("x-request-id") || null,
    });
  }

  fail(`Failed after ${MAX_RETRIES + 1} attempts. Last error: ${lastError}`, { clientRequestId });
}

// ---------------------------------------------------------------------------
// Edit-mode FormData builder
// ---------------------------------------------------------------------------

// Build a multipart/form-data body for the /v1/images/edits endpoint.
// Uses Node's built-in FormData + Blob (no external deps).
// NOTE: Buffer-backed Blobs are replayable, so retries in fetchWithRetry
// work correctly. Do not switch to streams without revisiting retry safety.
function appendSharedFormFields(form, args, outputFormat) {
  const normalized = normalizeRequest(args, outputFormat);
  form.append("model", normalized.model);
  form.append("prompt", normalized.prompt);
  form.append("size", args.size);
  form.append("quality", args.quality);
  form.append("output_format", normalized.outputFormat);
  if (normalized.background !== "auto") {
    form.append("background", normalized.background);
  }
  if (args.outputCompression !== null) {
    form.append("output_compression", String(args.outputCompression));
  }
}

function buildEditForm(args, outputFormat) {
  const form = new FormData();
  appendSharedFormFields(form, args, outputFormat);

  // Single image: field name "image". Multiple: "image[]".
  const fieldName = args.images.length === 1 ? "image" : "image[]";
  for (const imgPath of args.images) {
    const ext = path.extname(imgPath).toLowerCase();
    const mime = MIME_TYPES[ext];
    const buf = fs.readFileSync(imgPath);
    const blob = new Blob([buf], { type: mime });
    form.append(fieldName, blob, path.basename(imgPath));
  }

  if (args.mask) {
    const maskBuf = fs.readFileSync(args.mask);
    const maskBlob = new Blob([maskBuf], { type: "image/png" });
    form.append("mask", maskBlob, path.basename(args.mask));
  }

  return form;
}

function buildHeaders(apiKey, clientRequestId, isMultipart = false) {
  const headers = {
    Authorization: `Bearer ${apiKey}`,
    "X-Client-Request-Id": clientRequestId,
  };
  if (!isMultipart) {
    headers["Content-Type"] = "application/json";
  }
  if (process.env.OPENAI_ORGANIZATION) {
    headers["OpenAI-Organization"] = process.env.OPENAI_ORGANIZATION;
  }
  if (process.env.OPENAI_PROJECT) {
    headers["OpenAI-Project"] = process.env.OPENAI_PROJECT;
  }
  return headers;
}

function buildGenerationBody(args, outputFormat) {
  const normalized = normalizeRequest(args, outputFormat);
  const requestBody = {
    model: normalized.model,
    prompt: normalized.prompt,
    size: args.size,
    quality: args.quality,
    output_format: normalized.outputFormat,
  };
  if (normalized.background !== "auto") {
    requestBody.background = normalized.background;
  }
  if (args.outputCompression !== null) {
    requestBody.output_compression = args.outputCompression;
  }
  return requestBody;
}

function chromaKeyPromptSuffix(color) {
  return CHROMA_KEY_PROMPT_SUFFIX.replace("{color}", color.toLowerCase());
}

function normalizeRequest(args, outputFormat) {
  if (args.background === "transparent" && args.transparentMode === "chroma-key") {
    return {
      model: "gpt-image-2",
      prompt: `${args.prompt}\n\n${chromaKeyPromptSuffix(args.chromaKey)}`,
      background: "opaque",
      outputFormat: "png",
    };
  }
  return {
    model: args.model,
    prompt: args.prompt,
    background: args.background,
    outputFormat,
  };
}

function buildPostprocessSummary(args) {
  if (args.background !== "transparent" || args.transparentMode !== "chroma-key") return null;
  return {
    type: "chroma-key",
    chromaKey: args.chromaKey.toLowerCase(),
    tolerance: args.chromaTolerance,
    status: "pending-local-png-processing",
  };
}

function buildDryRun(args, outputFormat, outputPath, clientRequestId) {
  const isEdit = args.images.length > 0;
  const endpoint = isEdit ? "https://api.openai.com/v1/images/edits" : "https://api.openai.com/v1/images/generations";
  const params = buildGenerationBody(args, outputFormat);
  if (isEdit) {
    params.imageFields = args.images.map((imgPath) => ({
      field: args.images.length === 1 ? "image" : "image[]",
      path: imgPath,
    }));
    if (args.mask) params.mask = args.mask;
  }
  return {
    success: true,
    dryRun: true,
    mode: isEdit ? "edit" : "generation",
    endpoint,
    method: "POST",
    model: args.model,
    background: args.background,
    transparentMode: args.transparentMode,
    ...(args.fallbackModel ? { fallbackModel: args.fallbackModel } : {}),
    ...(args.transparentMode === "chroma-key" ? { chromaKey: args.chromaKey } : {}),
    ...(buildPostprocessSummary(args) ? { postprocess: buildPostprocessSummary(args) } : {}),
    output: outputPath,
    outputFormat,
    clientRequestId,
    params,
  };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const args = parseArgs(process.argv);
  validate(args);

  // Ensure output directory exists
  const outputDir = path.dirname(path.resolve(args.output));
  if (!args.dryRun) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // Determine output format from file extension
  const ext = path.extname(args.output).toLowerCase();
  const outputFormat = VALID_EXTENSIONS[ext]; // Already validated
  const outputPath = path.resolve(args.output);
  const clientRequestId = args.clientRequestId || crypto.randomUUID();

  if (args.dryRun) {
    process.stdout.write(JSON.stringify(buildDryRun(args, outputFormat, outputPath, clientRequestId)) + "\n");
    return;
  }

  // Check API key
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    fail(
      "OPENAI_API_KEY environment variable is not set. " +
      "See https://platform.openai.com/api-keys to create one.",
      { clientRequestId }
    );
  }

  const isEdit = args.images.length > 0;
  let url, fetchOptions;

  if (isEdit) {
    // --- Edits endpoint (multipart/form-data) ---
    url = "https://api.openai.com/v1/images/edits";
    const form = buildEditForm(args, outputFormat);
    fetchOptions = {
      method: "POST",
      // Do NOT set Content-Type - fetch auto-sets the multipart boundary.
      headers: buildHeaders(apiKey, clientRequestId, true),
      body: form,
    };
  } else {
    // --- Generations endpoint (JSON) ---
    url = "https://api.openai.com/v1/images/generations";
    // NOTE: Do NOT include `response_format` - gpt-image-2 returns b64_json.
    const requestBody = buildGenerationBody(args, outputFormat);
    fetchOptions = {
      method: "POST",
      headers: buildHeaders(apiKey, clientRequestId, false),
      body: JSON.stringify(requestBody),
    };
  }

  // Call the API
  const response = await fetchWithRetry(url, fetchOptions, clientRequestId);
  const openaiRequestId = response.headers?.get?.("x-request-id") || null;

  // Parse response
  let data;
  try {
    data = await response.json();
  } catch (err) {
    fail(`Failed to parse API response as JSON: ${err.message}`);
  }

  // Extract the base64 image data
  // gpt-image-2 returns b64_json for Image API responses.
  const imageData = data?.data?.[0];
  if (!imageData || !imageData.b64_json) {
    fail("Unexpected API response: no image data (b64_json) returned.");
  }

  let imageBuffer = Buffer.from(imageData.b64_json, "base64");
  let postprocessResult = null;
  if (args.background === "transparent" && args.transparentMode === "chroma-key") {
    try {
      postprocessResult = chromaKeyPng(imageBuffer, {
        chromaKey: args.chromaKey,
        tolerance: args.chromaTolerance,
      });
      imageBuffer = postprocessResult.buffer;
    } catch (err) {
      if (err instanceof Imagegen2Error) {
        fail(err.message, { clientRequestId, openaiRequestId, ...err.extra });
      }
      throw err;
    }
  }

  // Write to file
  try {
    fs.writeFileSync(outputPath, imageBuffer);
  } catch (err) {
    fail(`Failed to write image to "${outputPath}": ${err.message}`, { clientRequestId, openaiRequestId });
  }

  // Auto-derive history ID from output path if not provided
  // Uses relative path minus extension to avoid collisions (e.g.,
  // "assets/sprites/snake-idle" instead of just "snake-idle")
  const historyId = args.historyId ||
    args.output.replace(/\.[^.]+$/, "").replace(/^\.\//, "");

  // Build result
  const result = {
    success: true,
    output: outputPath,
    historyId: historyId,
    size: args.size,
    quality: args.quality,
    background: args.background,
    model: args.model,
    transparentMode: args.transparentMode,
    ...(args.fallbackModel ? { fallbackModel: args.fallbackModel } : {}),
    ...(postprocessResult ? {
      postprocess: {
        type: "chroma-key",
        status: "completed",
        ...postprocessResult.stats,
      },
    } : {}),
    clientRequestId,
    openaiRequestId,
    ...(args.outputCompression !== null ? { outputCompression: args.outputCompression } : {}),
    bytes: imageBuffer.length,
  };

  if (isEdit) {
    result.inputImages = args.images;
    if (args.mask) result.mask = args.mask;
  }

  // Append to history file (best-effort — never fail the generation over this)
  if (!args.noHistory) {
    const historyEntry = {
      id: historyId,
      timestamp: new Date().toISOString(),
      prompt: args.prompt,
      output: args.output, // Keep as provided (relative path)
      params: {
        size: args.size,
        quality: args.quality,
        background: args.background,
        ...(args.background === "transparent" && args.transparentMode === "chroma-key" ? {
          requestBackground: "opaque",
          chromaKey: args.chromaKey.toLowerCase(),
          chromaTolerance: args.chromaTolerance,
        } : {}),
        model: args.model,
        transparentMode: args.transparentMode,
        ...(args.fallbackModel ? { fallbackModel: args.fallbackModel } : {}),
        clientRequestId,
        openaiRequestId,
        ...(args.outputCompression !== null ? { outputCompression: args.outputCompression } : {}),
      },
      parentId: args.historyParent || null,
      bytes: imageBuffer.length,
      outputFormat: outputFormat,
    };
    if (postprocessResult) {
      historyEntry.postprocess = {
        type: "chroma-key",
        status: "completed",
        ...postprocessResult.stats,
      };
    }

    if (args.images.length > 0) {
      historyEntry.inputImages = args.images;
    }
    if (args.mask) {
      historyEntry.mask = args.mask;
    }
    try {
      fs.appendFileSync(
        path.resolve(".imagegen2-history.jsonl"),
        JSON.stringify(historyEntry) + "\n"
      );
    } catch (err) {
      result.historyWarning = `Failed to write history: ${err.message}`;
    }
  }

  process.stdout.write(JSON.stringify(result) + "\n");
}

if (require.main === module) {
  main().catch((err) => {
    fail(`Unexpected error: ${err.message}`);
  });
} else {
  module.exports = {
    Imagegen2Error,
    parsePng,
    encodeRgbaPng,
    alphaBleedTransparentPixels,
    suppressKeySpillOnVisibleEdges,
    chromaKeyPng,
  };
}
