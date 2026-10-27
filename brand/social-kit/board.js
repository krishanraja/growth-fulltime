/* Board layout: every artboard at true aspect, format-name labels, SPEC panel. */
(function(){
const {P, ORDER, ART, nameW100, fitName} = window.FT;
const S = window.SLOTS;
const fr = (id, scale, label, tags=[]) => {
  const a = ART[id];
  return `<figure class="fr" style="width:${Math.max(a.w*scale, 300)}px"><div class="box" style="width:${a.w*scale}px;height:${a.h*scale}px"><div style="transform:scale(${scale});transform-origin:0 0;width:${a.w}px">${a.html()}</div></div>
    <figcaption><b>${label}</b><span>${a.w} × ${a.h}</span>${tags.map(t=>`<em>${t}</em>`).join('')}</figcaption></figure>`;
};
const SL = 'sample line', TF = 'template fill, not a published show', BOTH = 'only when both AI Pundits made a show for this match';
const chRows = ORDER.map(id => { const p = P[id]; const r = ORDER[6 - p.n];
  return `<tr><td><i class="sw" style="background:${p.paper}"></i></td><td>CH ${p.n}</td><td class="sf"><em>The</em> ${p.name.replace('-', '<span class="hy">-</span>')}</td><td>${id}</td><td>${p.paper}</td><td>CH ${P[r].n}</td><td>${fitName(id, 876, 240)}px</td><td>Send to your mate who <em class="sf">${p.mate}</em></td></tr>`; }).join('');

const html = `<div class="board">
<header class="hd"><div class="k">Full Time · social design system</div><h1><em>The</em> Switch, revision 1</h1></header>

<section><h2>take_clip · 9:16 · frame 0, mid frame, safe zones, slot map</h2>
<div class="row">${fr('take_first_zen',.33,'take_clip · frame 0 · CH 1',[SL])}${fr('take_mid',.33,'take_clip · mid frame · CH 1',[SL])}${fr('take_first_safe',.33,'take_clip · frame 0 · safe zones')}${fr('take_slots',.33,'take_clip · frame 0 · slot map')}</div>
<div class="row">${fr('take_first_romantic',.33,'take_clip · frame 0 · CH 4',[SL])}${fr('take_first_gaffer',.33,'take_clip · frame 0 · CH 2',[SL])}${fr('take_first_stats',.33,'take_clip · frame 0 · CH 3 · long name, 79-character quote',[SL, TF])}${fr('take_mid_romantic',.33,'take_clip · mid frame · CH 4',[SL])}</div>
<div class="row">${fr('take_first_doomer',.33,'take_clip · frame 0 · CH 5',[SL, TF])}${fr('take_first_banter',.33,'take_clip · frame 0 · CH 6',[SL, TF])}</div>
</section>

<section><h2>Variants · ${BOTH}</h2>
<div class="row">${fr('take_first_variant_cut',.33,'take_clip · frame 0 · variant: the cut · CH 6 → CH 1',[BOTH, 'sample lines'])}${fr('row',.418,'row · Pundit v Pundit · CH 3 v CH 4',[BOTH + ', with two real conflicting lines', 'sample lines'])}</div>
</section>

<section><h2>Cards</h2>
<div class="row">${fr('morning',.418,'morning_card · top of the bill')}${fr('morning_long',.418,'morning_card · long club names')}${fr('end_card',.33,'match_ad · end card')}</div>
<div class="row">${fr('share',.62,'share card')}${fr('thumb',.58,'thumbnail')}</div>
<div class="row">${fr('thumb_long',.58,'thumbnail · long club names')}</div>
</section>

<section class="two"><div><h2>Profile grid · 3 × 3 · 3:4 crops · newest top left</h2>${fr('grid',.66,'grid · nine posts',['all quotes are sample lines'])}<div style="height:40px"></div>${fr('check_180',.592,'check_180 · take_clip frame 0 at 180px wide · CH 1 to 6 (true size in frames/check_180.png)',[SL])}</div>
<div class="spec">
<h2>Spec</h2>
<h3>Channels</h3>
<table class="tbl ch"><tr><th></th><th>CH</th><th>AI Pundit</th><th>id</th><th>paper</th><th>rival (7 − n)</th><th>name px</th><th>mate line (fixed)</th></tr>${chRows}</table>

<h3>Type scale at 1080 wide</h3>
<table class="tbl">
<tr><td>Pundit name</td><td>Instrument Serif 400. px = min(cap, column ÷ name width at 1px). Frame 0: column 876, cap 240. "The" italic at 0.42 × px, never wraps.</td></tr>
<tr><td>Hook quote</td><td>Instrument Serif. Up to 60 characters: 104px, lh 1.02, 3 lines max. 61 to 90: 88px, lh .99, 4 lines max. Over 90: rejected. Curly quotes added by code.</td></tr>
<tr><td>Rival quote</td><td>Variant only. Serif italic 58px, 6 words max.</td></tr>
<tr><td>Mate line</td><td>Label Grotesk 600 caps 20px, line Serif italic 48px (54 on morning_card).</td></tr>
<tr><td>Match line</td><td>Grotesk 600 36px, 2 lines max. Date label Grotesk 600 caps 20px.</td></tr>
<tr><td>Score</td><td>Instrument Serif at 0.30 × seal diameter, inside the seal with FULL TIME and dd·mm·yy. Seal 316px on frame 0, 388 on morning_card.</td></tr>
<tr><td>CTA</td><td>Grotesk 700 36 "Pick your channel." over 500 28 "Free pilot beta at fulltime.fm", beside the 68px mark.</td></tr>
<tr><td>Labels</td><td>Grotesk 600 caps, +0.14em, 20 to 26px. "CH n · AI Pundit" beside every name.</td></tr>
<tr><td>sample line</td><td>Grotesk 600 caps 20px in ink-3, under the line it marks. Dropped once a real transcript line fills the slot.</td></tr>
</table>

<h3>Frame 0 layout (1080 × 1920)</h3>
<p>Strip x 64, y 250, 876 × 64 on a ground plate. Name + quote + sample tag form one group (name to quote 52px, quote to tag 14px), centred between y 338 and 1066. Seal 316px at x 64, y 1090; beside it at x 410: date label, "Home v Away" (breaks before "v" when over 530px), mate line from y 1250. CTA at y 1426. Cover art band y 1520 to 1920, no text. Variant cut: rival slab y 0 to 620 (rival art 0 to 220, "CH r → CH n", rival name, rival_quote), seam at 620, seal 316 on the seam at x 624, our name column 540 wide.</p>
<h3>Caption style (mid frame)</h3>
<p>Grotesk 700 64/1.12 on a solid ground plate (x 64 to 940, y 1068 to 1480) over the cover art. Two lines, about 22 characters each, cut at phrase breaks. Said words cream, the current word cream with a 6px underline, words to come at 40%. Under the caption: lime pause glyph, lime progress fill on a 22% cream track, time; then "Made by AI from checked match facts"; then the CTA.</p>

<h3>Slot map</h3>
<table class="tbl">
<tr><td>pundit</td><td>paper ground, name, CH n, lit tab, mate line, cover art band.</td></tr>
<tr><td>match</td><td>home, away, score, date and shows[] (which AI Pundits published a show). Seal and cover art come from product code.</td></tr>
<tr><td>quote</td><td>Frame 0 hook. Real transcript line; until then a pundit's public line or a clear opinion line, marked sample line.</td></tr>
<tr><td>rival_quote</td><td>Variant cut only: the rival's real line, 6 words max.</td></tr>
<tr><td>said / now / next</td><td>Mid-frame caption chunk from the audio timing.</td></tr>
<tr><td>cta</td><td>Fixed: "${S.cta}".</td></tr>
</table>

<h3>Data truth</h3>
<ul>
<li>Strip tab state: <b>lit</b> = this post's AI Pundit; <b>on</b> = shows[] has a show for this match; <b>off</b> (38% opacity on the ground plate) = no show for this match. No match bound (end card, share): all on.</li>
<li>Default take_clip frame 0 is single channel. The cut renders only if shows[] holds the rival (7 − n) AND rival_quote is supplied; otherwise code falls back to the default.</li>
<li>row renders only if shows[] holds both AI Pundits and both lines are real and opposed. Copy: "Who is right? Comment a or b. Send it to the mate who is wrong."</li>
<li>morning_card headliner must be in shows[]; the other channels show as dimmed tabs, never as shows.</li>
<li>No line ever claims another AI Pundit disagrees unless that pundit's real line is on the frame.</li>
<li>Sample lines carry no match facts or numbers.</li>
</ul>

<h3>First second of take_clip (sound off)</h3>
<ol>
<li><b>0.00s</b> Frame 0 is complete: paper, strip, name, quote, seal, mate line, CTA. It reads with no motion.</li>
<li><b>0.08 to 0.24s</b> The lit tab blinks off and on once, like a channel number on a TV.</li>
<li><b>0.24 to 0.42s</b> The seal stamps: scale 1.06 to 1.00 with a 4px drop.</li>
<li><b>0.00 to 2.00s</b> Audio: "This is The Reporter, an AI Pundit on Full Time."</li>
<li><b>1.00 to 1.30s</b> Cut to the mid layout: the name drops to the header, the art band rises into the screen, captions start.</li>
<li><b>Variant cut</b> 0.00 to 0.12s the seam bar slips 24px sideways once; 0.12 to 0.40s the rival slab wipes up and out. Then as above.</li>
</ol>

<h3>Safe zones (9:16)</h3>
<p>Text and key art inside x 64 to 940, y 220 to 1500. The top 220 holds flat paper (or the rival's art on the cut); the bottom 420 holds the cover art band, which carries no text. render.js fails the build if any text box leaves the safe area. Lime: mark, play/pause and progress fill only.</p>

<h3>Grid</h3>
<p>3:4 crop of each post: 9:16 posts use the window y 190 to 1630 (set as the profile crop), 4:5 posts the centre 1012 × 1350. The strip sits at the same height in every tile. Never the same lead paper twice in a row (morning_card, row, end card lead on ground). render.js checks the rule.</p>
</div></section>
</div>`;
document.getElementById('root').innerHTML = html;
})();
