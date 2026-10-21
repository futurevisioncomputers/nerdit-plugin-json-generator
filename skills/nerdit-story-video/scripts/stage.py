"""The video's stage: one HTML page that draws any moment of the video with renderAt(t).

Chromium shapes Devanagari correctly and draws the lessons' own SVG figures with the lesson CSS,
including animated figures (their CSS animations are paused and seeked to each frame's time).
Every visual element is positioned from the timeline, so a frame depends only on t.
"""
import json
from pathlib import Path

W, H = 1280, 720
LESSON_CSS = ("css8.css", "css9-simple.css", "css10-brand.css")  # the site's lesson stylesheet order
CSS_DIR = Path(__file__).resolve().parents[2] / "nerdit-chapter-generator" / "references"

STYLE = """
:root { --navy:#0B1F3A; --teal:#14B8A6; --teal-soft:#D5F5F0; --bg:#EEF3F9; --warm:#F59E0B;
        --red:#B42318; --red-soft:#FDECEA; --green:#0F766E; --green-soft:#E3F6F2; }
* { box-sizing:border-box; margin:0; padding:0; }
html, body { width:1280px; height:720px; overflow:hidden; background:var(--bg);
  font-family:"Segoe UI","Nirmala UI",sans-serif; color:var(--navy); }
.layer { position:absolute; inset:0; opacity:0; }
.top { position:absolute; left:40px; right:40px; top:34px; height:44px; display:flex;
  align-items:center; justify-content:space-between; }
.top .title { font-size:26px; font-weight:700; }
.top .dots { display:flex; gap:8px; }
.top .dot { width:12px; height:12px; border-radius:50%; background:#C9D5E3; }
.top .dot.on { background:var(--teal); }
.top .dot.now { background:var(--navy); transform:scale(1.25); }
.box { position:absolute; left:40px; top:104px; width:720px; height:540px; border-radius:18px;
  overflow:hidden; background:#fff; box-shadow:0 6px 24px rgba(11,31,58,.12); }
.cam { position:absolute; left:0; top:0; width:720px; height:540px; transform-origin:0 0; }
.cam img { width:100%; height:100%; object-fit:cover; display:block; }
.cam iframe { width:100%; height:100%; border:0; background:#fff; }
.ring { position:absolute; width:84px; height:84px; margin:-42px 0 0 -42px; border-radius:50%;
  border:7px solid var(--warm); box-shadow:0 0 0 6px rgba(245,158,11,.25); opacity:0; }
.panel { position:absolute; left:784px; top:104px; width:456px; height:540px; border-radius:18px;
  background:#fff; padding:30px 30px; box-shadow:0 6px 24px rgba(11,31,58,.12); }
.label { font-size:17px; font-weight:800; letter-spacing:.12em; color:var(--teal); text-transform:uppercase; }
.key { font-size:30px; font-weight:700; line-height:1.28; margin-top:10px; }
.terms { display:flex; flex-wrap:wrap; gap:10px; margin-top:22px; }
.chip { font-size:21px; font-weight:600; padding:6px 14px; border-radius:999px; background:var(--teal-soft);
  color:var(--navy); opacity:0; transform-origin:left center; }
.myth { margin-top:24px; display:flex; flex-direction:column; gap:12px; }
.row { font-size:22px; font-weight:600; line-height:1.3; padding:12px 14px 12px 50px; border-radius:12px;
  position:relative; opacity:0; }
.row b { position:absolute; left:14px; top:9px; font-size:26px; }
.row.wrong { background:var(--red-soft); color:var(--red); }
.row.right { background:var(--green-soft); color:var(--green); }
.card { position:absolute; inset:0; display:flex; flex-direction:column; justify-content:center; padding:0 110px; }
.intro { background:var(--navy); color:#fff; }
.intro h1 { font-size:52px; line-height:1.15; }
.intro .label, .recap .label { margin:0 0 18px; font-size:22px; }
.intro h1 + .label { margin-top:34px; }
.pt { font-size:32px; font-weight:600; margin:10px 0; opacity:0; display:flex; gap:16px; align-items:baseline; }
.pt i { font-style:normal; color:var(--teal); font-weight:800; min-width:34px; }
.recap .pt { background:#fff; border-radius:14px; padding:14px 20px; box-shadow:0 4px 14px rgba(11,31,58,.08); }
.broll { position:absolute; inset:0; background:#0B1F3A; }
"""

SCRIPT = r"""
const D = window.DATA, TL = D.timeline, FADE = 0.35, MOVE = 0.9, PAD_IN = 0.5, BUILD = 0.8;
const $ = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html; return e; };
const esc = s => String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const ease = p => p < .5 ? 2*p*p : 1 - Math.pow(-2*p + 2, 2) / 2;
const back = p => { const c = 1.7; return 1 + (c + 1) * Math.pow(p - 1, 3) + c * Math.pow(p - 1, 2); };
const fade = (t, s, e) => clamp(Math.min((t - s) / FADE, (e - t) / FADE), 0, 1);
const seg = (kind, n) => TL.segments.find(s => s.kind === kind && s.scene === n);
const loads = [];
const stage = document.body;

// Intro and recap cards
const introSeg = TL.segments.find(s => s.kind === 'intro'), recapSeg = TL.segments.find(s => s.kind === 'recap');
const intro = $('div', 'layer'); const ic = $('div', 'card intro');
ic.append($('h1', '', esc(D.intro.title)), $('div', 'label', 'In this video'));
const introPts = D.intro.points.map(p => { const e = $('div', 'pt', '<i>✓</i><span>' + esc(p) + '</span>'); ic.append(e); return e; });
intro.append(ic); stage.append(intro);
const recap = $('div', 'layer'); const rc = $('div', 'card recap'); rc.append($('div', 'label', 'Remember'));
const recapPts = D.recap.points.map((p, i) => { const e = $('div', 'pt', '<i>' + (i + 1) + '</i><span>' + esc(p) + '</span>'); rc.append(e); return e; });
recap.append(rc); stage.append(recap);

// Scenes: vector or figure (or a B-roll window ffmpeg fills later), key-idea panel, terms, myth rows
const scenes = D.scenes.map((s, i) => {
  const n = i + 1, main = seg('scene', n), myth = seg('myth', n);
  const layer = $('div', 'layer'), box = $('div', 'box'), cam = $('div', 'cam'), ring = $('div', 'ring');
  let doc = null, total = 0;
  if (s.kind === 'broll') {
    cam.append($('div', 'broll'));
  } else {
    const fr = $('iframe'); fr.srcdoc = s.srcdoc;
    loads.push(new Promise(r => fr.addEventListener('load', () => {
      doc = fr.contentDocument; const svg = doc.querySelector('svg.nerdit-anim');
      if (svg) svg.classList.add('na-play');
      // Longest delay + duration: the build-up is stretched to finish while the narration explains it.
      total = Math.max(0, ...doc.getAnimations().map(a => a.effect.getComputedTiming().endTime || 0));
      r(); })));
    cam.append(fr);
  }
  cam.append(ring); box.append(cam);
  const panel = $('div', 'panel');
  panel.append($('div', 'label', 'Key idea'), $('div', 'key', esc(s.keyIdea)));
  const terms = $('div', 'terms'); const chips = main.terms.map(tm => { const c = $('div', 'chip', esc(tm.text)); terms.append(c); return c; });
  panel.append(terms);
  let wrong = null, right = null;
  if (s.myth) {
    const m = $('div', 'myth');
    wrong = $('div', 'row wrong', '<b>✗</b>' + esc(s.myth.wrong)); right = $('div', 'row right', '<b>✓</b>' + esc(s.myth.right));
    m.append(wrong, right); panel.append(m);
  }
  layer.append(box, panel); stage.append(layer);
  return { s, n, main, myth, layer, cam, ring, chips, wrong, right, get doc() { return doc; }, get total() { return total; },
           start: main.start, end: myth ? myth.end : main.end };
});

const topBar = $('div', 'top'); const topTitle = $('div', 'title'); const dots = $('div', 'dots');
const dotEls = D.scenes.map(() => { const d = $('div', 'dot'); dots.append(d); return d; });
topBar.append(topTitle, dots); stage.append(topBar);

function camera(sc, t) {
  let st = { x: .5, y: .5, zoom: 1 }, ringKey = null;
  for (const k of sc.main.focus) {
    if (t < k.t) break;
    const p = ease(clamp((t - k.t) / MOVE, 0, 1));
    st = { x: st.x + (k.x - st.x) * p, y: st.y + (k.y - st.y) * p, zoom: st.zoom + (k.zoom - st.zoom) * p };
    ringKey = p >= 1 && k.ring ? k : null;
  }
  const z = st.zoom * (1 + .03 * clamp((t - sc.start) / (sc.end - sc.start), 0, 1));
  const tx = clamp(360 - st.x * 720 * z, 720 - 720 * z, 0), ty = clamp(270 - st.y * 540 * z, 540 - 540 * z, 0);
  sc.cam.style.transform = `translate(${tx}px, ${ty}px) scale(${z})`;
  if (ringKey) {
    sc.ring.style.left = (ringKey.x * 720) + 'px'; sc.ring.style.top = (ringKey.y * 540) + 'px';
    const pulse = 1 + .12 * Math.sin((t - ringKey.t) * 2 * Math.PI * 1.1);
    sc.ring.style.transform = `scale(${pulse / z})`; sc.ring.style.opacity = 1;
  } else sc.ring.style.opacity = 0;
}

window.renderAt = function (t) {
  intro.style.opacity = fade(t, introSeg.start, introSeg.end);
  introPts.forEach((e, i) => { const p = clamp((t - introSeg.points[i]) / .4, 0, 1);
    e.style.opacity = p; e.style.transform = `translateX(${(1 - ease(p)) * 30}px)`; });
  recap.style.opacity = fade(t, recapSeg.start, recapSeg.end);
  recapPts.forEach((e, i) => { const p = clamp((t - recapSeg.points[i]) / .4, 0, 1);
    e.style.opacity = p; e.style.transform = `translateY(${(1 - ease(p)) * 20}px)`; });
  let current = null;
  for (const sc of scenes) {
    const on = t >= sc.start - FADE && t < sc.end + FADE;
    sc.layer.style.opacity = on ? fade(t, sc.start, sc.end) : 0;
    if (on) {
      current = sc; camera(sc, t);
      sc.main.terms.forEach((tm, i) => { const p = clamp((t - tm.t) / .3, 0, 1);
        sc.chips[i].style.opacity = p ? 1 : 0; sc.chips[i].style.transform = `scale(${p ? back(p) : 0})`; });
      if (sc.wrong) {
        sc.wrong.style.opacity = clamp((t - sc.myth.start - .2) / .3, 0, 1);
        sc.right.style.opacity = clamp((t - sc.myth.rightAt) / .3, 0, 1);
      }
      const doc = sc.doc;
      if (doc) {
        const spoken = Math.max(sc.main.end - sc.main.start - 1.3, 1);
        const at = sc.total ? clamp((t - sc.start - PAD_IN) / (spoken * BUILD), 0, 1) * sc.total : Math.max(0, t - sc.start - PAD_IN) * 1000;
        doc.getAnimations().forEach(a => { a.pause(); a.currentTime = at; });
      }
    }
  }
  topBar.style.opacity = current ? 1 : 0;
  if (current) {
    topTitle.textContent = current.s.title;
    dotEls.forEach((d, i) => { d.className = 'dot' + (i + 1 < current.n ? ' on' : i + 1 === current.n ? ' now' : ''); });
  }
};

window.ready = Promise.all([document.fonts.ready, ...loads]).then(() => true);
"""


def figure_doc(svg: str, css: str) -> str:
    """A standalone page for one lesson figure, styled exactly like the lesson."""
    return ("<!doctype html><html><head><meta charset='utf-8'><style>" + css + "</style><style>"
            "html,body{margin:0;height:100%;background:#fff;overflow:hidden}"
            ".nerdit-wrapper{height:100%;display:flex;align-items:center;justify-content:center;"
            "padding:28px;box-sizing:border-box;background:#fff}"
            ".nerdit-figure{width:100%;height:100%;max-width:none!important;margin:0!important}"
            "svg{width:100%;height:100%}</style></head><body><div class='nerdit-wrapper'>"
            "<div class='nerdit-figure'>" + svg + "</div></div></body></html>")


def lesson_css(css_dir: Path = CSS_DIR) -> str:
    return "\n".join((css_dir / name).read_text(encoding="utf-8") for name in LESSON_CSS
                     if (css_dir / name).is_file())


def build_stage(plan: dict, timeline: dict, svgs: list, css: str) -> str:
    """svgs: one entry per scene, the SVG markup to draw (None for a B-roll scene)."""
    scenes = []
    for s, svg in zip(plan["scenes"], svgs):
        item = {"kind": s["kind"], "title": s["title"], "keyIdea": s["keyIdea"], "myth": s.get("myth")}
        if svg is not None:
            item["srcdoc"] = figure_doc(svg, css)
        scenes.append(item)
    data = {"timeline": timeline, "scenes": scenes,
            "intro": {"title": plan["intro"]["title"], "points": plan["intro"]["points"]},
            "recap": {"points": plan["recap"]["points"]}}
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return ("<!doctype html><html><head><meta charset='utf-8'><style>" + STYLE + "</style></head><body>"
            "<script>window.DATA = " + blob + ";</script><script>" + SCRIPT + "</script></body></html>")
