import json, glob, os, sys, html

sys.path.insert(0, 'quran-tajweed-master')
from tajweed_classifier import label_ayah
from tree import json2tree
from translit_gen import translit_ayah

# rule -> (english, arabic, colour, short explanation)
RULES = {
    "madd_6":               ("Madd Laazim",         "مد لازم",         "#D40D0D", "Hold 6 counts. Obligatory."),
    "madd_muttasil":        ("Madd Muttasil",       "مد متصل",         "#F2700A", "Hold 4 to 5 counts."),
    "madd_munfasil":        ("Madd Munfasil",       "مد منفصل",        "#D9A106", "Hold 4 to 5 counts."),
    "madd_246":             ("Madd al-Aarid",       "مد عارض",         "#A87908", "Hold 2, 4 or 6 counts when stopping."),
    "madd_2":               ("Madd Tabee'i",        "مد طبيعي",        "#4A4740", "Natural madd. Hold 2 counts."),
    "ghunnah":              ("Ghunnah",             "غنة",             "#00A15E", "Nasal sound, 2 counts."),
    "idghaam_ghunnah":      ("Idghaam w/ Ghunnah",  "إدغام بغنة",      "#00A9A0", "Merge into the next letter with nasalisation."),
    "idghaam_no_ghunnah":   ("Idghaam w/o Ghunnah", "إدغام بغير غنة",  "#6D6AE0", "Merge into the next letter, no nasalisation."),
    "idghaam_shafawi":      ("Idghaam Shafawi",     "إدغام شفوي",      "#A32EDB", "Meem merges into meem."),
    "idghaam_mutajanisayn": ("Idghaam Mutajanisayn","إدغام متجانسين",  "#A32EDB", "Letters of the same articulation merge."),
    "idghaam_mutaqaribayn": ("Idghaam Mutaqaribayn","إدغام متقاربين",  "#A32EDB", "Letters of close articulation merge."),
    "ikhfa":                ("Ikhfa",               "إخفاء",           "#0090C8", "Hide the noon with a light nasal sound."),
    "ikhfa_shafawi":        ("Ikhfa Shafawi",       "إخفاء شفوي",      "#47B6E0", "Hide the meem before a baa."),
    "iqlab":                ("Iqlab",               "إقلاب",           "#E01FA8", "Noon turns into a meem sound."),
    "qalqalah":             ("Qalqalah",            "قلقلة",           "#0A2FD6", "Echo the letter with a slight bounce."),
    "hamzat_wasl":          ("Hamzat al-Wasl",      "همزة وصل",        "#8E959B", "Skipped when joined to the word before."),
    "lam_shamsiyyah":       ("Lam Shamsiyyah",      "لام شمسية",       "#8E959B", "Silent laam, merged into the next letter."),
    "silent":               ("Silent letter",       "حرف لا ينطق",     "#B9BFC4", "Written but not pronounced."),
}

# lower index wins when two rules cover the same character
PRIORITY = ["madd_6", "madd_muttasil", "madd_munfasil", "madd_246", "iqlab",
            "idghaam_ghunnah", "idghaam_no_ghunnah", "idghaam_shafawi",
            "idghaam_mutajanisayn", "idghaam_mutaqaribayn", "ikhfa_shafawi",
            "ikhfa", "ghunnah", "qalqalah", "lam_shamsiyyah", "hamzat_wasl",
            "silent", "madd_2"]

DIGITS = "٠١٢٣٤٥٦٧٨٩"
FAILED = []


def to_arabic_num(n):
    return "".join(DIGITS[int(d)] for d in str(n))


def load_trees():
    trees = {}
    for sf in glob.glob("quran-tajweed-master/rule_trees/*.start.json"):
        name = os.path.basename(sf).partition(".")[0]
        trees[name] = {
            "start": json2tree(json.load(open(sf))),
            "end": json2tree(json.load(open(sf.replace(".start.", ".end.")))),
        }
    return trees


def load_quran():
    """
    prefers the tanzil file the annotations were built against.
    download quran-uthmani.txt from tanzil.net (uthmani, with pause marks
    and sajdah signs) and drop it next to this script
    """
    if os.path.exists("quran-uthmani.txt"):
        out = {}
        for line in open("quran-uthmani.txt", encoding="utf-8-sig"):
            line = line.strip()
            if line and "|" in line:
                s, a, t = line.split("|", 2)
                out["%s:%s" % (s, a)] = t
        if out:
            return out, "tanzil"
    return json.load(open("quran_norm.json", encoding="utf-8")), "mirror"


def load_meta():
    return json.load(open("meta.json", encoding="utf-8"))


def owners_for(text, trees, key):
    try:
        ann = label_ayah((1, 1, text, trees))["annotations"]
    except AssertionError:
        FAILED.append(key)
        ann = []

    rank = {r: i for i, r in enumerate(PRIORITY)}
    owner = [None] * len(text)
    for a in sorted(ann, key=lambda x: rank.get(x["rule"], 99), reverse=True):
        for i in range(a["start"], min(a["end"], len(text))):
            owner[i] = a["rule"]
    return owner


def _span(rule, chunk):
    if not rule:
        return chunk
    return ('<span class="r-%s" data-rule="%s" title="%s">%s</span>'
            % (rule, rule, html.escape(RULES[rule][0]), chunk))


def arabic_word(text, owner, ws, we):
    out, i, used = [], ws, set()
    while i < we:
        j = i
        while j < we and owner[j] == owner[i]:
            j += 1
        if owner[i]:
            used.add(owner[i])
        out.append(_span(owner[i], html.escape(text[i:j])))
        i = j
    return "".join(out), used


def latin_word(pieces, owner):
    out = []
    for latin, idx in pieces:
        if not latin:
            continue
        rule = owner[idx] if idx < len(owner) else None
        out.append(_span(rule, html.escape(latin)))
    return "".join(out)


def build_ayah(text, trees, key):
    """returns (html, rules used) with the arabic and its latin, word by word"""
    owner = owners_for(text, trees, key)
    words = translit_ayah(text, owner)
    out, used = [], set()
    for pieces, ws, we in words:
        ar, u = arabic_word(text, owner, ws, we)
        used |= u
        out.append('<span class="w"><span class="wa">%s</span>'
                   '<span class="wt">%s</span></span>' % (ar, latin_word(pieces, owner)))
    return " ".join(out), used


def build_surah(m, quran, trees):
    sid = m["id"]
    body, used = [], set()
    for ayah in range(1, m["total_verses"] + 1):
        key = "%d:%d" % (sid, ayah)
        text = quran.get(key)
        if text is None:
            continue
        frag, u = build_ayah(text, trees, key)
        used |= u
        body.append(
            '<span class="ayah" id="a%d-%d" data-s="%d" data-a="%d">%s'
            '<span class="ayah-num">%s</span></span>'
            % (sid, ayah, sid, ayah, frag, to_arabic_num(ayah)))

    legend = []
    for r in PRIORITY:
        if r not in used:
            continue
        en, ar, col, desc = RULES[r]
        legend.append(
            '<li class="leg" data-rule="%s"><span class="sw" style="background:%s"></span>'
            '<span class="leg-txt"><b>%s</b><i>%s</i><em>%s</em></span></li>'
            % (r, col, html.escape(en), html.escape(ar), html.escape(desc)))

    return PAGE_TMPL.format(
        sid=sid,
        surah_ar=html.escape(m["name"]),
        surah_en=html.escape(m["transliteration"]),
        meta="%s &middot; %d ayat" % (m["type"].capitalize(), m["total_verses"]),
        body=" ".join(body),
        legend="\n".join(legend))


PAGE_TMPL = """
<section class="page" id="s{sid}" data-s="{sid}">
  <aside class="margin">
    <div class="key">
      <div class="margin-head">Tajweed key<span>rules in this surah</span></div>
      <ul class="legend">
{legend}
      </ul>
    </div>
  </aside>
  <div class="sheet">
    <header class="page-head">
      <span class="surah-en">{surah_en}</span>
      <span class="surah-ar">{surah_ar}</span>
      <span class="rng">{meta}</span>
    </header>
    <div class="mushaf" dir="rtl" lang="ar">{body}</div>
  </div>
</section>
"""


def build(outdir, only=None):
    """writes reader.html plus one small file per surah in surahs/"""
    trees = load_trees()
    quran, source = load_quran()
    meta = load_meta()
    if only:
        meta = [m for m in meta if m["id"] in only]
    print("text source:", source, "| surahs:", len(meta))

    frag_dir = os.path.join(outdir, "surahs")
    os.makedirs(frag_dir, exist_ok=True)
    total = 0
    for m in meta:
        frag = build_surah(m, quran, trees)
        path = os.path.join(frag_dir, "%d.html" % m["id"])
        open(path, "w", encoding="utf-8").write(frag)
        total += len(frag.encode("utf-8"))

    opts = "\n".join(
        '<option value="%d">%d. %s &middot; %s</option>'
        % (m["id"], m["id"], m["transliteration"], m["name"]) for m in meta)
    counts = json.dumps({m["id"]: m["total_verses"] for m in meta})
    names = json.dumps({m["id"]: m["transliteration"] for m in meta}, ensure_ascii=False)
    css = "\n".join(".r-%s{color:%s}" % (r, RULES[r][2]) for r in RULES)

    shell = os.path.join(outdir, "reader.html")
    open(shell, "w", encoding="utf-8").write(
        DOC_TMPL.format(css_rules=css, surah_options=opts,
                        ayah_counts=counts, surah_names=names))
    print("shell:", len(open(shell, "rb").read()), "bytes | fragments:", total, "bytes")


DOC_TMPL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Tajweed reader</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Amiri+Quran&family=Amiri:wght@400;700&family=Work+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--rule:#DCD6C6;--ink:#1B1A17;--paper:#FDFCF8;--gold:#B08C3A;--hl:#FFF3CE;--bar:64px;--ar-base:27px;--scale:1;--ar:calc(var(--ar-base) * var(--scale))}}
*{{box-sizing:border-box}}
body{{margin:0;background:#EDEAE1;font-family:"Work Sans",system-ui,sans-serif;color:var(--ink)}}

.bar{{position:sticky;top:0;z-index:20;background:#12312A;color:#EDE8DA;padding:13px 22px;
  display:flex;gap:20px;align-items:center;flex-wrap:wrap;font-size:15.5px}}
.bar strong{{font-weight:600;letter-spacing:.04em;font-size:16.5px}}
.bar input[type=checkbox]{{width:15px;height:15px}}
.bar label{{display:flex;align-items:center;gap:6px;cursor:pointer;white-space:nowrap}}
.bar .sp{{flex:1}}
.nav{{display:flex;gap:8px;align-items:center}}
.bar select{{
  background:#1B4A3E;color:#EDE8DA;border:1px solid rgba(224,206,147,.35);
  border-radius:4px;padding:7px 10px;font:inherit;font-size:15px;cursor:pointer;
  max-width:250px;
}}
.bar select:focus{{outline:2px solid var(--gold);outline-offset:1px}}
.here{{font-size:14.5px;color:#9FB3A9;white-space:nowrap}}
.credit{{
  margin-left:auto;align-self:flex-end;
  font-size:12.5px;color:#3E7361;text-decoration:none;white-space:nowrap;
  transition:color .15s ease;
}}
.credit:hover{{color:#7FA394}}

/* small ? that explains a toggle */
.hint{{
  display:inline-flex;align-items:center;justify-content:center;
  width:17px;height:17px;border-radius:50%;flex:0 0 17px;
  border:1px solid rgba(224,206,147,.55);color:#E4CE93;
  font-size:11.5px;font-weight:600;cursor:help;position:relative;margin-left:-12px;
}}
.hint:hover,.hint:focus{{background:rgba(224,206,147,.16);outline:none}}
.hint::after{{
  content:attr(data-tip);position:absolute;top:26px;left:50%;
  transform:translateX(-50%) translateY(-4px);
  width:290px;background:#0B211C;color:#DCD8CB;
  border:1px solid rgba(224,206,147,.3);border-radius:5px;
  padding:10px 12px;font-size:13px;font-weight:400;line-height:1.5;
  text-align:left;white-space:normal;letter-spacing:0;
  opacity:0;visibility:hidden;transition:opacity .14s ease, transform .14s ease;
  box-shadow:0 6px 20px rgba(0,0,0,.3);z-index:30;
}}
.hint:hover::after,.hint:focus::after{{opacity:1;visibility:visible;transform:translateX(-50%) translateY(0)}}

.msg{{text-align:center;color:#8A8578;font-size:15px;padding:60px 20px}}
.page{{display:flex;background:var(--paper);width:210mm;
  content-visibility:auto;contain-intrinsic-size:auto 1200px;
  margin:26px auto;box-shadow:0 2px 18px rgba(0,0,0,.14);scroll-margin-top:calc(var(--bar) + 16px)}}

.margin{{width:48mm;flex:0 0 48mm;border-left:1px solid var(--rule);
  padding:15mm 6mm 12mm;background:#FAF8F1}}
.key{{
  position:sticky;top:calc(var(--bar) + 14px);
  max-height:calc(100vh - var(--bar) - 42px);
  overflow-y:auto;scroll-behavior:smooth;
  scrollbar-width:none;-ms-overflow-style:none;
}}
.key::-webkit-scrollbar{{display:none}}
.margin-head{{font-size:9.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--gold);
  font-weight:600;border-bottom:1px solid var(--rule);padding-bottom:6px;margin-bottom:10px;
  position:sticky;top:0;background:#FAF8F1;z-index:2}}
.margin-head span{{display:block;color:#9A958A;letter-spacing:.07em;font-weight:400;margin-top:2px}}
.legend{{list-style:none;margin:0;padding:0 2px}}
.leg{{display:flex;gap:7px;padding:6px 4px;border-bottom:1px dotted var(--rule);
  cursor:default;border-radius:3px;transition:background .14s ease}}
.sw{{flex:0 0 9px;height:9px;margin-top:4px;border-radius:2px}}
.leg-txt b{{display:block;font-size:11px;font-weight:600;line-height:1.25}}
.leg-txt i{{display:block;font-family:Amiri,serif;font-style:normal;font-size:13.5px;
  color:#4A473F;line-height:1.3;direction:rtl}}
.leg-txt em{{display:block;font-style:normal;font-size:9.5px;color:#7C776B;line-height:1.35;margin-top:2px}}
.leg.hit-leg{{background:var(--hl)}}

.sheet{{flex:1;padding:15mm 12mm 15mm;display:flex;flex-direction:column;min-width:0}}
.page-head{{display:flex;align-items:baseline;gap:10px;font-size:11px;color:#8A8578;
  border-bottom:1px solid var(--rule);padding-bottom:8px;letter-spacing:.08em;
  position:sticky;top:var(--bar);background:var(--paper);padding-top:6px;z-index:5}}
.page-head .surah-en{{font-weight:600;color:#4A473F;text-transform:uppercase}}
.page-head .surah-ar{{font-family:Amiri,serif;font-size:17px;color:var(--gold)}}
.page-head .rng{{margin-left:auto}}

.mushaf{{font-family:"Amiri Quran",Amiri,serif;font-size:var(--ar);line-height:2.3;
  text-align:justify;padding-top:9mm;transition:font-size .15s ease}}
.ayah{{display:inline;scroll-margin-top:calc(var(--bar) + 90px)}}
.ayah-num{{font-family:Amiri,serif;font-size:.6em;color:var(--gold);
  border:1px solid var(--gold);border-radius:50%;display:inline-block;
  width:1.7em;height:1.7em;line-height:1.6em;text-align:center;
  margin:0 .2em;vertical-align:.15em}}
.ayah.pinged .ayah-num{{background:var(--hl)}}

/* word by word transliteration, only when the toggle is on */
.w{{display:inline}}
.wt{{display:none}}
body.show-tl .mushaf{{text-align:right;line-height:1.6}}
body.show-tl .ayah{{display:block;margin-bottom:2em}}
body.show-tl .w{{
  display:inline-flex;flex-direction:column;align-items:center;
  vertical-align:top;margin:0 .22em 1.5em;
}}
body.show-tl .wt{{
  display:block;direction:ltr;
  font-family:"Work Sans",system-ui,sans-serif;
  font-size:calc(var(--ar) * 0.42);line-height:1.35;
  color:#8A8478;margin-top:calc(var(--ar) * 0.34);white-space:nowrap;
}}

{css_rules}

/* toggles */
body.hide-madd2 .r-madd_2{{color:inherit}}
body.hide-madd2 .leg[data-rule="madd_2"]{{display:none}}
body.plain .mushaf span[class^="r-"]{{color:inherit}}
body.plain .legend{{opacity:.25}}

@media print{{
  body{{background:#fff}}
  .bar{{display:none}}
  .page{{margin:0;box-shadow:none;page-break-after:always;width:auto}}
  .page-head,.margin-head,.legend{{position:static}}
  @page{{size:A4 portrait;margin:0}}
}}
</style>
</head>
<body>

<div class="bar">
  <strong>Tajweed reader</strong>
  <div class="nav">
    <select id="sel-surah" aria-label="Surah">
{surah_options}
    </select>
    <select id="sel-ayah" aria-label="Ayah"></select>
  </div>
  <span class="here" id="here"></span>
  <label>Size
    <select id="sel-size" aria-label="Text size">
      <option value="0.75">75%</option>
      <option value="0.9">90%</option>
      <option value="1" selected>100%</option>
      <option value="1.25">125%</option>
      <option value="1.5">150%</option>
      <option value="1.75">175%</option>
      <option value="2">200%</option>
      <option value="2.5">250%</option>
    </select>
  </label>
  <span class="sp"></span>
  <label><input type="checkbox" id="t-madd2" checked> natural madd</label>
  <span class="hint" tabindex="0" data-tip="Madd tabee&#39;i is the plain two count stretch on alif, waw and yaa with no hamza or sukoon after it. It turns up in almost every line, so colouring it can bury the rules that need a decision. Untick to leave it black and keep the page calmer.">?</span>
  <label><input type="checkbox" id="t-plain"> plain text</label>
  <label><input type="checkbox" id="t-tl"> transliteration</label>
  <label><input type="checkbox" id="t-hover" checked> highlight key on hover</label>
  <a class="credit" href="https://sporkbots.stream/" target="_blank" rel="noopener">Website and reader by SporkTeam</a>
</div>

<main id="view"></main>
<p id="msg" class="msg">Loading&hellip;</p>

<script>
const b = document.body;
const AYAH_COUNTS = {ayah_counts};
const SURAH_NAMES = {surah_names};
// remembers settings and place. falls back to a cookie, then to nothing
const store = {{
  key: 'tajweed-reader',
  read() {{
    try {{
      const v = localStorage.getItem(this.key);
      if (v) return JSON.parse(v);
    }} catch (e) {{}}
    try {{
      const hit = document.cookie.split(';')
        .map(c => c.trim())
        .find(c => c.indexOf(this.key + '=') === 0);
      if (hit) return JSON.parse(decodeURIComponent(hit.slice(this.key.length + 1)));
    }} catch (e) {{}}
    return null;
  }},
  write(o) {{
    const v = JSON.stringify(o);
    try {{ localStorage.setItem(this.key, v); return; }} catch (e) {{}}
    try {{
      document.cookie = this.key + '=' + encodeURIComponent(v) +
        ';path=/;max-age=' + (60 * 60 * 24 * 365) + ';SameSite=Lax';
    }} catch (e) {{}}
  }}
}};
let state = store.read() || {{}};
let saveTimer = null;
function save() {{
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => store.write(state), 400);
}}

const selS = document.getElementById('sel-surah');
const selA = document.getElementById('sel-ayah');
const here = document.getElementById('here');
let syncing = false;

document.getElementById('t-madd2').addEventListener('change', e => {{
  b.classList.toggle('hide-madd2', !e.target.checked);
  state.madd2 = e.target.checked; save();
}});
document.getElementById('t-plain').addEventListener('change', e => {{
  b.classList.toggle('plain', e.target.checked);
  state.plain = e.target.checked; save();
}});
document.getElementById('t-tl').addEventListener('change', e => {{
  b.classList.toggle('show-tl', e.target.checked);
  state.tl = e.target.checked; save();
}});
document.getElementById('t-hover').addEventListener('change', e => {{
  b.classList.toggle('no-hover', !e.target.checked);
  state.hover = e.target.checked; save();
  if (!e.target.checked) document.querySelectorAll('.hit-leg')
    .forEach(n => n.classList.remove('hit-leg'));
}});

// fill the ayah list for a surah, keeping the chosen one if it still exists
function fillAyahs(sid, keep) {{
  const n = AYAH_COUNTS[sid] || 0;
  const want = keep && keep <= n ? keep : 1;
  selA.innerHTML = '';
  for (let i = 1; i <= n; i++) {{
    const o = document.createElement('option');
    o.value = i;
    o.textContent = 'Ayah ' + i;
    selA.appendChild(o);
  }}
  selA.value = want;
}}

function goTo(sid, ayah, smooth) {{
  const el = document.getElementById('a' + sid + '-' + ayah);
  if (!el) return;
  syncing = true;
  el.scrollIntoView({{ behavior: smooth === false ? 'auto' : 'smooth', block: 'center' }});
  el.classList.add('pinged');
  setTimeout(() => el.classList.remove('pinged'), 1400);
  setTimeout(() => {{ syncing = false; }}, 700);
}}

selS.addEventListener('change', () => {{
  const sid = +selS.value;
  fillAyahs(sid, 1);
  state.s = sid; state.a = 1; save();
  window.scrollTo(0, 0);
  loadSurah(sid, 1);
}});
selA.addEventListener('change', () => goTo(+selS.value, +selA.value));

const view = document.getElementById('view');
const msg = document.getElementById('msg');
const cache = new Map();
let io = null;

function wire(page) {{
  const m = page.querySelector('.mushaf');
  const clear = () => page.querySelectorAll('.hit-leg')
                          .forEach(n => n.classList.remove('hit-leg'));
  m.addEventListener('mouseover', e => {{
    if (b.classList.contains('no-hover')) return;
    const t = e.target.closest('[data-rule]');
    clear();
    if (!t) return;
    const leg = page.querySelector('.leg[data-rule="' + t.dataset.rule + '"]');
    if (!leg) return;
    leg.classList.add('hit-leg');
    const key = page.querySelector('.key');
    const kb = key.getBoundingClientRect(), lb = leg.getBoundingClientRect();
    if (lb.top < kb.top + 28) key.scrollTop -= (kb.top + 28 - lb.top);
    else if (lb.bottom > kb.bottom - 6) key.scrollTop += (lb.bottom - kb.bottom + 6);
  }});
  m.addEventListener('mouseleave', clear);

  // follow the reader down the page and keep the dropdowns in step
  if (io) io.disconnect();
  const seen = new Map();
  io = new IntersectionObserver(entries => {{
    entries.forEach(e => seen.set(e.target, e.isIntersecting ? e.intersectionRatio : 0));
    let best = null, bestR = 0;
    seen.forEach((r, el) => {{ if (r > bestR) {{ bestR = r; best = el; }} }});
    if (!best || syncing) return;
    const sid = +best.dataset.s, ayah = +best.dataset.a;
    selA.value = ayah;
    state.s = sid; state.a = ayah; save();
    here.textContent = (SURAH_NAMES[sid] || '') + '  ' + sid + ':' + ayah;
  }}, {{ rootMargin: '-25% 0px -55% 0px', threshold: [0, .25, .5, 1] }});
  page.querySelectorAll('.ayah').forEach(a => io.observe(a));
}}

async function loadSurah(sid, ayah) {{
  if (cache.has(sid)) {{
    view.innerHTML = cache.get(sid);
  }} else {{
    msg.textContent = 'Loading surah ' + sid + '\u2026';
    msg.style.display = 'block';
    try {{
      const r = await fetch('surahs/' + sid + '.html');
      if (!r.ok) throw new Error(r.status);
      const html = await r.text();
      cache.set(sid, html);
      view.innerHTML = html;
    }} catch (e) {{
      msg.textContent = 'Could not load surah ' + sid +
        '. Open this page over http, not as a local file.';
      return;
    }}
  }}
  msg.style.display = 'none';
  const page = view.querySelector('.page');
  if (page) wire(page);
  if (ayah) goTo(sid, ayah, false);
}}

function restore() {{
  const set = (id, on) => {{
    const el = document.getElementById(id);
    if (el.checked !== on) {{ el.checked = on; el.dispatchEvent(new Event('change')); }}
  }};
  if (state.madd2 === false) set('t-madd2', false);
  if (state.plain === true) set('t-plain', true);
  if (state.tl === true) set('t-tl', true);
  if (state.hover === false) set('t-hover', false);
  if (state.scale) {{
    const sel = document.getElementById('sel-size');
    sel.value = state.scale;
    document.documentElement.style.setProperty('--scale', state.scale);
  }}
  const sid = state.s && AYAH_COUNTS[state.s] ? state.s : +selS.value;
  const ayah = state.s === sid && state.a ? state.a : 1;
  selS.value = sid;
  fillAyahs(sid, ayah);
  loadSurah(sid, ayah);
}}

if (document.fonts && document.fonts.ready) document.fonts.ready.then(restore);
else window.addEventListener('load', restore);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    only = [int(x) for x in sys.argv[1:]] or None
    build("/mnt/user-data/outputs/quran-mastery", only)
    print("uncoloured ayat:", len(FAILED), FAILED[:10])
