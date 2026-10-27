#!/usr/bin/env node
// The Switch, revision 1: make the kit's assets from a Full Time product checkout.
//
//   node brand/social-kit/prepare-assets.mjs [full-time checkout] [--instance take.json ...]
//
// The checkout is the first argument, else FULL_TIME_REPO, else ../full-time beside this
// repository. Its cover, seal and atmosphere code (src/lib) is copied into a temporary
// folder with its relative imports patched to .ts, run with Node's type stripping, and
// deleted. Covers, seals, atmospheres, matches.json and the two product PNGs land in
// local/brand-kit/assets/ (or BRAND_KIT_DIR/assets/). Nothing here is committed: the
// repository is public and these are product files.
//
// The four published matches the approved board uses are built in. Each --instance names a
// take_clip instance (take_clip.js) whose match is added, so its cover and seal exist too.
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const KIT = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(KIT, '..', '..');
const OUT = resolve(process.env.BRAND_KIT_DIR || join(ROOT, 'local', 'brand-kit'), 'assets');

// The product files render.ts used, as copied for the approved board.
const SOURCES = ['pundit-cover.ts', 'match-seal.ts', 'match-atmosphere.ts', 'colour.ts', 'club-colours.ts',
  'premier-league.ts', 'pundit/types.ts'];
const STATIC = [['public/podcast-cover.png', 'podcast-cover.png'], ['src/assets/full-time-wordmark-trim.png', 'full-time-wordmark-trim.png']];
// The four real published matches on the approved board (slots.json), with the drop each seal is seeded from.
const MATCHES = [
  { date: '2026-10-19', drop: '519f3f12-1f7d-411a-9021-9f128ffd8496', home: 'Tottenham', away: 'Coventry', score: [3, 1] },
  { date: '2026-10-11', drop: '4e640fad-e3ea-400e-9e1f-e8481ff9a182', home: 'Crystal Palace', away: 'Nottingham Forest', score: [3, 1] },
  { date: '2026-09-20', drop: '18f075fd-3c2b-47d1-b2ed-c1ebda74acd5', home: 'Manchester City', away: 'Sunderland', score: [5, 3] },
  { date: '2026-09-19', drop: '8b7b68ac-9618-49be-b810-da65eeddc21e', home: 'Tottenham', away: 'Aston Villa', score: [2, 3] },
];

// The generator: render.ts from the approved board, reading its matches from a file.
const GENERATOR = `import { coverArt, COVER_WIDTH, COVER_HEIGHT, PUNDIT_HUES } from "./src/pundit-cover.ts";
import { sealPlate, sealTrack, sealWeave } from "./src/match-seal.ts";
import { atmosphere } from "./src/match-atmosphere.ts";
import { clubColours, clubInks } from "./src/club-colours.ts";
import { writeFileSync, mkdirSync, readFileSync } from "node:fs";
const out = process.argv[2];
const matches = JSON.parse(readFileSync(process.argv[3], "utf8"));
mkdirSync(out, { recursive: true });
const meta: any[] = [];
for (const m of matches) {
  const slug = \`\${m.date}_\${m.home}-\${m.away}\`.toLowerCase().replace(/ /g, "-");
  const cm = { seed: m.drop, homeGoals: m.score[0], awayGoals: m.score[1], homeColours: clubColours(m.home), awayColours: clubColours(m.away) };
  for (const p of Object.keys(PUNDIT_HUES)) {
    writeFileSync(\`\${out}/cover_\${p}_\${slug}.svg\`, \`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 \${COVER_WIDTH} \${COVER_HEIGHT}">\${coverArt(p as any, cm)}</svg>\`);
  }
  const hi = clubInks(m.home), ai = clubInks(m.away);
  const seal = \`<svg xmlns="http://www.w3.org/2000/svg" viewBox="-10 -10 220 220">\${sealPlate(m.drop)}\${sealWeave({ seed: m.drop, homeGoals: m.score[0], awayGoals: m.score[1], home: hi, away: ai })}\${sealTrack()}</svg>\`;
  writeFileSync(\`\${out}/seal_\${slug}.svg\`, seal);
  const W = 1080, H = 1920;
  const atm = atmosphere({ seed: m.drop, homeGoals: m.score[0], awayGoals: m.score[1], home: hi, away: ai, width: W, height: H, cx: W / 2, cy: 760, radius: 330 });
  writeFileSync(\`\${out}/atmosphere_\${slug}.svg\`, \`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 \${W} \${H}" width="\${W}" height="\${H}"><rect width="\${W}" height="\${H}" fill="#15110d"/>\${atm}</svg>\`);
  meta.push({ ...m, slug, homeColours: cm.homeColours, awayColours: cm.awayColours });
}
writeFileSync(\`\${out}/matches.json\`, JSON.stringify({ hues: PUNDIT_HUES, matches: meta }, null, 1));
`;

const fail = message => { console.error(message); process.exit(1); };
const sha256 = buf => createHash('sha256').update(buf).digest('hex');
// Relative imports gain .ts, as Node's type stripping needs; type-only import() expressions are erased anyway.
const patch = text => text.replace(/(\bfrom\s+["'])(\.{1,2}\/[^"']+?)(["'])/g, (m, a, p, b) => (p.endsWith('.ts') ? m : `${a}${p}.ts${b}`));

const args = process.argv.slice(2);
const instances = [];
const positional = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--instance') instances.push(args[++i]);
  else if (args[i] === '--help' || args[i] === '-h') { console.log('node brand/social-kit/prepare-assets.mjs [full-time checkout] [--instance take.json ...]'); process.exit(0); }
  else positional.push(args[i]);
}
const repo = resolve(positional[0] || process.env.FULL_TIME_REPO || join(ROOT, '..', 'full-time'));
if (!existsSync(join(repo, 'src', 'lib', 'pundit-cover.ts'))) fail(`no Full Time checkout at ${repo} (pass its path, or set FULL_TIME_REPO)`);

const matches = MATCHES.slice();
for (const file of instances) {
  const it = JSON.parse(readFileSync(file, 'utf8'));
  for (const key of ['drop', 'date', 'home', 'away', 'score']) if (it[key] == null) fail(`${file}: instance has no ${key}`);
  if (!matches.some(m => m.drop === it.drop)) matches.push({ date: it.date, drop: it.drop, home: it.home, away: it.away, score: it.score });
}

const [major, minor] = process.versions.node.split('.').map(Number);
if (major < 22 || (major === 22 && minor < 6)) fail(`Node ${process.versions.node} cannot strip types; use Node 22.6 or later`);
const strip = major > 23 || (major === 23 && minor >= 6) ? [] : ['--experimental-strip-types'];

const work = mkdtempSync(join(tmpdir(), 'fulltime-kit-'));
try {
  const record = {};
  for (const rel of SOURCES) {
    const from = join(repo, 'src', 'lib', rel), to = join(work, 'src', rel);
    if (!existsSync(from)) fail(`the checkout has no src/lib/${rel}`);
    mkdirSync(dirname(to), { recursive: true });
    const text = readFileSync(from, 'utf8');
    record['src/lib/' + rel] = sha256(Buffer.from(text.replace(/\r\n/g, '\n')));
    writeFileSync(to, patch(text));
  }
  writeFileSync(join(work, 'package.json'), '{"type": "module"}\n');
  writeFileSync(join(work, 'generate.ts'), GENERATOR);
  writeFileSync(join(work, 'matches.json'), JSON.stringify(matches));
  mkdirSync(OUT, { recursive: true });
  const run = spawnSync(process.execPath, [...strip, '--no-warnings', join(work, 'generate.ts'), OUT, join(work, 'matches.json')], { stdio: 'inherit' });
  if (run.status !== 0) fail('the product cover and seal code did not run');
  for (const [rel, name] of STATIC) {
    const from = join(repo, rel);
    if (!existsSync(from)) fail(`the checkout has no ${rel}`);
    copyFileSync(from, join(OUT, name));
    record[rel] = sha256(readFileSync(from));
  }
  const git = spawnSync('git', ['-C', repo, 'rev-parse', 'HEAD'], { encoding: 'utf8' });
  writeFileSync(join(OUT, 'SOURCE.json'), JSON.stringify({ full_time_commit: git.status === 0 ? git.stdout.trim() : null,
    files: record, matches: matches.map(m => m.drop), prepared_at: new Date().toISOString() }, null, 1) + '\n');
  console.log(`kit assets for ${matches.length} matches in ${OUT}`);
} finally {
  rmSync(work, { recursive: true, force: true });
}
