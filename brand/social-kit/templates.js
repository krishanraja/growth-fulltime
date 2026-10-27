/* The Switch, revision 1. Browser-side templates. Every artboard is a pure function of slots (window.SLOTS).
   Coordinates are true pixels. Text that must be read carries class "t" so render.js can check safe zones. */
(function(){
const S = window.SLOTS;
const P = {
  zen:      {n:1, name:'Reporter',    paper:'#3F607C', line:'Calm, clear, and first with the facts.',        mate:'wants the facts before the arguments.'},
  gaffer:   {n:2, name:'Gaffer',      paper:'#4E6B3C', line:'Spots the choices that changed the game.',     mate:'picks the team from the sofa.'},
  stats:    {n:3, name:'Numbers Guy', paper:'#2E6463', line:'Counts everything. Trusts almost nothing.',    mate:'wins every argument with a spreadsheet.'},
  romantic: {n:4, name:'Romantic',    paper:'#9B6269', line:'Finds the bit that made football feel magic.', mate:'still gets goosebumps at kick-off.'},
  doomer:   {n:5, name:'Doomer',      paper:'#4F4868', line:'Sees the wobble before anyone else.',          mate:'is worried even when you win.'},
  banter:   {n:6, name:'Wind-Up',     paper:'#A3542E', line:'Starts arguments for fun. Football needs one.', mate:'bites every single time.'},
};
const ORDER = ['zen','gaffer','stats','romantic','doomer','banter'];
const byN = n => ORDER[n-1];
const rival = id => byN(7 - P[id].n);
const GROUND = '#1c1611';
const A = 'assets/';
const MARK = A + 'podcast-cover.png';
const CTA = S.cta;
const cover = (id, m) => `${A}cover_${id}_${m.slug}.svg`;
const sealSrc = m => `${A}seal_${m.slug}.svg`;
const day = d => new Date(d+'T12:00:00Z').toLocaleDateString('en-GB',{weekday:'short',day:'numeric',month:'short',timeZone:'UTC'}).replace(',','');
const dshort = d => { const [y,mo,da] = d.split('-'); return `${da}·${mo}·${y.slice(2)}`; };
const nm = id => P[id].name.replace('-', '<span class="hy">-</span>');      /* Wind-Up: tightened hyphen */
const theName = id => `<span class="it">The</span> ${nm(id)}`;
const score = m => `${m.score[0]}–${m.score[1]}`;
const qsize = q => { if (q.length > 90) throw new Error('quote over 90 chars: ' + q); return q.length <= 60 ? 104 : 88; };
const words = q => q.trim().split(/\s+/).length;
const curly = q => `“${q.replace(/(^|\s)(I|a|A) /g, '$1$2\u00a0')}”`;   /* one-letter words never end a line */
const quoteCss = qs => `font-family:'Instrument Serif';font-size:${qs}px;line-height:${qs>100?1.02:.99};text-wrap:balance;letter-spacing:-.005em;text-indent:-.36em`;
function match(d){ const m = Object.assign({}, S.matches[d.match]); if (d.shows) m.shows = d.shows; return m; }

/* ---------- measuring (fonts are loaded before any template runs) ---------- */
const meas = document.createElement('div');
meas.style.cssText = 'position:absolute;left:-99999px;top:0;white-space:nowrap;visibility:hidden';
document.body.appendChild(meas);
const W = {};
function width(html, css){ const k = css + '|' + html; if (W[k] == null){ meas.innerHTML = `<span style="${css}">${html}</span>`; W[k] = meas.firstChild.getBoundingClientRect().width; } return W[k]; }
/* Name fit (from The Six Papers): px = min(cap, maxW / width of the name at 1px) */
const nameW100 = id => width(nm(id), "font:400 100px 'Instrument Serif'");
const fitName = (id, maxW, cap) => Math.floor(Math.min(cap, maxW * 100 / nameW100(id)));
function heightOf(html, w, css){ meas.innerHTML = `<div style="width:${w}px;white-space:normal;${css}">${html}</div>`; return meas.firstChild.getBoundingClientRect().height; }
const fitText = (html, maxW, cap, css) => Math.floor(Math.min(cap, maxW * 100 / width(html, `${css};font-size:100px`)));

/* ---------- components ---------- */
/* The strip. state per tab: lit = this post's AI Pundit; on = a show exists for this match; off = no show for this match (dimmed). No match bound: all on. */
function strip({x=64, y=250, w=876, h=64, lit, m=null, fs=28, all=false}){
  const pad = Math.max(2, Math.round(h/9));
  let s = `<div class="strip" style="left:${x}px;top:${y}px;width:${w}px;height:${h}px;gap:${pad}px;padding:${pad}px;font-size:${fs}px">`;
  for (let n = 1; n <= 6; n++){
    const id = byN(n);
    const st = id === lit ? 'lit' : (all || !m || m.shows.includes(id)) ? 'on' : 'off';
    s += `<div class="tab ${st}" style="background:${P[id].paper};${st==='lit'?`box-shadow:inset 0 0 0 ${Math.max(2,Math.round(h/14))}px var(--ink)`:''}">${st==='lit'?`<b style="font-size:${fs*.72}px">CH</b>`:''}${n}</div>`;
  }
  return s + '</div>';
}
/* Name block: "The" italic over the name, "CH n · AI Pundit" beside "The". Positioned by the name's line-box bottom so every pundit sits on one baseline. */
function nameBlock(id, {x, bottom, maxW, cap, lab=24}){
  const px = fitName(id, maxW, cap), the = px * .42;
  const top = Math.round(bottom - (the + px * .82));
  return `<div class="abs" style="left:${x}px;top:${top}px">
    <div style="display:flex;align-items:baseline;gap:${Math.round(px*.13)}px;height:${the}px"><span class="serif it t" style="font-size:${the}px;line-height:1">The</span><span class="cap t" style="font-size:${lab}px">CH ${P[id].n} · AI Pundit</span></div>
    <div class="serif t" style="font-size:${px}px;line-height:.86;margin-top:${-px*.04}px;white-space:nowrap">${nm(id)}</div></div>`;
}
/* Match seal (graft from The Stamped Verdict): FULL TIME, score in Instrument Serif at .30 d, date */
function seal(m, x, y, d){
  return `<div class="seal" style="left:${x}px;top:${y}px;width:${d}px;height:${d}px"><img src="${sealSrc(m)}" alt="">
    <div class="c"><span class="ft t" style="font-size:${Math.max(9,d*.042)}px">Full time</span>
    <span class="sc t" style="font-size:${d*.30}px;margin:${d*.025}px 0 ${d*.03}px">${m.score[0]}<span class="dash">–</span>${m.score[1]}</span>
    <span class="dt t" style="font-size:${Math.max(9,d*.038)}px">${dshort(m.date)}</span></div></div>`;
}
const mark = (x, y, w) => `<img class="abs" src="${MARK}" style="left:${x}px;top:${y}px;width:${w}px;height:${w}px" alt="Full Time">`;
/* CTA: two lines beside the mark. "free pilot beta" is on every format. */
function cta(x, y, {mk=68, a=36, b=28, w=800} = {}){
  const [l1, l2] = CTA.split('. ');
  return mark(x, y, mk) + `<div class="abs" style="left:${x+mk+22}px;top:${y + (mk - (a*1.1 + b*1.2))/2}px;width:${w}px">
    <div class="t" style="font:700 ${a}px/1.1 var(--sans);white-space:nowrap">${l1}.</div><div class="t" style="font:500 ${b}px/1.2 var(--sans);white-space:nowrap">${l2}</div></div>`;
}
const ctaLine = (x, y, size, mk) => mark(x, y, mk) + `<div class="abs t" style="left:${x+mk+16}px;top:${y + (mk-size*1.2)/2}px;font:600 ${size}px/1.2 var(--sans);white-space:nowrap">${CTA}</div>`;
const sampleTag = (x, y, txt='Sample line', size=20) => `<div class="abs t cap" style="left:${x}px;top:${y}px;font-size:${size}px;color:var(--ink3)">${txt}</div>`;
function mateBlock(id, x, y, w, size=50, lab=20){
  return `<div class="abs" style="left:${x}px;top:${y}px;width:${w}px"><div class="cap t" style="font-size:${lab}px;opacity:.85">Send to your mate who</div>
    <div class="serif it t" style="font-size:${size}px;line-height:1.06;margin-top:6px;text-wrap:balance">${P[id].mate}</div></div>`;
}
const artBand = (id, m, y, h, pos='50% 38%') => `<div class="abs" style="left:0;top:${y}px;width:1080px;height:${h}px;overflow:hidden;background:${P[id].paper}"><img src="${cover(id,m)}" style="position:absolute;left:0;top:0;width:100%;height:100%;object-fit:cover;object-position:${pos}" alt=""></div>`;
function seam(y, upper){ /* the one seam: a single misregistered bar of the upper paper + 3px cream line */
  return `<div class="abs" style="left:0;top:${y}px;width:330px;height:22px;background:${P[upper].paper}"></div>
  <div class="abs" style="left:0;top:${y-2}px;width:1080px;height:3px;background:rgba(241,233,218,.8)"></div>`;
}
const ab = (w, h, bg, inner, id='') => `<div class="ab" data-w="${w}" data-h="${h}" data-id="${id}" style="width:${w}px;height:${h}px;background:${bg}">${inner}</div>`;

/* ---------- overlays ---------- */
function safeOverlay(){
  const z = (x,y,w,h) => `<div class="abs zone" style="left:${x}px;top:${y}px;width:${w}px;height:${h}px"></div>`;
  return `<div class="ov">${z(0,0,1080,220)}${z(0,1500,1080,420)}${z(940,220,140,1280)}
  <div class="abs" style="left:0;top:220px;width:940px;height:1280px;outline:4px dashed rgba(241,233,218,.95);outline-offset:-2px"></div>
  <div class="abs zl" style="left:40px;top:120px">Unsafe: top 220</div><div class="abs zl" style="left:40px;top:1700px">Unsafe: bottom 420 (platform UI)</div>
  <div class="abs zl" style="left:1060px;top:560px;transform:rotate(90deg);transform-origin:0 0;white-space:nowrap">Unsafe: right 140</div></div>`;
}
function slotOverlay(L){
  const b = (x,y,w,h,l) => `<div class="abs" style="left:${x}px;top:${y}px;width:${w}px;height:${h}px;outline:4px dashed var(--ink);background:rgba(21,17,13,.3)"></div><div class="abs sl" style="right:${1080-x-w+8}px;top:${y+h-38}px">${l}</div>`;
  return `<div class="ov"><div class="abs" style="inset:0;background:rgba(21,17,13,.25)"></div>
  ${b(64,250,876,64,'strip: pundit (lit) + match.shows')}${b(60,L.groupTop,880,L.nameH,'pundit: name (fit), CH n · AI Pundit')}
  ${b(64,L.quoteTop,876,L.quoteH,'quote (≤60: 104px · 61 to 90: 88px)')}${b(64,L.tagTop,220,26,'sample tag')}
  ${b(64,1090,316,316,'seal + score + date')}${b(410,1090,530,128,'date · home v away')}${b(410,1228,530,178,'pundit.mate (fixed)')}
  ${b(64,1424,876,72,'cta (fixed)')}${b(0,1520,1080,400,'cover art band (product code)')}</div>`;
}

/* ===================== FORMATS ===================== */
/* "Home v Away" on one line if it fits, else break before "v" */
const matchLine = (m, w, size) => width(`${m.home} v ${m.away}`, `font:600 ${size}px 'Schibsted Grotesk'`) <= w ? `${m.home} v ${m.away}` : `${m.home}<br>v ${m.away}`;
/* name + quote (+ sample tag) as one group, centred in [top, bottom]. Gap name to quote 52px, quote to tag 14px. */
function groupLayout(id, d, {top, bottom, maxW, cap, minQuoteTop=0}){
  const px = fitName(id, maxW, cap), hn = px * .42 + px * .82, qs = qsize(d.quote);
  const hq = heightOf(curly(d.quote), 876, quoteCss(qs));
  const ht = d.sample ? 14 + 24 : 0;
  const g = hn + 52 + hq + ht;
  let t = Math.max(top, Math.round(top + (bottom - top - g) / 2));
  if (t + hn + 52 < minQuoteTop) t = minQuoteTop - hn - 52;
  return {nameBottom: Math.round(t + hn), quoteTop: Math.round(t + hn + 52), tagTop: Math.round(t + hn + 52 + hq + 14), groupTop: t, quoteH: Math.round(hq), nameH: Math.round(hn)};
}
/* take_clip frame 0. DEFAULT = single channel. The cut is a variant used only when the rival made a show for this match and rival_quote is supplied. */
function takeFirst(d){
  const m = match(d), id = d.pundit, r = rival(id);
  if (d.rival_quote && m.shows.includes(r)) return takeCut(d, m);
  const qs = qsize(d.quote);
  const L = groupLayout(id, d, {top:338, bottom:1066, maxW:876, cap:240});
  let h = '';
  h += strip({lit:id, m});
  h += nameBlock(id, {x:60, bottom:L.nameBottom, maxW:876, cap:240});
  h += `<div class="abs t" style="left:64px;top:${L.quoteTop}px;width:876px;${quoteCss(qs)}">${curly(d.quote)}</div>`;
  if (d.sample) h += sampleTag(64, L.tagTop);
  h += seal(m, 64, 1090, 316);
  h += `<div class="abs" style="left:410px;top:1096px;width:530px"><div class="cap t" style="font-size:20px;opacity:.85">${day(m.date)} · Premier League</div>
    <div class="t" style="font:600 36px/1.14 var(--sans);margin-top:10px">${matchLine(m, 530, 36)}</div></div>`;
  h += mateBlock(id, 410, 1250, 530, 48);
  h += cta(64, 1426);
  h += artBand(id, m, 1520, 400);
  if (d.overlay === 'safe') h += safeOverlay();
  if (d.overlay === 'slots') h += slotOverlay(L);
  return ab(1080, 1920, P[id].paper, h, 'take_first');
}
/* VARIANT: the cut. Only when both AI Pundits made a show for this match. rival_quote ≤ 6 words, the rival's real line. */
function takeCut(d, m){
  const id = d.pundit, r = rival(id), qs = qsize(d.quote);
  if (words(d.rival_quote) > 6) throw new Error('rival_quote over 6 words');
  let h = '';
  h += `<div class="abs" style="left:0;top:0;width:1080px;height:620px;background:${P[r].paper}"></div>`;
  h += artBand(r, m, 0, 220, '50% 20%');
  h += strip({lit:id, m});
  h += `<div class="abs cap t" style="left:64px;top:346px;font-size:26px">CH ${P[r].n} → CH ${P[id].n}</div>`;
  h += `<div class="abs" style="left:64px;top:384px;display:flex;align-items:baseline;gap:18px;white-space:nowrap"><span class="serif t" style="font-size:56px;line-height:1">${theName(r)}</span><span class="cap t" style="font-size:20px;opacity:.85">AI Pundit</span></div>`;
  h += `<div class="abs serif it t" style="left:64px;top:458px;width:530px;font-size:58px;line-height:1.04">${curly(d.rival_quote.replace(/([.?!]) (?=\S)/, '$1<br>'))}</div>`;
  h += seam(620, r);
  h += seal(m, 624, 470, 316);
  const L = groupLayout(id, Object.assign({}, d, {sample:true}), {top:656, bottom:1300, maxW:540, cap:200, minQuoteTop:806});
  h += nameBlock(id, {x:60, bottom:L.nameBottom, maxW:540, cap:200});
  h += `<div class="abs t" style="left:64px;top:${L.quoteTop}px;width:876px;${quoteCss(qs)}">${curly(d.quote)}</div>`;
  if (d.sample) h += sampleTag(64, L.tagTop, 'Sample lines');
  h += `<div class="abs" style="left:64px;top:1322px;width:876px"><div class="serif t" style="font-size:44px;line-height:1">Who is right? Comment <span class="sans" style="font-weight:700;font-size:38px">${P[r].n}</span> or <span class="sans" style="font-weight:700;font-size:38px">${P[id].n}</span>.</div>
    <div class="t" style="font:500 26px var(--sans);margin-top:10px;opacity:.9">Send it to the mate who is wrong.</div></div>`;
  h += cta(64, 1426);
  h += artBand(id, m, 1520, 400);
  return ab(1080, 1920, P[id].paper, h, 'take_first_variant_cut');
}
/* take_clip mid frame: the cover art is the picture on screen. One ground plate holds captions, progress, disclosure, CTA. */
function takeMid(d){
  const m = match(d), id = d.pundit;
  let h = '';
  h += strip({lit:id, m});
  h += `<div class="abs" style="left:64px;top:346px;width:640px"><div class="cap t" style="font-size:22px">CH ${P[id].n} · AI Pundit</div>
    <div class="serif t" style="font-size:68px;line-height:1;margin-top:10px;white-space:nowrap">${theName(id)}</div>
    <div class="t" style="font:600 26px/1.2 var(--sans);margin-top:14px;white-space:nowrap;opacity:.92">${m.home} v ${m.away} · ${day(m.date)}</div></div>`;
  h += seal(m, 760, 330, 180);
  h += `<div class="abs" style="left:0;top:540px;width:1080px;height:1380px;overflow:hidden;background:${P[id].paper}"><img src="${cover(id,m)}" style="position:absolute;left:0;top:0;width:100%;height:100%;object-fit:cover;object-position:50% 30%" alt=""></div>`;
  h += `<div class="abs" style="left:0;top:538px;width:1080px;height:3px;background:rgba(241,233,218,.85)"></div>`;
  h += `<div class="abs" style="left:64px;top:1068px;width:876px;height:412px;background:var(--ground)"></div>`;
  h += `<div class="abs t capt" style="left:100px;top:1094px;width:804px"><span>${d.said}</span> <span class="now">${d.now}</span> <span class="next">${d.next}</span></div>`;
  h += `<div class="abs" style="left:100px;top:1262px;width:804px;height:40px;display:flex;align-items:center;gap:22px">
    <svg width="30" height="36" viewBox="0 0 30 36"><rect x="1" y="1" width="9" height="34" fill="var(--lime)"/><rect x="20" y="1" width="9" height="34" fill="var(--lime)"/></svg>
    <div style="flex:1;height:10px;background:rgba(241,233,218,.22);position:relative"><div style="position:absolute;left:0;top:0;bottom:0;width:${d.progress*100}%;background:var(--lime)"></div></div>
    <div class="t" style="font:600 26px var(--sans);letter-spacing:.04em">${d.time}</div></div>`;
  h += `<div class="abs t" style="left:100px;top:1326px;font:500 24px var(--sans);color:var(--ink2);white-space:nowrap">Made by AI from checked match facts</div>`;
  if (d.sample) h += sampleTag(700, 1330, 'Sample line', 18);
  h += `<div class="abs" style="left:100px;top:1370px;width:804px;height:1px;background:var(--hair)"></div>`;
  h += ctaLine(100, 1394, 25, 52);
  return ab(1080, 1920, P[id].paper, h, 'take_mid');
}
/* morning card: top of the bill (the AI Pundit whose show is published) + large seal. Channels with no show are dimmed. */
function morning(d){
  const m = match(d), id = d.pundit;
  if (!m.shows.includes(id)) throw new Error('morning headliner has no show for this match');
  let h = '';
  h += strip({x:64, y:56, w:952, h:56, lit:id, m, fs:24});
  h += `<div class="abs cap t" style="left:64px;top:132px;font-size:20px">${day(m.date)} · The morning after</div>`;
  h += `<div class="abs cap t" style="right:64px;top:132px;font-size:20px;color:var(--ink2)">Dimmed: no show for this match</div>`;
  h += `<div class="abs" style="left:64px;top:184px;width:388px;height:458px;background:${P[id].paper}"><img src="${cover(id,m)}" style="position:absolute;inset:0;width:100%;height:100%" alt=""></div>`;
  h += `<div class="abs cap t" style="left:492px;top:192px;font-size:22px;color:var(--ink2)">Top of the bill</div>`;
  h += nameBlock(id, {x:488, bottom:448, maxW:524, cap:170, lab:20});
  h += `<div class="abs serif it t" style="left:492px;top:476px;width:524px;font-size:46px;line-height:1.06;text-wrap:balance;color:var(--ink)">${P[id].line}</div>`;
  h += seal(m, 64, 672, 388);
  const cs = "font-family:'Instrument Serif'";
  const px = Math.min(fitText(m.home, 524, 96, cs), fitText('<i>v</i> ' + m.away, 524, 96, cs));
  h += `<div class="abs" style="left:492px;top:${866 - px*1.0}px"><div class="cap t" style="font-size:20px;color:var(--ink2);margin-bottom:14px">Premier League · Full time</div>
    <div class="serif t" style="font-size:${px}px;line-height:.98;white-space:nowrap">${m.home}<br><span class="it">v</span> ${m.away}</div></div>`;
  h += mateBlock(id, 64, 1100, 952, 54, 20);
  h += `<div class="abs" style="left:64px;top:1222px;width:952px;height:1px;background:var(--hair)"></div>`;
  h += ctaLine(64, 1252, 30, 56);
  return ab(1080, 1350, GROUND, h, 'morning');
}
/* row: Pundit v Pundit. Only when both made a show for this match and the two lines really conflict. */
function row(d){
  const m = match(d), a = d.a, b = d.b;
  if (!(m.shows.includes(a) && m.shows.includes(b))) throw new Error('row needs two published shows');
  let h = '';
  h += `<div class="abs" style="left:0;top:0;width:1080px;height:620px;background:${P[a].paper}"></div>`;
  h += `<div class="abs" style="left:0;top:620px;width:1080px;height:510px;background:${P[b].paper}"></div>`;
  h += strip({x:64, y:56, w:952, h:56, lit:a, m, fs:24});
  const art = (id, y) => `<div class="abs" style="left:770px;top:${y}px;width:246px;height:290px;overflow:hidden;background:${P[id].paper}"><img src="${cover(id,m)}" style="position:absolute;inset:0;width:100%;height:100%" alt=""></div>`;
  h += art(a, 150);
  h += nameBlock(a, {x:60, bottom:316, maxW:640, cap:140, lab:20});
  h += `<div class="abs serif t" style="left:64px;top:346px;width:640px;font-size:68px;line-height:1.02;text-wrap:balance">${curly(d.qa)}</div>`;
  h += seam(620, a);
  h += seal(m, 744, 470, 290);
  h += art(b, 800);
  h += nameBlock(b, {x:60, bottom:830, maxW:640, cap:140, lab:20});
  h += `<div class="abs serif t" style="left:64px;top:860px;width:640px;font-size:68px;line-height:1.02;text-wrap:balance">${curly(d.qb)}</div>`;
  if (d.sample) h += sampleTag(64, 1088, 'Sample lines', 18);
  h += `<div class="abs" style="left:64px;top:1150px;width:952px"><div class="serif t" style="font-size:52px;line-height:1">Who is right? Comment <span class="sans" style="font-weight:700;font-size:44px">${P[a].n}</span> or <span class="sans" style="font-weight:700;font-size:44px">${P[b].n}</span>.</div>
    <div class="t" style="font:500 28px var(--sans);margin-top:12px;color:var(--ink)">Send it to the mate who is wrong.</div></div>`;
  h += ctaLine(64, 1270, 26, 48);
  return ab(1080, 1350, GROUND, h, 'row');
}
/* six cover-art bands with names (graft from The Six Papers). Lit band = the channel the post lands on. */
function bands({x=0, y, w, bh, lit, nameSize, chSize, artW, artPos='50% 40%', inset=5, m=S.matches.tc}){
  let s = '';
  ORDER.forEach((id, i) => {
    const yy = y + i*bh, isLit = id === lit;
    s += `<div class="abs" style="left:${x}px;top:${yy}px;width:${w}px;height:${bh}px;background:${P[id].paper};overflow:hidden">
      <img src="${cover(id, m)}" style="position:absolute;right:0;top:0;width:${artW}px;height:100%;object-fit:cover;object-position:${artPos}" alt="">
      <div class="cap t" style="position:absolute;left:${x?20:64}px;top:${bh/2 - chSize*.6}px;font-size:${chSize}px;white-space:nowrap">CH ${P[id].n}</div>
      <div class="serif t" style="position:absolute;left:${(x?20:64) + chSize*3.4}px;top:${bh/2 - nameSize*.55}px;font-size:${nameSize}px;line-height:1;white-space:nowrap"><span class="it" style="font-size:.62em">The</span> ${nm(id)}</div>
      ${isLit?`<div style="position:absolute;inset:0;box-shadow:inset 0 0 0 ${inset}px var(--ink)"></div>`:''}</div>`;
  });
  return s;
}
function endCard(d){
  let h = '';
  const m = S.matches[d.match || 'tc'];
  h += strip({lit:d.lit, all:true});
  h += bands({y:340, w:1080, bh:118, lit:d.lit, nameSize:74, chSize:22, artW:380, m});
  h += mark(56, 1082, 92);
  h += `<img class="abs" src="${A}full-time-wordmark-trim.png" style="left:170px;top:1102px;width:320px" alt="FULL_TIME">`;
  h += `<div class="abs serif t" style="left:64px;top:1206px;width:876px;font-size:58px;line-height:1.04">One real match. Six AI Pundits.<br><span class="it">Pick the brain you fancy.</span></div>`;
  h += `<div class="abs" style="left:64px;top:1384px"><div class="t" style="font:700 44px/1.1 var(--sans)">Pick your channel.</div><div class="t" style="font:500 34px/1.2 var(--sans);margin-top:2px">Free pilot beta at fulltime.fm</div></div>`;
  h += artBand(d.lit, m, 1520, 400);
  return ab(1080, 1920, GROUND, h, 'end_card');
}
function share(d){
  let h = '';
  h += bands({y:0, w:680, bh:105, lit:d.lit, nameSize:46, chSize:15, artW:250, inset:4});
  h += mark(726, 48, 64);
  h += `<img class="abs" src="${A}full-time-wordmark-trim.png" style="left:806px;top:62px;width:210px" alt="FULL_TIME">`;
  h += `<div class="abs serif t" style="left:726px;top:162px;width:440px;font-size:50px;line-height:1.04">One real match.<br>Six AI Pundits.<br><span class="it">Pick the brain<br>you fancy.</span></div>`;
  h += `<div class="abs" style="left:726px;top:468px;width:440px"><div class="t" style="font:700 30px/1.15 var(--sans)">Pick your channel.</div><div class="t" style="font:500 24px/1.25 var(--sans);margin-top:4px">Free pilot beta at fulltime.fm</div></div>`;
  return ab(1200, 630, GROUND, h, 'share');
}
/* YouTube thumbnail: names the clubs and the score, carries the CTA. Bottom-right corner kept clear for the timestamp. */
function thumb(d){
  const m = match(d), id = d.pundit;
  let h = '';
  h += strip({x:48, y:40, w:700, h:46, lit:id, m, fs:22});
  h += nameBlock(id, {x:44, bottom:318, maxW:720, cap:180, lab:20});
  const line = `${m.home} ${score(m)} ${m.away}`;
  const px = fitText(line, 720, 62, "font-family:'Schibsted Grotesk';font-weight:800");
  h += `<div class="abs t" style="left:48px;top:${398 - px*.5}px;font:800 ${px}px/1 var(--sans);white-space:nowrap;letter-spacing:-.01em">${line}</div>`;
  h += `<div class="abs cap t" style="left:48px;top:456px;font-size:20px;opacity:.9">${day(m.date)} · Premier League · AI Pundit show</div>`;
  h += `<div class="abs" style="left:48px;top:530px;width:720px;height:2px;background:rgba(241,233,218,.35)"></div>`;
  h += cta(48, 572, {mk:76, a:40, b:30});
  h += `<div class="abs" style="left:826px;top:34px;width:406px;height:479px;overflow:hidden;background:${P[id].paper};box-shadow:0 0 0 3px rgba(241,233,218,.85)"><img src="${cover(id,m)}" style="position:absolute;inset:0;width:100%;height:100%" alt=""></div>`;
  h += seal(m, 850, 372, 300);
  return ab(1280, 720, P[id].paper, h, 'thumb');
}
const FN = {take_first:takeFirst, take_mid:takeMid, morning, row, end_card:endCard, share, thumb};
const SIZE = {take_first:[1080,1920], take_mid:[1080,1920], morning:[1080,1350], row:[1080,1350], end_card:[1080,1920], share:[1200,630], thumb:[1280,720]};
const leadPaper = d => (d.format === 'morning' || d.format === 'end_card' || d.format === 'row' || d.format === 'share') ? 'ground' : P[d.pundit].paper;

const GRID_TOP = 190;
/* profile grid: 3x3, each tile a centred 3:4 crop. The strip stays fully inside every crop. */
function grid(){
  const tw = 360, th = 480, g = 4;
  const seq = S.grid.map(leadPaper);
  for (let i = 1; i < seq.length; i++) if (seq[i] === seq[i-1]) throw new Error('grid rule broken: same lead paper twice in a row at ' + i);
  let s = '';
  S.grid.forEach((d, i) => {
    const [w, hh] = SIZE[d.format], x = (i%3)*(tw+g), y = Math.floor(i/3)*(th+g);
    let k, ox, oy;
    if (hh/w > 4/3){ k = tw/w; ox = 0; oy = -GRID_TOP * k; }   /* 9:16: profile crop window y 190 to 1630 */ else { k = th/hh; oy = 0; ox = -((w*k - tw)/2); }
    s += `<div class="abs" style="left:${x}px;top:${y}px;width:${tw}px;height:${th}px;overflow:hidden"><div style="position:absolute;left:${ox}px;top:${oy}px;transform:scale(${k});transform-origin:0 0">${FN[d.format](d)}</div></div>`;
  });
  return ab(tw*3+g*2, th*3+g*2, '#000', s, 'grid');
}
/* check: take_clip frame 0 for all six AI Pundits at 180px wide */
const CHECK = ORDER.map(id => S.posts['take_first_' + id]);
function check180(){
  let s = '';
  CHECK.forEach((d, i) => {
    s += `<div class="abs" style="left:${24 + i*204}px;top:24px;width:180px;height:320px;overflow:hidden"><div style="transform:scale(${180/1080});transform-origin:0 0">${takeFirst(Object.assign({}, d, {sample:false}))}</div></div>`;
  });
  return ab(24*2 + 6*180 + 5*24, 368, '#0d0a08', s, 'check_180');
}

/* ===================== registry ===================== */
const ART = {};
for (const [k, d] of Object.entries(S.posts)) { const [w, hh] = SIZE[d.format]; ART[k] = {w, h:hh, html:() => FN[d.format](d), d}; }
ART.grid = {w:1088, h:1448, html:grid, d:{}};
ART.check_180 = {w:24*2+6*180+5*24, h:368, html:check180, d:{}};
window.FT = {P, ORDER, ART, nameW100, fitName, qsize};
})();
