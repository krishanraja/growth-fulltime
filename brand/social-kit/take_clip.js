// The Switch, revision 1: the still layers of one take_clip (brand/social-kit/README.md).
//
//   node brand/social-kit/take_clip.js <instance.json> [--out <folder>]
//
// Writes frame0.png (take_clip frame 0) and one plate-NNN.png per caption segment (the mid
// frame with that caption and an empty progress track), all 1080x1920, plus layers.json:
// the sha256 and bytes of each layer, the text each carries, the instance's sha256, the kit
// lock, and the exact rectangle and colour of the progress fill, measured in the page.
// The engine composes the video from these (python3 growth.py assets render <manifest>), and
// draws the growing lime fill itself. Default folder: local/brand-kit/layers/<instance name>/.
// Fails (exit 1), writing no layers.json, on any automatic check render.js makes, a caption
// over two lines, or a progress track that is not the same on every plate.
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const kit = require('./render.js');

const PUNDITS = ['zen', 'gaffer', 'stats', 'romantic', 'doomer', 'banter'];
const FIELDS = ['schema_version', 'pundit', 'drop', 'home', 'away', 'score', 'date', 'shows', 'quote', 'sample', 'captions', 'audio'];
const REQUIRED = FIELDS.filter(f => f !== 'sample');
const CAPTION_LINES = 2;
const fail = message => { throw new Error(message); };
const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const clock = seconds => { const s = Math.round(seconds); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };

function checkInstance(it){
  if (!it || typeof it !== 'object' || Array.isArray(it)) fail('instance must be a JSON object');
  const missing = REQUIRED.filter(f => !(f in it)), extra = Object.keys(it).filter(f => !FIELDS.includes(f));
  if (missing.length || extra.length) fail(`instance fields: missing ${missing.join(', ') || 'none'}; unknown ${extra.join(', ') || 'none'}`);
  if (it.schema_version !== 1) fail('instance schema_version must be 1');
  if (!PUNDITS.includes(it.pundit)) fail('pundit must be one of ' + PUNDITS.join(', '));
  if (!Array.isArray(it.shows) || !it.shows.includes(it.pundit) || it.shows.some(p => !PUNDITS.includes(p))) fail('shows must list the published AI Pundits, this one included');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(it.date)) fail('date must be YYYY-MM-DD');
  if (!Array.isArray(it.score) || it.score.length !== 2 || !it.score.every(Number.isInteger)) fail('score must be [home, away]');
  for (const k of ['drop', 'home', 'away', 'quote']) if (typeof it[k] !== 'string' || !it[k].trim()) fail(k + ' must be text');
  if ('sample' in it && typeof it.sample !== 'boolean') fail('sample must be true or false');
  const a = it.audio;
  if (!a || typeof a.source_record !== 'string' || typeof a.start_seconds !== 'number' || typeof a.end_seconds !== 'number' || !(a.end_seconds > a.start_seconds)) fail('audio must be {source_record, start_seconds, end_seconds}');
  const duration = a.end_seconds - a.start_seconds;
  if (!Array.isArray(it.captions) || !it.captions.length) fail('captions must be a non-empty list');
  let last = 0;
  it.captions.forEach((c, i) => {
    if (!c || typeof c.text !== 'string' || !c.text.trim() || typeof c.start !== 'number' || typeof c.end !== 'number') fail(`caption ${i + 1} must be {start, end, text}`);
    if (c.start < last - 1e-9 || !(c.end > c.start) || c.end > duration + 1e-6) fail(`caption ${i + 1} is out of order or outside the clip`);
    last = c.end;
  });
  return duration;
}

/* The one pixel at (x, y) of a page, as #rrggbb, read from a 1x1 PNG screenshot (any PNG filter leaves a lone pixel as is). */
async function pixel(page, x, y){
  const png = await page.screenshot({ clip: { x, y, width: 1, height: 1 } });
  let at = 8, idat = [], type = 0;
  while (at < png.length) {
    const len = png.readUInt32BE(at), name = png.toString('ascii', at + 4, at + 8), data = png.subarray(at + 8, at + 8 + len);
    if (name === 'IHDR') { if (data[8] !== 8) fail('unexpected PNG bit depth'); type = data[9]; }
    if (name === 'IDAT') idat.push(data);
    at += 12 + len;
  }
  if (type !== 2 && type !== 6) fail('unexpected PNG colour type');
  const raw = zlib.inflateSync(Buffer.concat(idat));
  return '#' + [1, 2, 3].map(i => raw[i].toString(16).padStart(2, '0')).join('');
}

async function main(){
  const args = process.argv.slice(2);
  const file = args.find(a => !a.startsWith('--') && args[args.indexOf(a) - 1] !== '--out');
  if (!file) fail('usage: node brand/social-kit/take_clip.js <instance.json> [--out <folder>]');
  const outArg = args.includes('--out') ? args[args.indexOf('--out') + 1] : null;
  const L = kit.lock();
  kit.needAssets();
  const bytes = fs.readFileSync(file);
  const it = JSON.parse(bytes.toString('utf8'));
  const duration = checkInstance(it);
  const name = path.basename(file).replace(/\.json$/i, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const folder = path.resolve(outArg || path.join(kit.OUT, 'layers', name));
  const base = JSON.parse(fs.readFileSync(path.join(kit.KIT, 'slots.json'), 'utf8'));
  const slug = `${it.date}_${it.home}-${it.away}`.toLowerCase().replace(/ /g, '-');
  for (const asset of [`cover_${it.pundit}_${slug}.svg`, `seal_${slug}.svg`]) {
    if (!fs.existsSync(path.join(kit.ASSETS, asset))) fail(`no ${asset}: run prepare-assets.mjs with --instance ${file}`);
  }
  const time = clock(duration);
  const sample = it.sample === true;
  const slots = { cta: base.cta, grid: [],
    matches: { m: { slug, home: esc(it.home), away: esc(it.away), score: it.score, date: it.date, shows: it.shows } },
    posts: { frame0: { format: 'take_first', pundit: it.pundit, match: 'm', quote: esc(it.quote.trim()), sample } } };
  const ids = it.captions.map((c, i) => `plate-${String(i + 1).padStart(3, '0')}`);
  it.captions.forEach((c, i) => {
    slots.posts[ids[i]] = { format: 'take_mid', pundit: it.pundit, match: 'm', said: esc(c.text.trim()), now: '', next: '', progress: 0, time, sample };
  });
  const url = kit.writePage('take-clip.html', slots);
  fs.mkdirSync(folder, { recursive: true });
  const stale = path.join(folder, 'layers.json');
  if (fs.existsSync(stale)) fs.unlinkSync(stale);

  const { chromium } = require('playwright');
  const br = await chromium.launch(kit.LAUNCH);
  const problems = [], layers = [];
  let progress = null;
  try {
    for (const id of ['frame0', ...ids]) {
      const p = await br.newPage({ viewport: { width: 1080, height: 1920 } });
      await p.goto(url + '?only=' + id, { waitUntil: 'networkidle' });
      await p.evaluate(() => window.__ready);
      await p.waitForTimeout(200);
      const issues = await p.evaluate(kit.checkArt, { id, ov: '', BANNED: kit.BANNED });
      const info = await p.evaluate(lines => {
        const root = document.querySelector('#root > .ab');
        const text = [...root.querySelectorAll('.t')].map(e => e.textContent.replace(/\s+/g, ' ').trim()).filter(Boolean);
        const out = { text, issues: [] };
        const capt = root.querySelector('.capt');
        if (capt) {
          const lh = parseFloat(getComputedStyle(capt).lineHeight);
          if (capt.getBoundingClientRect().height > lh * lines + 1) out.issues.push(`caption runs over ${lines} lines`);
          const fill = root.querySelector('div[style*="var(--lime)"]'), r = fill.parentElement.getBoundingClientRect();
          out.track = { x: r.left, y: r.top, w: r.width, h: r.height };
          const pause = root.querySelector('svg rect').getBoundingClientRect();
          out.pause = { x: Math.floor(pause.left + pause.width / 2), y: Math.floor(pause.top + pause.height / 2) };
        }
        return out;
      }, CAPTION_LINES);
      issues.push(...info.issues);
      if (info.track) {
        const t = info.track, rect = { x: Math.round(t.x), y: Math.round(t.y), w: Math.round(t.w), h: Math.round(t.h) };
        /* The left, top and height are whole pixels; the width ends where the time label starts, so it is rounded. */
        if ([t.x, t.y, t.h].some((v, i) => Math.abs(v - [rect.x, rect.y, rect.h][i]) > 0.01)) issues.push(`progress track is not on whole pixels: ${JSON.stringify(t)}`);
        const color = await pixel(p, info.pause.x, info.pause.y);
        const here = Object.assign(rect, { color });
        if (progress && JSON.stringify(progress) !== JSON.stringify(here)) issues.push('progress track differs between plates');
        progress = progress || here;
      }
      if (issues.length) problems.push(`${id}:\n  ${issues.join('\n  ')}`);
      const png = path.join(folder, id + '.png');
      await p.screenshot({ path: png, clip: { x: 0, y: 0, width: 1080, height: 1920 } });
      const b = fs.readFileSync(png);
      layers.push({ file: id + '.png', bytes: b.length, sha256: kit.sha256(b), text: info.text });
      await p.close();
    }
  } finally {
    await br.close();
  }
  if (problems.length) fail('layers refused:\n' + problems.join('\n'));
  const [frame0, ...plates] = layers;
  const manifest = { schema_version: 1, kit: L.kit, revision: L.revision, lock_sha256: L.lock_sha256,
    instance: path.resolve(file), instance_sha256: kit.sha256(bytes), size: '1080x1920', width: 1080, height: 1920,
    time_label: time, frame0,
    plates: plates.map((x, i) => Object.assign(x, { start: it.captions[i].start, end: it.captions[i].end, caption: it.captions[i].text })),
    progress, rendered_at: new Date().toISOString() };
  fs.writeFileSync(path.join(folder, 'layers.json'), JSON.stringify(manifest, null, 1) + '\n');
  console.log(`take_clip layers: frame 0 and ${plates.length} plate(s) in ${folder}`);
}

if (require.main === module) main().catch(e => { console.error(e.message || e); process.exitCode = 1; });
module.exports = { checkInstance, clock };
