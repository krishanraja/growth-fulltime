// The Switch, revision 1: the approved Full Time social kit (brand/social-kit/README.md).
// node brand/social-kit/render.js
//   reads   local/brand-kit/assets/ (made by prepare-assets.mjs)
//   writes  local/brand-kit/board.html, local/brand-kit/frames/<library name>.png at true pixel size,
//           and local/brand-kit/manifest.json (sha256 and bytes of every output)
// Fails (exit 1) on: a locked file that differs from LOCK.json, missing assets, text outside the
// 9:16 safe area, text overflow, banned copy, a grid rule break.
// BRAND_KIT_DIR moves local/brand-kit somewhere else (the folder must hold assets/).
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const KIT = __dirname;
const ROOT = path.resolve(KIT, '..', '..');
const OUT = path.resolve(process.env.BRAND_KIT_DIR || path.join(ROOT, 'local', 'brand-kit'));
const ASSETS = path.join(OUT, 'assets');
const FRAMES = path.join(OUT, 'frames');
const read = f => fs.readFileSync(path.join(KIT, f), 'utf8');
const lf = buf => Buffer.from(buf.toString('binary').replace(/\r\n/g, '\n'), 'binary');
const sha256 = buf => crypto.createHash('sha256').update(buf).digest('hex');

/* The lock: spec.md, templates.js and slots.json must be the approved revision, byte for byte (CRLF read as LF). */
function lock(){
  const L = JSON.parse(read('LOCK.json'));
  const bad = Object.entries(L.files).filter(([f, h]) => sha256(lf(fs.readFileSync(path.join(KIT, f)))) !== h).map(([f]) => f);
  if (bad.length) throw new Error(`locked kit file changed: ${bad.join(', ')}. A change needs a new revision approved by Krish (README.md).`);
  return Object.assign({}, L, {lock_sha256: sha256(lf(fs.readFileSync(path.join(KIT, 'LOCK.json'))))});
}
/* Growth Build library name for 05_Brand-Kit: <ISO week of the approval>_social-kit-<frame>_v<revision>.png */
function isoWeek(date){
  const d = new Date(date + 'T12:00:00Z'), day = (d.getUTCDay() + 6) % 7;
  d.setUTCDate(d.getUTCDate() - day + 3);
  const year = d.getUTCFullYear(), jan4 = new Date(Date.UTC(year, 0, 4));
  const week = 1 + Math.round(((d - jan4) / 864e5 - 3 + ((jan4.getUTCDay() + 6) % 7)) / 7);
  return `${year}-W${String(week).padStart(2, '0')}`;
}
const frameName = (L, id) => `${isoWeek(L.approved_on)}_social-kit-${id.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}_v${L.revision}.png`;

const CSS = `
:root{--ground:#1c1611;--ground2:#15110d;--raise:#261f19;--ink:#f1e9da;--ink2:#b9ac98;--ink3:#998c7a;--hair:rgba(241,233,218,.13);
--lime:oklch(0.88 0.24 138);--serif:'Instrument Serif',Georgia,serif;--sans:'Schibsted Grotesk',system-ui,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--ground2);color:var(--ink);font-family:var(--sans);-webkit-font-smoothing:antialiased}
body.only{background:#000}
.it{font-style:italic}.serif{font-family:var(--serif);font-weight:400}.sans{font-family:var(--sans)}
.hy{margin:0 -.075em 0 -.05em}
.cap{font-family:var(--sans);font-weight:600;letter-spacing:.14em;text-transform:uppercase;white-space:nowrap}
.ab{position:relative;overflow:hidden;color:var(--ink);font-family:var(--sans)}
.abs{position:absolute}
.strip{position:absolute;display:flex;background:var(--ground)}
.tab{flex:1;position:relative;display:flex;align-items:center;padding-left:.5em;font-weight:700;color:rgba(241,233,218,.7)}
.tab.lit{flex:2.1;color:var(--ink)}.tab.lit b{font-weight:600;letter-spacing:.14em;margin-right:.36em;opacity:.9}
.tab.on{color:rgba(241,233,218,.85)}
.tab.off{opacity:.38}
.seal{position:absolute}.seal img{position:absolute;inset:0;width:100%;height:100%}
.seal .c{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
.seal .ft{font-weight:700;letter-spacing:.3em;text-transform:uppercase;color:var(--ink2);padding-left:.3em;white-space:nowrap}
.seal .sc{font-family:var(--serif);line-height:.86;color:var(--ink);white-space:nowrap}
.seal .dash{display:inline-block;transform:translateY(-.06em);margin:0 .06em}
.seal .dt{font-weight:600;letter-spacing:.24em;color:var(--ink3);padding-left:.24em;white-space:nowrap}
.capt{font:700 64px/1.12 var(--sans);letter-spacing:-.01em;color:var(--ink)}
.capt .now{text-decoration:underline;text-decoration-thickness:6px;text-underline-offset:10px}
.capt .next{color:rgba(241,233,218,.4)}
.ov .zone{background:repeating-linear-gradient(135deg,rgba(21,17,13,.78) 0 14px,rgba(21,17,13,.5) 14px 28px)}
.ov .zl{font:700 30px var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--ink);background:rgba(0,0,0,.6);padding:8px 14px}
.ov .sl{font:700 24px var(--sans);background:var(--ink);color:var(--ground);padding:3px 10px;white-space:nowrap}
/* board */
.board{width:1640px;margin:0 auto;padding:64px 64px 120px}
.hd{padding-bottom:8px}
.hd .k,.board h2{font:600 14px var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--ink2)}
.hd h1{font:400 96px/1 var(--serif);margin-top:10px}.hd h1 em{font-style:italic}
.board section{margin-top:56px}
.board h2{margin-bottom:20px;padding-top:16px;border-top:1px solid var(--hair)}
.row{display:flex;gap:28px;align-items:flex-start;flex-wrap:wrap;margin-bottom:32px}
.col{display:flex;flex-direction:column;gap:20px}
.fr{margin:0;display:flex;flex-direction:column;gap:10px}
.fr .box{position:relative;overflow:hidden;outline:1px solid var(--hair)}
figcaption{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:baseline;font-size:13px;color:var(--ink2)}
figcaption b{color:var(--ink);font-weight:600}
figcaption em{font-style:normal;font-size:11px;letter-spacing:.1em;text-transform:uppercase;border:1px solid var(--hair);padding:2px 6px;color:var(--ink2)}
.two{display:grid;grid-template-columns:740px 1fr;gap:48px}
.spec h3{font:400 28px var(--serif);margin:26px 0 10px}
.spec p,.spec li{font-size:15px;line-height:1.55;color:var(--ink2)}
.spec ul,.spec ol{padding-left:20px}.spec li{margin-bottom:6px}
.spec b{color:var(--ink);font-weight:600}
.tbl{border-collapse:collapse;width:100%;font-size:14px}
.tbl td,.tbl th{border-top:1px solid var(--hair);padding:7px 10px 7px 0;vertical-align:top;color:var(--ink2);text-align:left}
.tbl th{font-weight:600;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink3)}
.tbl td:first-child{color:var(--ink);font-weight:600}
.ch td{vertical-align:middle}.ch td:nth-child(2){white-space:nowrap}.ch .sw{display:block;width:22px;height:22px}
.sf{font-family:var(--serif);font-size:19px;color:var(--ink)}.sf em,em.sf{font-style:italic}
`;

const page = slots => `<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Switch r1</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Schibsted+Grotesk:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>${CSS}</style></head><body><div id="root"></div>
<script>window.SLOTS=${JSON.stringify(slots)};</script>
<script>
window.__ready = (async () => {
  await Promise.all(["400 100px 'Instrument Serif'","italic 400 100px 'Instrument Serif'","500 30px 'Schibsted Grotesk'","600 30px 'Schibsted Grotesk'","700 30px 'Schibsted Grotesk'","800 30px 'Schibsted Grotesk'"].map(f => document.fonts.load(f)));
  await document.fonts.ready;
  const s = document.createElement('script'); s.textContent = ${JSON.stringify(read('templates.js'))}; document.body.appendChild(s);
  const only = new URLSearchParams(location.search).get('only');
  if (only) { document.body.classList.add('only'); document.getElementById('root').innerHTML = window.FT.ART[only].html(); }
  else { const b = document.createElement('script'); b.textContent = ${JSON.stringify(read('board.js'))}; document.body.appendChild(b); }
  await Promise.all([...document.images].map(i => i.complete ? 1 : new Promise(r => { i.onload = i.onerror = r; })));
  return true;
})();
</script></body></html>`;

/* '\u2014' is the em dash: no kit copy may carry one. */
const BANNED = ['\u2014', 'game-changing', 'next-generation', 'must-listen', 'unmissable', 'unbiased', 'seamless', 'revolutionary', 'AI-powered', 'They do not agree', 'thinks this is wrong', 'Switched from', 'scored early', 'more of the ball', 'ember'];
const LAUNCH = { args: ['--disable-gpu', '--font-render-hinting=none', '--disable-lcd-text', '--disable-partial-raster', '--num-raster-threads=1'] };

/* Runs in the page: every reason an artboard is refused. */
function checkArt({ id, ov, BANNED }){
  const out = [], root = document.querySelector('#root > .ab'), R = root.getBoundingClientRect();
  const W = R.width, H = R.height, tall = H === 1920 && !ov;
  const txt = root.innerText;
  BANNED.forEach(b => { if (txt.toLowerCase().includes(b.toLowerCase())) out.push('banned copy: ' + b); });
  if (id === 'grid' || id === 'check_180') return out;
  root.querySelectorAll('.t').forEach(e => {
    if (e.closest('.ov')) return;
    const rg = document.createRange(); rg.selectNodeContents(e); const r = rg.getBoundingClientRect();
    const x0 = r.left - R.left, y0 = r.top - R.top, x1 = r.right - R.left, y1 = r.bottom - R.top;
    const name = (e.innerText || '').slice(0, 28).replace(/\n/g, ' ');
    if (x0 < -1 || y0 < -1 || x1 > W + 1 || y1 > H + 1) out.push(`out of artboard "${name}" ${[x0, y0, x1, y1].map(Math.round)}`);
    if (tall && (y0 < 220 || y1 > 1500 || x1 > 940)) out.push(`unsafe "${name}" ${[x0, y0, x1, y1].map(Math.round)}`);
    if (e.scrollWidth > e.clientWidth + 2 && getComputedStyle(e).display === 'block') out.push(`overflow "${name}"`);
    if (id.startsWith('thumb') && x1 > 1150 && y1 > 660) out.push(`timestamp zone "${name}"`);
  });
  return out;
}

function needAssets(){
  if (!fs.existsSync(path.join(ASSETS, 'matches.json'))) throw new Error(`no kit assets in ${ASSETS}. Run: node brand/social-kit/prepare-assets.mjs <full-time checkout>`);
}
/* The page lives next to assets/ so the templates' relative asset paths resolve. */
function writePage(name, slots){
  fs.mkdirSync(OUT, { recursive: true });
  const file = path.join(OUT, name);
  fs.writeFileSync(file, page(slots));
  return require('url').pathToFileURL(file).href;
}

async function main(){
  const { chromium } = require('playwright');
  const L = lock();
  needAssets();
  const slots = JSON.parse(read('slots.json'));
  const url = writePage('board.html', slots);
  fs.mkdirSync(FRAMES, { recursive: true });
  const br = await chromium.launch(LAUNCH);
  let fail = 0;
  const flagged = {}, outputs = [];
  const save = (file, id, w, h) => { const b = fs.readFileSync(file); outputs.push({ file: path.basename(file), artboard: id, width: w, height: h, bytes: b.length, sha256: sha256(b) }); };
  const p0 = await br.newPage();
  await p0.goto(url + '?only=take_first_zen', { waitUntil: 'networkidle' });
  await p0.evaluate(() => window.__ready);
  const arts = await p0.evaluate(() => Object.fromEntries(Object.entries(window.FT.ART).map(([k, a]) => [k, [a.w, a.h, a.d.overlay || '']])));
  await p0.close();
  for (const [id, [w, h, ov]] of Object.entries(arts)) {
    const p = await br.newPage({ viewport: { width: w, height: h } });
    await p.goto(url + '?only=' + id, { waitUntil: 'networkidle' });
    await p.evaluate(() => window.__ready);
    await p.waitForTimeout(200);
    const issues = await p.evaluate(checkArt, { id, ov, BANNED });
    if (issues.length) { fail++; flagged[id] = issues; console.log(id + ':\n  ' + issues.join('\n  ')); }
    const file = path.join(FRAMES, frameName(L, id));
    await p.screenshot({ path: file, clip: { x: 0, y: 0, width: w, height: h } });
    save(file, id, w, h);
    await p.close();
  }
  const pb = await br.newPage({ viewport: { width: 1640, height: 1200 } });
  await pb.goto(url, { waitUntil: 'networkidle' });
  await pb.evaluate(() => window.__ready);
  await pb.waitForTimeout(400);
  const board = path.join(FRAMES, frameName(L, 'board'));
  await pb.screenshot({ path: board, fullPage: true });
  save(board, 'board', 1640, null);
  await br.close();
  const manifest = { schema_version: 1, kit: L.kit, revision: L.revision, approval: L.approval, approved_on: L.approved_on,
    lock_sha256: L.lock_sha256, rendered_at: new Date().toISOString(), checks_passed: !fail, flagged, outputs };
  fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 1) + '\n');
  console.log(fail ? `done with ${fail} artboard(s) flagged` : `done, all checks pass: ${outputs.length} frames in ${FRAMES}`);
  process.exitCode = fail ? 1 : 0;
}

module.exports = { KIT, ROOT, OUT, ASSETS, CSS, BANNED, LAUNCH, page, checkArt, lock, needAssets, writePage, sha256, lf, isoWeek };
if (require.main === module) main().catch(e => { console.error(e.message || e); process.exitCode = 1; });
