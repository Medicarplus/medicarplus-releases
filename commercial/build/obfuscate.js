#!/usr/bin/env node
/**
 * Caja del Día — obfuscation build step (Fase 7)
 *
 * Reads the source HTML, obfuscates the inline <script> block(s) with sensible
 * defaults, and writes the result to the Electron packaging directory.
 *
 * IMPORTANT: This is ONLY run before packaging the Electron installer. The
 * development files under /app/frontend/public/ remain unobfuscated so the app
 * is still hot-reloadable during dev.
 *
 * Usage:
 *   node obfuscate.js                    # default: v2.html → electron/index.html
 *   node obfuscate.js <input> <output>   # custom paths
 *
 * Notes on settings:
 *   - `renameGlobals: false` — leaves module-level names alone (safe for
 *     Vanilla JS apps that expose helpers globally). Nested identifiers inside
 *     functions are still renamed.
 *   - `stringArray + base64` — moves string literals (including the MASTER_KEY,
 *     LIC config keys, error messages) into a base64-encoded array, making
 *     Ctrl+F reverse engineering ineffective.
 *   - `controlFlowFlattening: false`, `deadCodeInjection: false` — these two
 *     bloat size 4-10x and slow startup. Not worth it for a client-side app.
 *   - `selfDefending: true` — anti-tamper: the code detects beautification and
 *     debugger tampering, throws infinite loops if triggered. Small cost, big
 *     deterrent.
 *   - The `<script src="…xlsx…">` external CDN tag is NOT matched because our
 *     regex only catches `<script>` opening WITHOUT attributes.
 *   - Nested inline scripts inside `w.document.write("…<\\/script>")` template
 *     strings are NOT matched because the escaped `\\/` prevents the regex
 *     from stopping there.
 */
const fs = require("fs");
const path = require("path");
const JavaScriptObfuscator = require("javascript-obfuscator");

const ROOT = path.resolve(__dirname, "..", "..");
const DEFAULT_INPUT = path.join(ROOT, "frontend", "public", "v2.html");
const DEFAULT_OUTPUT = path.join(ROOT, "commercial", "electron", "index.html");

const args = process.argv.slice(2);
const input = args[0] || DEFAULT_INPUT;
const output = args[1] || DEFAULT_OUTPUT;

if (!fs.existsSync(input)) {
  console.error("[obfuscate] Input file not found:", input);
  process.exit(1);
}

console.log("[obfuscate] Reading   :", input);
const originalHtml = fs.readFileSync(input, "utf8");
const originalSize = Buffer.byteLength(originalHtml, "utf8");

// Regex matches inline <script> tags WITHOUT attributes (i.e. our app code,
// not the xlsx CDN which has src="…"). The lazy [\s\S]*? correctly stops at
// the FIRST literal </script>, ignoring escaped `<\/script>` inside template
// strings used by w.document.write() for print windows.
const inlineRe = /<script>([\s\S]*?)<\/script>/g;

const options = {
  compact: true,
  controlFlowFlattening: false,
  deadCodeInjection: false,
  debugProtection: false,
  disableConsoleOutput: false,
  identifierNamesGenerator: "hexadecimal",
  log: false,
  numbersToExpressions: false,
  renameGlobals: false,
  selfDefending: true,
  simplify: true,
  splitStrings: true,
  splitStringsChunkLength: 10,
  stringArray: true,
  stringArrayCallsTransform: true,
  stringArrayEncoding: ["base64"],
  stringArrayIndexShift: true,
  stringArrayRotate: true,
  stringArrayShuffle: true,
  stringArrayThreshold: 0.75,
  transformObjectKeys: false, // keep object keys readable (localStorage keys, JSON payloads)
  unicodeEscapeSequence: false,
  target: "browser",
};

let blockCount = 0;
let inputSizeJs = 0;
let outputSizeJs = 0;

const obfuscated = originalHtml.replace(inlineRe, (full, code) => {
  blockCount++;
  inputSizeJs += Buffer.byteLength(code, "utf8");
  const t0 = Date.now();
  const result = JavaScriptObfuscator.obfuscate(code, options).getObfuscatedCode();
  outputSizeJs += Buffer.byteLength(result, "utf8");
  console.log(
    `[obfuscate] Block ${blockCount}: ${code.length} → ${result.length} chars (${((Date.now() - t0) / 1000).toFixed(2)}s)`,
  );
  return `<script>${result}</script>`;
});

// Add a build-time banner comment right before </head> so we know an HTML is
// the obfuscated variant.
const banner = `<!-- Caja del Día · commercial build · obfuscated ${new Date().toISOString()} -->`;
const finalHtml = obfuscated.replace(/<\/head>/i, `${banner}\n</head>`);

fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, finalHtml);
const outSize = Buffer.byteLength(finalHtml, "utf8");

console.log("[obfuscate] Wrote     :", output);
console.log("[obfuscate] Blocks    :", blockCount);
console.log(
  `[obfuscate] HTML size : ${(originalSize / 1024).toFixed(1)} KB → ${(outSize / 1024).toFixed(1)} KB`,
);
console.log(
  `[obfuscate] JS size   : ${(inputSizeJs / 1024).toFixed(1)} KB → ${(outputSizeJs / 1024).toFixed(1)} KB (${((outputSizeJs / inputSizeJs) * 100).toFixed(0)}%)`,
);

if (blockCount === 0) {
  console.error("[obfuscate] WARNING: no inline <script> blocks found.");
  process.exit(2);
}
