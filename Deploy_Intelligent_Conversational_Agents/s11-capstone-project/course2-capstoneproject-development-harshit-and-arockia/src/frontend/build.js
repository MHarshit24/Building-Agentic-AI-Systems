/**
 * Frontend build script — run by Vercel at deploy time.
 *
 * Reads config from Vercel Environment Variables (set in the dashboard
 * or via `vercel env add`), replaces %%PLACEHOLDER%% markers in index.html,
 * and writes the result to dist/index.html.
 *
 * Required Vercel env vars (set under Project → Settings → Environment Variables):
 *   AUTH0_DOMAIN
 *   AUTH0_CLIENT_ID
 *   AUTH0_AUDIENCE
 *   BACKEND_URL
 */

const fs   = require('fs');
const path = require('path');

const REQUIRED = ['AUTH0_DOMAIN', 'AUTH0_CLIENT_ID', 'AUTH0_AUDIENCE', 'BACKEND_URL'];

// ── Collect values (from process.env, set by Vercel at build time) ─────────
const vars = {};
const missing = [];

for (const key of REQUIRED) {
  const val = (process.env[key] || '').trim();
  if (!val) {
    missing.push(key);
  } else {
    vars[key] = val;
  }
}

if (missing.length > 0) {
  console.error(`\nBuild failed — missing environment variables:\n  ${missing.join('\n  ')}`);
  console.error('\nSet them in the Vercel dashboard → Project → Settings → Environment Variables\n');
  process.exit(1);
}

// ── Read template ──────────────────────────────────────────────────────────
const srcPath = path.join(__dirname, 'index.html');
let html = fs.readFileSync(srcPath, 'utf8');

// ── Replace %%PLACEHOLDERS%% ───────────────────────────────────────────────
for (const [key, value] of Object.entries(vars)) {
  const placeholder = `%%${key}%%`;
  if (!html.includes(placeholder)) {
    console.warn(`  Warning: placeholder ${placeholder} not found in index.html`);
  }
  html = html.split(placeholder).join(value);
}

// ── Write to dist/ ─────────────────────────────────────────────────────────
const distDir = path.join(__dirname, 'dist');
fs.mkdirSync(distDir, { recursive: true });
fs.writeFileSync(path.join(distDir, 'index.html'), html, 'utf8');

console.log('\nBuild complete → dist/index.html');
console.log('Variables injected:');
for (const key of REQUIRED) {
  console.log(`  %%${key}%% = ${vars[key]}`);
}
