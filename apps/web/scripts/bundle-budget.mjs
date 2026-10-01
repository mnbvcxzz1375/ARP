#!/usr/bin/env node
/**
 * Bundle budget check for the single AgentNet web build (stage 4 guard).
 *
 * The split decision (docs/platform-split-decision.md, option A) keeps one
 * Vite app as long as the platform boundary holds. The measurable
 * last-straw signal for revisiting that decision is bundle bloat: this
 * script sizes every chunk under dist/assets and fails when a single
 * chunk or the total exceeds the budget. Raw (uncompressed) bytes are
 * measured because they are what `ls`/CI sees directly; thresholds are
 * therefore calibrated on raw bytes, not gzip.
 *
 * Usage:
 *   node scripts/bundle-budget.mjs                      # dist/assets, defaults
 *   node scripts/bundle-budget.mjs dist/assets          # explicit dir
 *   node scripts/bundle-budget.mjs --single 1400        # override single-chunk budget (KiB)
 *   node scripts/bundle-budget.mjs --total 4200         # override total budget (KiB)
 *
 * Environment overrides (same names, for CI): BUNDLE_SINGLE_KIB,
 * BUNDLE_TOTAL_KIB. CLI flags win over env, defaults win over nothing.
 *
 * Exit codes: 0 = within budget, 1 = breach (or the dir is missing), so a
 *CI step can gate on it.
 */
import { readdir, stat } from 'node:fs/promises';
import { extname, join, resolve } from 'node:path';

// Calibrated 2026-10-01 against the post-lazy-loading baseline (82 chunks,
// 1171 KiB total, largest = docsSite 532 KiB). Single-chunk headroom ~50%
// over the docsSite markdown chain, total ~2x - enough for feature growth,
// tight enough that naive re-bundling trips the split review.
const DEFAULT_SINGLE_KIB = 800; // largest acceptable single chunk
const DEFAULT_TOTAL_KIB = 2400; // largest acceptable dist/assets total

function parseArgs(argv) {
  const args = { dir: 'dist/assets', single: null, total: null };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--single') args.single = Number(argv[++i]);
    else if (arg === '--total') args.total = Number(argv[++i]);
    else if (!arg.startsWith('--')) args.dir = arg;
  }
  return args;
}

function kib(bytes) {
  return (bytes / 1024).toFixed(1);
}

async function collectAssets(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await collectAssets(fullPath)));
    } else if (extname(entry.name) === '.js' || extname(entry.name) === '.css') {
      const { size } = await stat(fullPath);
      files.push({ name: entry.name, path: fullPath, size });
    }
  }
  return files;
}

const args = parseArgs(process.argv.slice(2));
const assetsDir = resolve(process.cwd(), args.dir);
const singleKib =
  Number.isFinite(args.single) && args.single > 0
    ? args.single
    : Number(process.env.BUNDLE_SINGLE_KIB) || DEFAULT_SINGLE_KIB;
const totalKib =
  Number.isFinite(args.total) && args.total > 0
    ? args.total
    : Number(process.env.BUNDLE_TOTAL_KIB) || DEFAULT_TOTAL_KIB;

try {
  const files = await collectAssets(assetsDir);
  if (files.length === 0) {
    console.error(`[bundle-budget] no .js/.css assets under ${assetsDir}`);
    process.exit(1);
  }
  files.sort((a, b) => b.size - a.size);
  const total = files.reduce((sum, f) => sum + f.size, 0);
  const largest = files[0];

  console.log(`[bundle-budget] ${assetsDir}: ${files.length} chunks, total ${kib(total)} KiB`);
  for (const f of files.slice(0, 8)) {
    console.log(`  ${kib(f.size).padStart(9)} KiB  ${f.name}`);
  }
  if (files.length > 8) console.log(`  ... ${files.length - 8} more`);

  const breaches = [];
  if (largest.size > singleKib * 1024) {
    breaches.push(
      `single chunk ${largest.name} is ${kib(largest.size)} KiB > ${singleKib} KiB budget`,
    );
  }
  if (total > totalKib * 1024) {
    breaches.push(`total ${kib(total)} KiB > ${totalKib} KiB budget`);
  }
  if (breaches.length > 0) {
    console.error('[bundle-budget] BUDGET BREACH: ' + breaches.join('; '));
    console.error(
      '[bundle-budget] see docs/platform-split-review-cadence.md: bundle bloat over threshold is a split trigger.',
    );
    process.exit(1);
  }
  console.log('[bundle-budget] within budget');
  process.exit(0);
} catch (err) {
  console.error(`[bundle-budget] cannot read ${assetsDir}: ${err.message}`);
  console.error('[bundle-budget] run `npx vite build` first (output: dist/)');
  process.exit(1);
}
