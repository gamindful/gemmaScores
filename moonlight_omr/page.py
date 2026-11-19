"""Render the extracted positions as a keyboard reference page."""

import json

HEAD = """<meta charset="utf-8">
<title>Moonlight Hand Positions</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Spectral:ital,wght@0,400;0,600;1,400&display=swap">
<style>
  /* Layout: a reference sheet — masthead, then the score in system sections. */
  :root {
    --paper: #f3f4f7; --card: #ffffff; --ink: #1a1d23; --muted: #5e646f;
    --rule: #dde0e7; --lh: #2256d6; --lh-soft: #bccef8; --rh: #bc4712;
    --rh-soft: #f2c7a9; --kw: #ffffff; --kb: #23262c; --kedge: #aeb4bf;
    --flag: #8a6d1f; --flag-soft: #f0e3bd;
    --display: "Spectral", Georgia, "Times New Roman", serif;
    --body: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --paper: #101216; --card: #181b21; --ink: #e9ebef; --muted: #99a0ac;
      --rule: #282c34; --lh: #74a6ff; --lh-soft: #2a4677; --rh: #ff9d59;
      --rh-soft: #6d3a1b; --kw: #d5d8de; --kb: #0c0e11; --kedge: #6b707a;
      --flag: #d8b55a; --flag-soft: #4a3d17; color-scheme: dark;
    }
  }
  :root[data-theme="dark"] {
    --paper: #101216; --card: #181b21; --ink: #e9ebef; --muted: #99a0ac;
    --rule: #282c34; --lh: #74a6ff; --lh-soft: #2a4677; --rh: #ff9d59;
    --rh-soft: #6d3a1b; --kw: #d5d8de; --kb: #0c0e11; --kedge: #6b707a;
    --flag: #d8b55a; --flag-soft: #4a3d17; color-scheme: dark;
  }
  body { background: var(--paper); color: var(--ink); font-family: var(--body);
         font-size: 15px; line-height: 1.55; }
  .wrap { max-width: 1180px; margin: 0 auto;
          padding-left: max(16px, env(safe-area-inset-left, 0px));
          padding-right: max(16px, env(safe-area-inset-right, 0px));
          padding-block: 40px 56px; }
  header { border-bottom: 1px solid var(--rule); padding-bottom: 26px; }
  .eyebrow { font-size: 11px; letter-spacing: .14em; text-transform: uppercase;
             color: var(--muted); font-weight: 600; }
  h1 { font-family: var(--display); font-size: clamp(30px, 5vw, 46px);
       font-weight: 600; line-height: 1.08; margin: 10px 0 0;
       text-wrap: balance; letter-spacing: -.01em; }
  h1 em { font-style: italic; font-weight: 400; }
  .standfirst { margin: 14px 0 0; max-width: 64ch; color: var(--muted); font-size: 16px; }
  .legend { display: flex; flex-wrap: wrap; gap: 10px 22px; margin-top: 22px;
            align-items: center; font-size: 13px; color: var(--muted); }
  .swatch { display: inline-flex; align-items: center; gap: 8px; }
  .chip { width: 26px; height: 14px; border-radius: 2px; border: 1px solid var(--kedge); }
  .chip.lh { background: var(--lh-soft); border-color: var(--lh); }
  .chip.rh { background: var(--rh-soft); border-color: var(--rh); }
  .chip.fl { background: var(--flag-soft); border-color: var(--flag); }
  .chip.mel { background: none; border: 0; width: 14px; height: 14px;
              display: inline-block; position: relative; }
  .chip.mel::after { content: ""; position: absolute; inset: 2px 0 auto 0;
    border-left: 7px solid transparent; border-right: 7px solid transparent;
    border-top: 8px solid var(--rh); }
  .scoreline { margin-top: 26px; display: grid; gap: 6px; }
  .scoreline h2 { font-family: var(--display); font-size: 18px; margin: 0; }
  .scoreline p { margin: 0; font-size: 13px; color: var(--muted); max-width: 70ch; }
  section { margin-top: 34px; }
  .sechead { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;
             border-bottom: 1px solid var(--rule); padding-bottom: 7px; }
  .sechead h3 { font-family: var(--display); font-size: 19px; margin: 0; font-weight: 600; }
  .sechead span { font-size: 12px; color: var(--muted); }
  .grid { display: grid; gap: 14px; margin-top: 16px;
          grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }
  .card { background: var(--card); border: 1px solid var(--rule); border-radius: 6px;
          padding: 12px 12px 10px; display: flex; flex-direction: column; gap: 8px;
          min-width: 0; }
  .card.check { border-color: var(--flag); }
  .card.reviewed { border-color: var(--flag); border-style: dashed; }
  .card-head { display: flex; align-items: baseline; justify-content: space-between;
               gap: 10px; flex-wrap: wrap; }
  .where { font-family: var(--display); font-size: 16px; font-weight: 600;
           font-variant-numeric: tabular-nums; }
  .where span { color: var(--muted); font-weight: 400; font-size: 13px; }
  .mark { font-size: 10px; letter-spacing: .08em; text-transform: uppercase;
          color: var(--flag); border: 1px solid currentColor; border-radius: 3px;
          padding: 1px 5px; }
  svg { display: block; width: 100%; height: auto; }
  svg text { font-family: var(--body); }
  .hands { display: grid; gap: 3px; font-size: 13px; }
  .hand { display: flex; gap: 8px; align-items: baseline; min-width: 0; }
  .tag { font-size: 10px; font-weight: 600; letter-spacing: .1em; padding: 1px 5px;
         border-radius: 3px; flex: none; border: 1px solid currentColor; }
  .tag.lh { color: var(--lh); } .tag.rh { color: var(--rh); }
  .notes { font-variant-numeric: tabular-nums; }
  .notes sup { font-size: 9px; font-weight: 700; margin-left: 1px; top: -.5em; }
  .hand.lh .notes sup { color: var(--lh); } .hand.rh .notes sup { color: var(--rh); }
  .notes b { font-weight: 600; }
  .notes b::after { content: " ◂melody"; font-size: 10px; font-weight: 500;
                    color: var(--muted); letter-spacing: .02em; }
  footer { margin-top: 44px; padding-top: 22px; border-top: 1px solid var(--rule);
           color: var(--muted); font-size: 13px; max-width: 74ch; }
  footer h2 { font-family: var(--display); font-size: 17px; color: var(--ink); margin: 0 0 8px; }
  footer p { margin: 0 0 10px; } footer p:last-child { margin-bottom: 0; }
  table.test { border-collapse: collapse; font-size: 12px; margin: 10px 0 0;
               font-variant-numeric: tabular-nums; }
  table.test td { padding: 2px 10px 2px 0; }
</style>
"""

SCRIPT = r"""
<script>
const DATA = __DATA__;
const BASE = {C:0, D:2, E:4, F:5, G:7, A:9, B:11};
function midi(name){
  const m = /^([A-G])([#bnx]?)(-?\d)$/.exec(name);
  if (!m) return null;
  const alt = {"#":1, "b":-1, "n":0, "x":2, "":0}[m[2]];
  return (parseInt(m[3],10)+1)*12 + BASE[m[1]] + alt;
}
const pretty = n => n.replace("#","♯").replace("n","♮").replace("x","×");
const LO = 24, HI = 88, WHITE = [0,2,4,5,7,9,11];
const KW = 15, KH = 58, BW = 9, BH = 36, TOP = 11, LAB = 14;
const whiteX = {}; let wi = 0;
for (let m = LO; m <= HI; m++) if (WHITE.includes(((m%12)+12)%12)) whiteX[m] = wi++;
const TOTAL_W = wi * KW;
function keyboard(lhMap, rhMap, melMidi){
  const parts = [], digits = [];
  const colorOf = m => lhMap.has(m) ? "lh" : (rhMap.has(m) ? "rh" : null);
  const fingerOf = m => lhMap.has(m) ? lhMap.get(m) : rhMap.get(m);
  for (let m = LO; m <= HI; m++){
    if (!(m in whiteX)) continue;
    const x = whiteX[m]*KW, c = colorOf(m);
    parts.push(`<rect x="${x}" y="${TOP}" width="${KW}" height="${KH}" rx="1.5" fill="${c?`var(--${c}-soft)`:"var(--kw)"}" stroke="${c?`var(--${c})`:"var(--kedge)"}" stroke-width="${c?1.3:0.7}"/>`);
    if (c) digits.push(`<text x="${x+KW/2}" y="${TOP+KH-6}" text-anchor="middle" font-size="10" font-weight="700" fill="var(--${c})">${fingerOf(m)}</text>`);
  }
  for (let m = LO; m <= HI; m++){
    if (m in whiteX) continue;
    const x = whiteX[m-1]*KW + KW - BW/2, c = colorOf(m);
    parts.push(`<rect x="${x}" y="${TOP}" width="${BW}" height="${BH}" rx="1.5" fill="${c?`var(--${c})`:"var(--kb)"}" stroke="${c?`var(--${c})`:"var(--kb)"}" stroke-width="0.7"/>`);
    if (c) digits.push(`<text x="${x+BW/2}" y="${TOP+BH-4}" text-anchor="middle" font-size="8" font-weight="700" fill="var(--kb)">${fingerOf(m)}</text>`);
  }
  parts.push(...digits);
  if (melMidi != null){
    const cx = (melMidi in whiteX ? whiteX[melMidi]*KW + KW/2 : whiteX[melMidi-1]*KW + KW);
    parts.push(`<path d="M ${cx-5} 1 L ${cx+5} 1 L ${cx} 9 Z" fill="var(--rh)"/>`);
  }
  for (let m = LO; m <= HI; m++){
    if (((m%12)+12)%12 !== 0) continue;
    parts.push(`<text x="${whiteX[m]*KW+KW/2}" y="${TOP+KH+10}" text-anchor="middle" font-size="8" fill="var(--muted)">C${m/12-1}</text>`);
  }
  return `<svg viewBox="-1 0 ${TOTAL_W+2} ${TOP+KH+LAB}" role="img">${parts.join("")}</svg>`;
}
const label = p => pretty(p[0]) + "<sup>" + p[1] + "</sup>";
let html = "";
let system = null;
for (const pos of DATA.positions){
  if (pos.system !== system){
    if (system !== null) html += "</div></section>";
    system = pos.system;
    const inSys = DATA.positions.filter(p => p.system === system);
    const lo = inSys[0].bar, hi = inSys[inSys.length-1].until;
    html += `<section><div class="sechead"><h3>System ${system}</h3>`
         +  `<span>bars ${lo}–${hi} · ${inSys.length} position${inSys.length>1?"s":""}</span></div><div class="grid">`;
  }
  const lhMap = new Map(), rhMap = new Map();
  for (const [n,f] of pos.lh){ const m = midi(n); if (m!=null) lhMap.set(m,f); }
  for (const [n,f] of pos.rh){ const m = midi(n); if (m!=null) rhMap.set(m,f); }
  let melM = null;
  if (pos.mel){ melM = midi(pos.mel[0]); if (melM!=null && !rhMap.has(melM)) rhMap.set(melM, pos.mel[1]); }
  const span = pos.until > pos.bar ? `bars ${pos.bar}–${pos.until}` : `bar ${pos.bar}`;
  const rhList = pos.rh.map(label).join(" · ")
    + (pos.mel && !pos.rh.some(p => p[0] === pos.mel[0]) ? " · <b>" + label(pos.mel) + "</b>" : "");
  html += `<article class="card ${pos.quality}">
    <div class="card-head"><div class="where">${span} <span>· beat ${pos.beat}</span></div>
    ${pos.quality === "check" ? '<span class="mark">unconfirmed</span>' :
      (pos.quality === "reviewed" ? '<span class="mark">arbitrated</span>' : "")}</div>
    ${keyboard(lhMap, rhMap, melM)}
    <div class="hands">
      <div class="hand lh"><span class="tag lh">LH</span><span class="notes">${pos.lh.map(label).join(" · ") || "—"}</span></div>
      <div class="hand rh"><span class="tag rh">RH</span><span class="notes">${rhList || "—"}</span></div>
    </div></article>`;
}
if (system !== null) html += "</div></section>";
document.getElementById("score").innerHTML = html;
</script>
"""


def render(positions, stats, test_rows, test_summary):
    data = json.dumps({"positions": positions}, separators=(",", ":"))
    firm = sum(1 for p in positions if p["quality"] == "firm")
    rows = "".join(
        "<tr><td>bar %d</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (bar, "hands ok" if a else "hands differ",
           "figure ok" if b else "figure differs", detail)
        for bar, a, b, detail in test_rows)
    body = f"""
<div class="wrap">
  <header>
    <div class="eyebrow">Beethoven · Op. 27 No. 2 · Adagio sostenuto</div>
    <h1>Where the hands sit, <em>through the whole movement</em></h1>
    <p class="standfirst">Every change of hand position in the first movement, read off the
      engraving by a program: {len(positions)} positions across {stats['bars']} bars.
      Each keyboard shows the keys a hand covers and the finger that takes each one.</p>
    <div class="legend">
      <span class="swatch"><span class="chip lh"></span>Left hand</span>
      <span class="swatch"><span class="chip rh"></span>Right hand</span>
      <span class="swatch"><span class="chip mel"></span>Melody note struck here</span>
      <span class="swatch"><span class="chip fl"></span>Unconfirmed, or arbitrated by the local model</span>
      <span class="swatch">Numbers are fingering — 1 is the thumb</span>
    </div>
    <div class="scoreline">
      <h2>How far to trust it</h2>
      <p>The accompaniment figure comes round four times a bar. Where at least two of
      those four readings agree, the position is marked plain; where one stands alone it
      is marked <strong>unconfirmed</strong> and is the first thing to check against the
      score. {firm} of {len(positions)} positions are corroborated this way.</p>
      <p>Against twenty-two positions read by eye off the scan, the program gets
      {test_summary['figure']} of {test_summary['bars']} right-hand figures and
      {test_summary['hands']} of {test_summary['bars']} left-hand chords,
      {test_summary['both']} of {test_summary['bars']} completely. Those bars are a test,
      never an input: nothing hand-entered reaches this page.</p>
    </div>
  </header>

  <div id="score"></div>

  <footer>
    <h2>Reading the diagrams</h2>
    <p>A position is one group of the triplet figure: the three keys the right hand
      covers, any melody note struck with them, and whatever the left hand is holding
      at that moment. Consecutive groups of the same shape are shown once, with the
      bars they span.</p>
    <p>Fingering follows the shape rather than the bar that follows it. The right
      thumb takes the lowest note of the figure; when a melody note sits above, the
      figure is held back to the fourth finger so the fifth is free for it. The left
      hand puts 5 on the bottom and 1 on top.</p>
    <p>Note names follow the engraving's spelling, so a key marked B♯2 is the one
      you would otherwise call C3. Where the right-hand figure is written down in the
      bass clef, its shading sits low on the keyboard.</p>
    <h2>Self-test against the verified bars</h2>
    <table class="test">{rows}</table>
  </footer>
</div>
"""
    return HEAD + body + SCRIPT.replace("__DATA__", data)
