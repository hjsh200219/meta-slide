#!/usr/bin/env python3
"""meta-slide — 내용에 맞는 슬라이드 템플릿·한글 서체를 Jev 가 고르고, 원칙대로 덱을 만들고 점검한다.

  python3 slide.py [--local] [--port 8766] [--no-open]       # 인자 없이 = 로컬 갤러리(템플릿·인포그래픽·색·서체) — serve.py
                                                           #   --local: SSH 로 붙은 내 PC 브라우저에서 열 주소(Tailscale)
  python3 slide.py templates [--json]                      # 템플릿 목록(인터넷 MIT 230종)
  python3 slide.py layouts <템플릿>                         # 그 템플릿의 장(슬라이드)별 레이아웃 종류
  python3 slide.py pick <브리프|개요.md|-> [--n 3] [--scheme light|dark] [--template id] [--exclude a,b]
                          [--title-font id] [--body-font id] [--series 이름] [--no-jev] [--json]
  python3 slide.py new <덱폴더> --template <id> [--title-font id] [--body-font id] [--brand '#hex'] [--force]
  python3 slide.py outline <개요.md> [--template id] [--jev] [--json]   # 원칙 점검 + 헤드라인만 읽기 + 장별 레이아웃 대응
  python3 slide.py shots <덱.html> [--out 폴더] [--pdf] [--json]        # 장마다 캡처 + 넘침·대체 서체·자간 검사 + 한 장 모음
  python3 slide.py record <덱폴더> [--series 이름] [--title 제목]        # 이력(비슷한 자료는 같은 템플릿)
  python3 slide.py history | fonts

원칙 정본은 data/principles.md. Jev 로는 브리프·개요 글만 나간다(api.typesafe.ai) — 미공개·개인정보 자료는 --no-jev.
표준 라이브러리만 쓴다. shots 만 Playwright(python) 와 Pillow 가 필요하다.
"""
import json
import os
import pathlib
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
TEMPLATE_DIRS = (os.path.join(DATA, "house"), os.path.join(DATA, "templates"))
INDEX_PATH = os.path.join(DATA, "index.json")  # build_index.py 가 만든다(레이아웃·한국어 요약)
FONTS_PATH = os.path.join(DATA, "fonts.json")
HISTORY_PATH = os.environ.get("META_SLIDE_HISTORY", os.path.expanduser("~/.local/share/meta-slide/history.jsonl"))
# 원칙 PDF 는 원칙만 쓴다 — 그 자료의 바탕·색·서체를 본뜬 템플릿은 두지 않는다(2026-10-22 사용자 지시). 기본값도 인터넷 MIT 템플릿.
DEFAULT_TEMPLATE = {"light": "blue-professional", "dark": "broadside", "mixed": "signal", None: "broadside"}
DEFAULT_FONTS = ("pretendard", "pretendard")
HANGUL = re.compile(r"[가-힣]")

# 장 레이아웃 종류 — 원칙(간지·1 slide 1 idea·도식화·요약)에 맞춘 닫힌 목록. build_index.py 와 outline 이 같이 쓴다.
LAYOUTS = {
    "cover": "표지 — 발표 제목·부제·발표자·날짜",
    "agenda": "목차 — 장 제목 목록",
    "divider": "간지 — 장(섹션)을 여는 구분 장, 장 번호와 장 제목",
    "statement": "한두 줄 메시지만 크게(Large & Bold) — 주장·전환·핵심 문장",
    "points": "헤드라인 + 근거 목록 3~5개(박스·카드)",
    "diagram": "도식 — 단계·흐름·구조·관계·프레임워크",
    "compare": "두 안 비교 — VS·전후·장단점·표 두 칸",
    "number": "큰 숫자 하나 또는 지표 몇 개 — 수치가 주인공",
    "chart": "그래프 — 막대·선·비중·추이",
    "table": "표 — 여러 행과 열의 자료",
    "quote": "인용 — 고객·전문가의 말, 증언",
    "image": "사진·화면·사례 이미지가 주인공",
    "timeline": "일정·로드맵·연혁",
    "team": "사람·조직·팀 소개",
    "summary": "요약 — 앞의 내용을 몇 줄로 정리",
    "closing": "마무리 — 감사·연락처·다음 행동",
}
# 템플릿에 그 레이아웃이 없을 때 대신 쓸 순서
LAYOUT_FALLBACK = {
    "table": ["chart", "compare", "points"], "chart": ["number", "diagram", "points"], "number": ["statement", "chart"],
    "timeline": ["diagram", "points"], "diagram": ["points", "compare"], "compare": ["points", "diagram"],
    "quote": ["statement", "divider"], "image": ["statement", "points"], "team": ["points", "diagram"],
    "summary": ["points", "statement"], "agenda": ["points", "summary"], "statement": ["divider", "quote", "points"],
    "divider": ["statement", "cover"], "closing": ["statement", "cover", "divider"], "points": ["diagram", "statement"],
    "cover": ["divider", "statement"],
}


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def file_url(path):
    """로컬 파일 → file:// 주소. Windows 드라이브 경로(C:\\…)와 한글 경로도 맞게 만든다."""
    return pathlib.Path(os.path.abspath(path)).as_uri()


def utf8_console():
    """Windows 콘솔·파이프 기본 인코딩(cp949)에서 한글·기호(✓) 출력이 깨지거나 멈추지 않게."""
    if os.name == "nt":
        for s in (sys.stdout, sys.stderr):
            try:
                s.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass


# ── 공통 ─────────────────────────────────────────────────────────


def opt(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def positional(argv):
    out, skip = [], False
    for i, a in enumerate(argv):
        if skip:
            skip = False
            continue
        if a.startswith("--"):
            if a not in ("--json", "--jev", "--no-jev", "--pdf", "--force", "--all", "--ko-sample"):
                skip = True
            continue
        out.append(a)
    return out


def read_text_arg(arg):
    if arg == "-":
        return sys.stdin.read()
    if arg and os.path.isfile(arg):
        return _read(arg)
    return arg or ""


def load_index():
    if os.path.exists(INDEX_PATH):
        return json.loads(_read(INDEX_PATH))
    return {}


def load_templates():
    """slug → 메타. house(사내 템플릿 — 지금은 없음)가 먼저, 그다음 인터넷 템플릿. index.json 의 한국어 요약·레이아웃을 합친다."""
    idx = load_index()
    out = {}
    for base in TEMPLATE_DIRS:
        if not os.path.isdir(base):
            continue
        for slug in sorted(os.listdir(base)):
            p = os.path.join(base, slug, "template.json")
            if not os.path.exists(p):
                continue
            try:
                t = json.loads(_read(p))
            except ValueError as e:  # 쓰는 중이거나 깨진 메타데이터 — 그 템플릿만 건너뛴다
                sys.stderr.write(f"slide.py: {slug}/template.json 을 읽지 못해 건너뜀 ({e})\n")
                continue
            t["slug"] = slug
            t["dir"] = os.path.join(base, slug)
            t["house"] = base.endswith("house")
            t.update({k: v for k, v in idx.get(slug, {}).items() if k not in t or k in ("layouts", "accents")})
            out[slug] = t
    return out


def load_fonts():
    return json.loads(_read(FONTS_PATH))["fonts"]


def load_jev():
    import importlib.util
    path = os.path.join(HERE, "jev.py")  # 번들 사본만 — PC 마다 같게(키 저장소는 setup.py)
    spec = importlib.util.spec_from_file_location("meta_slide_jev", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def template_desc(t):
    best = t.get("best_for_ko") or t.get("best_for", "")
    return (f"{t.get('name')}: {t.get('tagline_ko') or t.get('tagline', '')} | 어울림: {best} | 분위기 {', '.join(t.get('mood', []))}"
            f" | 어조 {', '.join(t.get('tone', []))} | 격식 {t.get('formality', '')} | 밀도 {t.get('density', '')}"
            f" | 바탕 {t.get('scheme', '')} | 포인트 색 {t.get('accents', '?')}개 | 피할 곳: {t.get('avoid_for', '')}")[:600]


# ── 이력(비슷한 자료는 같은 템플릿) ───────────────────────────────


def load_history(path=None):
    path = path or HISTORY_PATH
    if not os.path.exists(path):
        return []
    out = []
    for line in _read(path).splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def series_hit(series, history):
    for h in reversed(history):
        if series and h.get("series") == series:
            return h
    return None


# ── pick ─────────────────────────────────────────────────────────


def keyword_pick(text, templates, scheme=None):
    """Jev 를 못 쓸 때: 바탕 지정 > 기본값(인터넷 MIT 템플릿)."""
    slug = DEFAULT_TEMPLATE.get(scheme) or DEFAULT_TEMPLATE[None]
    return slug if slug in templates else next(iter(templates))


def font_options(fonts, role, template):
    """제목·본문 서체 후보. 본문은 읽히는 서체만(손글씨·디스플레이 제외 — 템플릿이 손글씨 계열이면 손글씨 허용)."""
    tone = " ".join(template.get("mood", []) + template.get("tone", [])).lower()
    playful = any(w in tone for w in ("playful", "handmade", "handwritten", "whimsical", "cute", "craft"))
    out = {}
    for fid, f in fonts.items():
        if role == "title" and f["role"] in ("title", "both"):
            out[fid] = f
        elif role == "body" and f["role"] in ("body", "both"):
            if f["kind"] == "hand" and not playful:
                continue
            if f["kind"] == "mono" and "terminal" not in tone and "geeky" not in tone and "retro-tech" not in tone:
                continue
            out[fid] = f
    return out


# ── 색 체계 ─────────────────────────────────────────────────────

COLORS_PATH = os.path.join(DATA, "colors.json")
KEEP_COLOR = "template"  # 템플릿 원래 색 유지


def load_colors():
    return json.loads(_read(COLORS_PATH))["systems"]


def _rgb(h):
    return hex_to_rgb(h)


def rel_lum(h):
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = [x / 255 for x in _rgb(h)]
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = sorted((rel_lum(a), rel_lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def hue_word(h):
    import colorsys
    r, g, b = [x / 255 for x in _rgb(h)]
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    if ss < 0.15 or ll < 0.08 or ll > 0.95:
        return "무채색" if 0.15 < ll < 0.85 else ("검정" if ll <= 0.15 else "흰색")
    deg = hh * 360
    for lim, w in ((15, "빨강"), (40, "주황"), (65, "노랑"), (160, "초록"), (195, "청록"), (240, "파랑"), (265, "남색"), (300, "보라"), (340, "분홍"), (361, "빨강")):
        if deg < lim:
            return w
    return "빨강"


def color_desc(c):
    return (f"{c['name']} — 주색 {hue_word(c['primary'])} · 강조 {hue_word(c['accent'])} · 보조 {hue_word(c['secondary'])} · "
            f"{'어두운' if c['scheme'] == 'dark' else '밝은'} 바탕 · {c.get('notes', '')}")[:300]


def color_options(tpl):
    """템플릿 바탕과 같은 밝기의 색 체계 + 원래 색 유지. 글자 대비 7 이상·강조 대비 3 이상만."""
    out = {}
    for cid, c in load_colors().items():
        if tpl.get("scheme") in ("light", "dark") and c["scheme"] != tpl["scheme"]:
            continue
        if contrast(c["fg"], c["bg"]) < 7 or contrast(c["primary"], c["bg"]) < 3:
            continue
        out[cid] = c
    return out


LIT = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(?:,\s*[\d.]+\s*)?\)")


def _norm(lit):
    if lit.startswith("#"):
        h = lit[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        return "#" + h.upper()
    nums = re.findall(r"[\d.]+", lit)
    return "#%02X%02X%02X" % tuple(min(255, int(float(x))) for x in nums[:3])


def _hls(h):
    import colorsys
    r, g, b = [x / 255 for x in _rgb(h)]
    return colorsys.rgb_to_hls(r, g, b)


def _from_hls(hh, ll, ss):
    import colorsys
    r, g, b = colorsys.hls_to_rgb(hh, max(0, min(1, ll)), max(0, min(1, ss)))
    return "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def _mix(a, b, t):
    ra, rb = _rgb(a), _rgb(b)
    return "#%02X%02X%02X" % tuple(round(x + (y - x) * t) for x, y in zip(ra, rb))


def template_roles(t, text):
    """템플릿 바탕·글자 색과 많이 쓰인 유채색 순서."""
    pal = {k: v.upper() for k, v in (t.get("palette") or {}).items() if isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v)}
    lits = [_norm(m.group(0)) for m in LIT.finditer(text)]
    freq = {}
    for c in lits:
        freq[c] = freq.get(c, 0) + 1
    pool = list(pal.values()) or list(freq)
    if not pool:
        return None
    bg = next((v for k, v in pal.items() if re.search(r"^(bg|background|paper|canvas|base|void|page|cream|bone)", k, re.I)), None)
    if not bg:
        bg = (min if t.get("scheme") == "dark" else max)(pool, key=rel_lum)
    fg = next((v for k, v in pal.items() if re.search(r"^(ink|text|fg|foreground|type)", k, re.I)), None)
    if not fg:
        fg = max(pool, key=lambda c: contrast(c, bg))
    sat = sorted((c for c in freq if _hls(c)[2] > 0.25 and 0.12 < _hls(c)[1] < 0.92), key=lambda c: -freq[c])
    return {"bg": bg, "fg": fg, "saturated": sat}


def recolor_map(t, system, text):
    roles = template_roles(t, text)
    if not roles:
        return {}
    lb, lf = _hls(roles["bg"])[1], _hls(roles["fg"])[1]
    targets = [system["primary"], system["accent"], system["secondary"]]
    lead = roles["saturated"][:3]
    m = {}
    for c in {_norm(x.group(0)) for x in LIT.finditer(text)}:
        hh, ll, ss = _hls(c)
        if c in roles["saturated"]:
            if c in lead:
                tgt = targets[lead.index(c)]
            else:  # 나머지 유채색은 색상이 가장 가까운 주요 유채색의 대상으로
                near = min(lead, key=lambda x: min(abs(_hls(x)[0] - hh), 1 - abs(_hls(x)[0] - hh)))
                tgt = targets[lead.index(near)]
            th, tl, ts = _hls(tgt)
            m[c] = tgt if abs(tl - ll) <= 0.22 else _from_hls(th, ll, min(ts, max(ss, 0.35)))
        else:  # 무채색·옅은 색 — 바탕↔글자 사이 위치를 지킨다
            span = (lf - lb) or 1e-6
            pos = max(0.0, min(1.0, (ll - lb) / span))
            m[c] = _mix(system["bg"], system["fg"], pos)
    return m


def apply_recolor(text, mapping):
    def sub(mo):
        lit = mo.group(0)
        new = mapping.get(_norm(lit))
        if not new:
            return lit
        if lit.startswith("#"):
            return new
        r, g, b = _rgb(new)
        parts = re.findall(r"[\d.]+", lit)
        return f"rgba({r}, {g}, {b}, {parts[3]})" if len(parts) > 3 else f"rgb({r}, {g}, {b})"
    return LIT.sub(sub, text)


def ig_palette(t, text, system=None):
    if system:
        return [system["primary"], system["accent"], system["secondary"], system["muted_fg"]]
    roles = template_roles(t, text) or {"saturated": [], "fg": "#333333"}
    pal = roles["saturated"][:3] or [roles["fg"]]
    return pal + [roles["fg"]]


# ── 인포그래픽 ──────────────────────────────────────────────────

IG_DIR = os.path.join(DATA, "infographics")
IG_MIN = 0.6  # 「인포그래픽으로 보여 주면 더 잘 전달되는가」 예 확률이 이 이상인 장만


def load_ig():
    return json.loads(_read(os.path.join(IG_DIR, "catalog.json")))


def ig_families(cat, usable_only=True):
    """계열 → 모양 목록. usable_only 면 qa_infographics.py 가 ok 로 본 것만(영문 고정 문구·렌더 실패 제외)."""
    fam = {}
    for name, v in cat.items():
        if usable_only and v.get("qa", "ok") != "ok":
            continue
        fam.setdefault(v["family"], {"desc": v["desc"].split(" · 모양")[0], "names": []})["names"].append(name)
    return fam


def ig_example(name, cat=None):
    cat = cat or load_ig()
    ex = json.loads(_read(os.path.join(IG_DIR, "examples.json")))
    field = cat[name]["field"]
    key = "compares:swot" if name == "compare-swot" else ("compares:quadrant" if "quadrant" in name else field)
    return ex.get(key, ex["lists"]).replace("{name}", name)


# ── 큰 선택(옵션 255개 상한) ────────────────────────────────────

def big_choice(jev, state, instr, options, timeout_s=90):
    """옵션이 많으면 묶음별 예선 → 결승. (고른 것, 확신, 상위 확률 목록)."""
    keys = list(options)
    if len(keys) <= 200:
        a = jev.ask(state, {"q": jev.choice(instr, options)}, timeout_s=timeout_s)
        ch, conf = jev.choice_of(a, "q")
        probs = (a.get("q") or {}).get("probabilities") or {}
        return ch, conf, sorted(probs.items(), key=lambda kv: -kv[1])
    groups = [keys[i:i + 150] for i in range(0, len(keys), 150)]
    qs = {f"g{i}": jev.choice(instr, {k: options[k] for k in g}) for i, g in enumerate(groups)}
    a = jev.ask(state, qs, timeout_s=timeout_s)
    finals = []
    for i in range(len(groups)):
        probs = (a.get(f"g{i}") or {}).get("probabilities") or {}
        finals += [k for k, _ in sorted(probs.items(), key=lambda kv: -kv[1])[:6]]
    finals = [k for k in dict.fromkeys(finals) if k in options] or keys[:200]
    return big_choice(jev, state, instr, {k: options[k] for k in finals}, timeout_s)


# ── pick: ① 템플릿 → ④ 색 체계 → ⑤ 서체 (② ③ 인포그래픽은 장마다 outline --jev) ──

def pick(text, scheme=None, template_id=None, exclude=(), title_font=None, body_font=None, color=None, n=3, use_jev=True,
         series=None, history_path=None):
    templates = load_templates()
    fonts = load_fonts()
    colors = load_colors()
    cands = {k: t for k, t in templates.items() if k not in exclude and (not scheme or t.get("scheme") in (scheme, "mixed"))}
    if not cands:
        raise SystemExit("조건에 맞는 템플릿이 없습니다(--scheme·--exclude 확인)")
    res = {"how": None, "template": None, "template_confidence": None, "candidates": [], "color": None, "color_how": None,
           "title_font": None, "body_font": None, "font_how": None, "jev_error": None}
    hit = series_hit(series, load_history(history_path)) if series else None
    jev = None
    if use_jev:
        try:
            jev = load_jev()
        except Exception as e:
            res["jev_error"] = f"import: {e}"

    # ① 템플릿: 사용자 지정 > 같은 시리즈 이력 > Jev > 기본값
    if template_id:
        if template_id not in templates:
            raise SystemExit(f"없는 템플릿: {template_id} (slide.py templates)")
        res.update(template=template_id, how="user")
    elif hit and hit.get("template") in templates:
        res.update(template=hit["template"], how=f"series:{series}")
        title_font, body_font = title_font or hit.get("title_font"), body_font or hit.get("body_font")
        color = color or hit.get("color")
    elif jev:
        try:
            ch, conf, ranked = big_choice(
                jev, {"brief": text[:6000]},
                "이 발표 자료의 브리프(목적·청중·내용)에 가장 잘 맞는 슬라이드 템플릿을 하나 고른다. 발표 목적·청중·분위기·격식·내용 밀도로 판단한다. "
                "메시지를 가리지 않는 바탕(단색 + 포인트 한 색)을 가진 템플릿이 같은 조건이면 낫다.",
                {k: template_desc(t) for k, t in cands.items()})
            if ch in cands:
                res.update(template=ch, template_confidence=round(conf, 3), how="jev")
                res["candidates"] = [{"slug": k, "p": round(v, 3), "name": templates[k]["name"]} for k, v in ranked[:max(n, 1)] if k in templates]
        except Exception as e:
            res["jev_error"] = f"template: {type(e).__name__}: {str(e)[:200]}"
    if not res["template"]:
        res.update(template=keyword_pick(text, cands, scheme), how="default")
    tpl = templates[res["template"]]
    if not res["candidates"]:
        res["candidates"] = [{"slug": tpl["slug"], "p": None, "name": tpl["name"]}]

    # ④ 색 체계 · ⑤ 서체 — 고른 템플릿을 보여 주고 한 번에(서로 독립 문항)
    if title_font and title_font not in fonts or body_font and body_font not in fonts:
        raise SystemExit("없는 서체 id (slide.py fonts)")
    if color and color != KEEP_COLOR and color not in colors:
        raise SystemExit("없는 색 체계 id (slide.py colors)")
    c_opts = color_options(tpl)
    t_opts, b_opts = font_options(fonts, "title", tpl), font_options(fonts, "body", tpl)
    q = {}
    if jev:
        typo = tpl.get("typography", {})
        state = {"brief": text[:4000], "template": f"{tpl['name']} — {tpl.get('tagline_ko') or tpl.get('tagline', '')}",
                 "template_colors": (tpl.get("palette") or {}).get("description", ""),
                 "template_typography": f"제목 {typo.get('display', '')} · 본문 {typo.get('body', '')} · {typo.get('style', '')}"}
        if not color:
            opts = {KEEP_COLOR: f"템플릿 원래 색 유지 — {(tpl.get('palette') or {}).get('description', '')}"[:300]}
            opts.update({k: color_desc(c) for k, c in c_opts.items()})
            q["color"] = jev.choice("이 발표 자료에 맞는 색 체계를 하나 고른다. 발표 주제의 업종·분야와 분위기에 맞고, 흑백 위에 포인트 한 색으로 강조하기 좋은 것. "
                                    "템플릿 원래 색이 주제와 잘 맞으면 원래 색 유지를 고른다.", dict(list(opts.items())[:250]))
        if not title_font:
            q["title"] = jev.choice("이 발표 자료의 한글 제목 서체를 하나 고른다. 브리프의 분위기와 고른 템플릿의 영문 서체 성격(세리프·산세리프·손글씨·굵기)에 어울리는 것.",
                                    {k: f"{f['name']} — {f['desc']}" for k, f in t_opts.items()})
        if not body_font:
            q["body"] = jev.choice("이 발표 자료의 한글 본문 서체를 하나 고른다. 작은 글씨로도 잘 읽히고, 고른 템플릿의 영문 본문 서체 성격과 어울리는 것.",
                                   {k: f"{f['name']} — {f['desc']}" for k, f in b_opts.items()})
        if q:
            try:
                ans = jev.ask(state, q, timeout_s=60)
                if "color" in q:
                    cc, ccf = jev.choice_of(ans, "color")
                    if cc == KEEP_COLOR or cc in colors:
                        res.update(color=cc, color_how="jev", color_confidence=round(ccf, 3))
                if "title" in q or "body" in q:
                    tf, tc = jev.choice_of(ans, "title") if "title" in q else (title_font, 1.0)
                    bf, bc = jev.choice_of(ans, "body") if "body" in q else (body_font, 1.0)
                    if tf in fonts and bf in fonts:
                        res.update(title_font=tf, body_font=bf, font_how="jev", title_font_confidence=round(tc, 3), body_font_confidence=round(bc, 3))
            except Exception as e:
                res["jev_error"] = (res["jev_error"] or "") + f" color/fonts: {type(e).__name__}: {str(e)[:160]}"
    if not res["color"]:
        res.update(color=color or KEEP_COLOR, color_how="user" if color else "default")
    if not res["title_font"]:
        res.update(title_font=title_font or DEFAULT_FONTS[0], body_font=body_font or DEFAULT_FONTS[1],
                   font_how="user" if (title_font and body_font) else "default")
    if color and res["color_how"] == "jev":
        res["color_how"] = "user"
    res["template_name"] = tpl["name"]
    res["scheme"] = tpl.get("scheme")
    res["house"] = tpl["house"]
    if res["color"] != KEEP_COLOR:
        res["color_name"] = colors[res["color"]]["name"]
    return res


def cmd_pick(argv):
    args = positional(argv)
    text = read_text_arg(args[0] if args else opt(argv, "--brief", ""))
    if not text.strip():
        raise SystemExit("브리프가 비었습니다 — 파일·문장·- (stdin)")
    exclude = tuple(x for x in (opt(argv, "--exclude", "") or "").split(",") if x)
    r = pick(text, scheme=opt(argv, "--scheme"), template_id=opt(argv, "--template"), exclude=exclude,
             title_font=opt(argv, "--title-font"), body_font=opt(argv, "--body-font"), color=opt(argv, "--color"), n=int(opt(argv, "--n", "3")),
             use_jev="--no-jev" not in argv, series=opt(argv, "--series"), history_path=opt(argv, "--history"))
    if "--json" in argv:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    fonts = load_fonts()
    conf = f" 확신 {r['template_confidence']}" if r.get("template_confidence") is not None else ""
    print(f"템플릿: {r['template']} ({r['template_name']}, {r['scheme']}) — 경로 {r['how']}{conf}")
    if len(r["candidates"]) > 1:
        print("후보: " + " · ".join(f"{c['slug']} {c['p']}" for c in r["candidates"]))
    cname = "템플릿 원래 색" if r["color"] == KEEP_COLOR else f"{r['color']} ({r.get('color_name')})"
    cconf = f" 확신 {r['color_confidence']}" if r.get("color_confidence") is not None else ""
    print(f"색 체계: {cname} — 경로 {r['color_how']}{cconf}")
    print(f"서체: 제목 {fonts[r['title_font']]['name']} · 본문 {fonts[r['body_font']]['name']} — 경로 {r['font_how']}")
    if r.get("jev_error"):
        print(f"Jev 실패로 기본값 사용: {r['jev_error']}", file=sys.stderr)
    print(f"다음: python3 {os.path.relpath(__file__)} new <덱폴더> --template {r['template']} --color {r['color']} "
          f"--title-font {r['title_font']} --body-font {r['body_font']}")


# ── new: 템플릿 복사 + 한글 서체·자간·줄바꿈 주입 ────────────────

GENERIC = r"(?:sans-serif|serif|monospace|cursive|fantasy|system-ui|ui-sans-serif|ui-serif|ui-monospace)"
TITLE_VAR = re.compile(r"(display|head|title|serif|heading|hero|accent|^--f[dht]$|^--ff-?d)", re.I)  # --fd 같은 줄임 변수도 제목


SYSTEMISH = re.compile(r"^(-apple-system|blinkmacsystemfont|system-ui|ui-[\w-]+|helvetica( neue)?|arial|segoe ui|roboto|"
                       r"sfmono-regular|sf mono|menlo|monaco|consolas|courier( new)?|georgia|times( new roman)?|"
                       r"sans-serif|serif|monospace|cursive|fantasy|emoji|apple color emoji|noto color emoji)$", re.I)


def _kr_insert(value, fam):
    """font-family 값에 한글 서체를 끼운다 — 템플릿의 웹 서체들 뒤, 시스템·일반 서체(-apple-system·Arial·sans-serif 등) 앞.
    영문 글자는 템플릿 서체로, 한글은 고른 서체로 그려진다(시스템 서체가 앞에 있으면 macOS 가 한글을 Apple SD Gothic 으로 대신 그린다)."""
    v = value.rstrip()
    vm = re.match(r"^(\s*var\(\s*--[\w-]+\s*,)(.+)(\)\s*(?:!important)?\s*)$", v)
    if vm and fam not in v:  # var(--x, "A", serif) — 변수가 없을 때 쓰는 대체 목록에도 끼운다
        return vm.group(1) + _kr_insert(vm.group(2), fam) + vm.group(3)
    if fam in v or v.strip().startswith("var(") or v.strip() in ("inherit", "initial", "unset", "revert"):
        return value
    imp = ""
    m = re.search(r"\s*!important\s*$", v)
    if m:
        v, imp = v[:m.start()], v[m.start():]
    parts = [x.strip() for x in re.findall(r"""(?:"[^"]*"|'[^']*'|[^,])+""", v)]
    at = len(parts)
    for i, ptok in enumerate(parts):
        if SYSTEMISH.match(ptok.strip("'\" ")):
            at = i
            break
    lead = v[:len(v) - len(v.lstrip())]
    parts.insert(at, f"'{fam}'")
    return lead + ", ".join(parts) + imp


def rewrite_fonts(text, display_family, body_family, title_kr, body_kr, whole_css=False):
    """CSS(<style>·style 속성)의 font-family·font 단축·--*font* 변수에 한글 서체를 끼운다. 바뀐 개수도 돌려준다."""
    count = [0]
    same = (display_family or "").strip().lower() == (body_family or "").strip().lower()

    def role_for(prop, val):
        if prop.startswith("--"):
            return title_kr if TITLE_VAR.search(prop) else body_kr
        if "monospace" in val.lower() or "mono" in val.lower():
            return body_kr
        if display_family and not same and display_family.lower() in val.lower():
            return title_kr
        return body_kr

    def sub_decl(m):
        prop, val, end = m.group(1), m.group(2), m.group(3)
        if prop.strip().lower().startswith("font") and not prop.strip().lower().startswith("font-family"):
            # font 단축: 크기 뒤 서체 목록이 있을 때만
            if not re.search(r"\d(px|em|rem|%|pt)\b", val) or val.strip().startswith("var("):
                return m.group(0)
        fam = role_for(prop.strip().lower(), val)
        new = _kr_insert(val, fam)
        if new != val:
            count[0] += 1
        return f"{prop}:{new}{end}"

    pat = re.compile(r"((?<![\w-])font-family\s*|(?<![\w-])font\s*|--[\w-]*font[\w-]*\s*):([^;{}]+?)(\s*(?:;|}|$))", re.I | re.M)
    # 이름에 font 가 없는 변수(--fd·--sans 등)라도 값이 서체 목록(끝이 일반 계열)이면 서체 변수로 본다
    vpat = re.compile(r"((?<![\w-])--(?![\w-]*font)[\w-]+\s*):([^;{}]*?,\s*" + GENERIC + r")(\s*(?:;|}|$))", re.I | re.M)
    css = lambda s: vpat.sub(sub_decl, pat.sub(sub_decl, s))
    if whole_css:  # .css 파일 전체
        return css(text), count[0]
    # <style> 블록 안(서체 이름에 큰따옴표가 올 수 있다)과 style="…" 속성 안(큰따옴표가 경계)을 따로 고친다
    out = re.sub(r"(<style[^>]*>)(.*?)(</style>)", lambda m: m.group(1) + css(m.group(2)) + m.group(3), text, flags=re.S | re.I)
    out = re.sub(r'(\sstyle=")([^"]*)(")', lambda m: m.group(1) + css(m.group(2)) + m.group(3), out, flags=re.I)
    return out, count[0]


META_CSS = """/* meta-slide — 한글 서체·줄바꿈·자간 (principles.md: 자간·굴림/바탕 금지·단어 중간 줄바꿈 금지) */
:root { --ms-title: '%(title)s'; --ms-body: '%(body)s'; %(igvars)s }
.ms-ig { box-sizing: border-box; }
/* deck-stage 는 :host 에 시스템 서체를 걸어 장들이 body 서체를 못 물려받는다 — 바깥에서 덮는다 */
deck-stage { font-family: %(deck)s; }
body, body * { word-break: keep-all; overflow-wrap: break-word; line-break: strict; }
button, input, select, textarea { font-family: inherit; }  /* 양식 요소는 서체를 물려받지 않는다(브라우저 기본 서체 → 한글이 시스템 서체로) */
"""

META_JS = r"""/* meta-slide — 한글이 든 글자 요소의 넓은 자간·좁은 줄간격을 고친다(영문용 값이 한글에서 «없어 보이는» 문제). */
(function () {
  var HANGUL = /[가-힣]/;
  function ownText(el) { var s = ''; for (var n = el.firstChild; n; n = n.nextSibling) if (n.nodeType === 3) s += n.nodeValue; return s; }
  function fix(root) {
    var els = (root || document).querySelectorAll('body *');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (!HANGUL.test(ownText(el))) continue;
      var cs = getComputedStyle(el), fs = parseFloat(cs.fontSize) || 16;
      var ls = cs.letterSpacing === 'normal' ? 0 : parseFloat(cs.letterSpacing);
      if (ls > fs * 0.06) { el.style.letterSpacing = '0.01em'; el.setAttribute('data-ms-fix', 'tracking'); }
      var lh = cs.lineHeight === 'normal' ? fs * 1.2 : parseFloat(cs.lineHeight);
      if (lh < fs * 1.12 && el.getBoundingClientRect().height > lh * 1.5) { el.style.lineHeight = '1.18'; el.setAttribute('data-ms-fix', 'leading'); }
    }
  }
  // 큰 제목 한글이 장 밖으로 넘치면 글자 크기를 줄인다(영문 압축 서체 기준으로 잡은 크기가 한글에서는 넓다). 보이는 장만 잴 수 있어 장을 넘길 때마다 다시 돈다.
  function slideRect(el) {
    var s = el.closest('deck-stage > *, .deck > section, .slide, section');
    var r = s ? s.getBoundingClientRect() : null;
    return r && r.width > 1 ? r : {left: 0, top: 0, right: innerWidth, bottom: innerHeight};
  }
  function over(el, b) { var r = el.getBoundingClientRect(); return r.left < b.left - 2 || r.right > b.right + 2 || r.top < b.top - 2 || r.bottom > b.bottom + 2; }
  function fit(root) {
    var els = (root || document).querySelectorAll('body *');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (el.hasAttribute('data-ms-fit') || !HANGUL.test(ownText(el))) continue;
      var r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1) continue;
      var fs0 = parseFloat(getComputedStyle(el).fontSize) || 16; if (fs0 < 40) continue;
      var b = slideRect(el); if (!over(el, b)) continue;
      var fs = fs0;
      while (fs > fs0 * 0.55 && over(el, b)) { fs *= 0.92; el.style.fontSize = fs.toFixed(1) + 'px'; }
      el.setAttribute('data-ms-fit', String(Math.round(fs / fs0 * 100)));
    }
    // 큰 제목이 줄 수가 늘어 아래 글(꼬리말·목록)을 장 밖으로 밀면 그 장의 큰 한글 제목을 함께 줄인다(최소 70%).
    var slides = document.querySelectorAll('deck-stage > *, .deck > section, .slide');
    for (var j = 0; j < slides.length; j++) {
      var sl = slides[j], b = sl.getBoundingClientRect();
      if (b.width < 1 || b.right <= 1 || b.left >= innerWidth - 1) continue;
      var big = [], all = sl.querySelectorAll('*');
      for (var k = 0; k < all.length; k++) {
        var e = all[k], t = ownText(e).trim(); if (!t || !HANGUL.test(t)) continue;
        var f = parseFloat(getComputedStyle(e).fontSize) || 16;
        if (f >= 40) big.push([e, e.dataset.msFs0 ? parseFloat(e.dataset.msFs0) : f]);
      }
      if (!big.length) continue;
      for (var step = 0; step < 5 && pushedOut(sl, b); step++)
        for (var m = 0; m < big.length; m++) {
          var e2 = big[m][0], f0 = big[m][1], cur = parseFloat(getComputedStyle(e2).fontSize);
          if (cur <= f0 * 0.7) continue;
          e2.dataset.msFs0 = f0; e2.style.fontSize = (cur * 0.92).toFixed(1) + 'px'; e2.setAttribute('data-ms-fit', 'pushed');
        }
    }
  }
  function pushedOut(sl, b) {
    var all = sl.querySelectorAll('*');
    for (var k = 0; k < all.length; k++) {
      var e = all[k], t = ownText(e).replace(/[\s.,:;!?'"()\[\]\/%+\-–—·•&@#*]/g, '');
      if (t.length <= 2) continue;
      var r = e.getBoundingClientRect(); if (r.width < 1 || r.height < 1) continue;
      if (r.bottom > b.bottom + 2 && r.top < b.bottom - 1) return true;
    }
    return false;
  }
  window.metaSlideFix = fix;
  window.metaSlideFit = fit;
  function later() { setTimeout(function () { fit(document); }, 450); }
  function run() { fix(document); fit(document); if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { fix(document); fit(document); }); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run); else run();
  addEventListener('keydown', later); addEventListener('click', later); addEventListener('hashchange', later); addEventListener('resize', later);
})();
"""


def hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def saturation(h):
    r, g, b = [x / 255 for x in hex_to_rgb(h)]
    mx, mn = max(r, g, b), min(r, g, b)
    return 0 if mx == 0 else (mx - mn) / mx


def accent_of(t):
    """template.json palette 에서 가장 채도 높은 색(포인트). 없으면 None."""
    pal = t.get("palette") or {}
    best = None
    for k, v in pal.items():
        if isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v):
            s = saturation(v)
            if best is None or s > best[1]:
                best = (v, s)
    return best[0] if best and best[1] > 0.25 else None


def tone_down(hex_color, amount=0.12):
    """브랜드 색을 적절히 톤 다운(principles p171) — 회색 쪽으로 조금 섞는다."""
    r, g, b = hex_to_rgb(hex_color)
    gray = (r + g + b) / 3
    mix = lambda c: round(c + (gray - c) * amount)
    return "#%02X%02X%02X" % (mix(r), mix(g), mix(b))


def inject(html, t, title_font, body_font, brand=None):
    fonts = load_fonts()
    tf, bf = fonts[title_font], fonts[body_font]
    typo = t.get("typography") or {}
    html, n = rewrite_fonts(html, typo.get("display"), typo.get("body"), tf["family"], bf["family"])
    links = []
    for f in {tf["css"], bf["css"]}:
        links.append(f'<link rel="stylesheet" href="{f}" data-meta-slide="font" />')
    head = ("\n" + "\n".join(links) + '\n<link rel="stylesheet" href="meta-slide.css" data-meta-slide="css" />\n'
            '<script src="meta-slide.js" data-meta-slide="js"></script>\n'
            '<script src="infographics/infographic.min.js" data-meta-slide="ig"></script>\n'
            '<script src="infographics/icons.js" data-meta-slide="ig"></script>\n')
    tail = '<script src="infographics/meta-slide-ig.js" data-meta-slide="ig"></script>\n'
    html = html.replace("</body>", tail + "</body>", 1) if "</body>" in html else html + tail
    html = re.sub(r"<html(\s[^>]*)?>", lambda m: re.sub(r'\slang="[^"]*"', "", m.group(0)).replace("<html", '<html lang="ko"', 1), html, count=1)
    if "</head>" in html:
        html = html.replace("</head>", head + "</head>", 1)
    else:
        html = head + html
    swapped = 0
    if brand:
        acc = accent_of(t)
        if acc:
            new = tone_down(brand)
            swapped = len(re.findall(re.escape(acc), html, re.I))
            html = re.sub(re.escape(acc), new, html, flags=re.I)
    return html, {"font_decls": n, "brand_swaps": swapped}


def cmd_new(argv):
    args = positional(argv)
    if not args:
        raise SystemExit("사용: new <덱폴더> --template <id> [--color id|template] [--title-font id] [--body-font id] [--brand '#hex']")
    dest = os.path.abspath(args[0])
    templates = load_templates()
    slug = opt(argv, "--template")
    if slug not in templates:
        raise SystemExit(f"--template 이 없거나 모르는 템플릿: {slug}")
    t = templates[slug]
    title_font, body_font = opt(argv, "--title-font", DEFAULT_FONTS[0]), opt(argv, "--body-font", DEFAULT_FONTS[1])
    fonts = load_fonts()
    for f in (title_font, body_font):
        if f not in fonts:
            raise SystemExit(f"모르는 서체: {f} (slide.py fonts)")
    if os.path.exists(dest) and os.listdir(dest) and "--force" not in argv:
        raise SystemExit(f"{dest} 가 비어 있지 않습니다 — 다른 폴더나 --force")
    os.makedirs(dest, exist_ok=True)
    for name in os.listdir(t["dir"]):
        src = os.path.join(t["dir"], name)
        if name in ("template.html",):
            continue
        dst = os.path.join(dest, name)
        (shutil.copytree(src, dst, dirs_exist_ok=True) if os.path.isdir(src) else shutil.copy2(src, dst))
    html = _read(os.path.join(t["dir"], "template.html"))
    if "deck-stage.js" in html and not os.path.exists(os.path.join(dest, "deck-stage.js")):
        shutil.copy2(os.path.join(DATA, "deck-stage.js"), dest)
    brand = opt(argv, "--brand")
    color = opt(argv, "--color", KEEP_COLOR)
    system = None
    if color != KEEP_COLOR:
        colors = load_colors()
        if color not in colors:
            raise SystemExit(f"모르는 색 체계: {color} (slide.py colors)")
        system = colors[color]
    # ④ 색 체계: 템플릿의 HTML·CSS 색 값을 역할(바탕·글자·주색·강조·보조)대로 바꾼다
    css_files = [os.path.join(r, f) for r, _, fs in os.walk(dest) for f in fs if f.endswith(".css")]
    alltext = html + "".join(_read(f) for f in css_files)
    recolored = 0
    if system:
        mapping = recolor_map(t, system, alltext)
        recolored = len(mapping)
        html = apply_recolor(html, mapping)
        for f in css_files:
            txt = _read(f)
            _write(f, apply_recolor(txt, mapping))
    igpal = ig_palette(t, alltext, system)
    typo = t.get("typography") or {}
    css_decls = 0
    for f in css_files:  # 서체를 별도 CSS 파일에 둔 템플릿(html-ppt 등)
        txt = _read(f)
        new, k = rewrite_fonts(txt, typo.get("display"), typo.get("body"), fonts[title_font]["family"], fonts[body_font]["family"], whole_css=True)
        if k:
            _write(f, new)
            css_decls += k
    html, stats = inject(html, t, title_font, body_font, brand)
    stats["recolored"] = recolored
    stats["font_decls"] += css_decls
    _write(os.path.join(dest, "deck.html"), html)
    igdst = os.path.join(dest, "infographics")
    os.makedirs(igdst, exist_ok=True)
    for f in ("infographic.min.js", "icons.js", "meta-slide-ig.js", "LICENSE-antv-infographic", "LICENSE-tabler-icons"):
        shutil.copy2(os.path.join(IG_DIR, f), igdst)
    body_latin = (t.get("typography") or {}).get("body")
    deck_font = (f"'{body_latin}', " if body_latin else "") + f"'{fonts[body_font]['family']}', sans-serif"
    _write(os.path.join(dest, "meta-slide.css"), 
        META_CSS % {"title": fonts[title_font]["family"], "body": fonts[body_font]["family"], "deck": deck_font,
                    "igvars": " ".join(f"--ms-ig-{i + 1}: {c};" for i, c in enumerate(igpal))})
    _write(os.path.join(dest, "meta-slide.js"), META_JS)
    meta = {"template": slug, "template_name": t["name"], "color": color, "title_font": title_font, "body_font": body_font, "brand": brand,
            "ig_palette": igpal,
            "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **stats,
            "license": (t.get("source") or {}).get("repo", "zarazhangrui/beautiful-html-templates") + " (MIT)" if not t["house"] else "house(사내)"}
    _write(os.path.join(dest, "meta-slide.json"), json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"만듦: {os.path.join(dest, 'deck.html')}")
    print(f"템플릿 {slug} · 색 {'원래 색' if not system else system['name'] + f' (색 값 {recolored}개 교체)'}"
          f" · 제목 {fonts[title_font]['name']} · 본문 {fonts[body_font]['name']} · 서체 선언 {stats['font_decls']}곳에 한글 서체"
          + (f" · 포인트 색 {stats['brand_swaps']}곳 → 브랜드 {tone_down(brand)}" if brand else ""))
    lay = t.get("layouts") or []
    if lay:
        print("장 레이아웃: " + " · ".join(f"{x['i'] + 1}.{x['layout']}" for x in lay))
    print("다음: 개요대로 장을 복제·삭제하고 글을 바꾼 뒤 → python3 slide.py shots " + os.path.join(dest, "deck.html"))


# ── outline: 원칙 점검 ───────────────────────────────────────────


def parse_outline(text):
    """--- 머리말 --- / # 간지 / ## 헤드라인 {layout} / 본문 줄 / > 노트"""
    meta, body = {}, text
    m = re.match(r"\s*---\n(.*?)\n---\n", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        body = text[m.end():]
    sections, slides = [], []
    cur_sec = None
    for raw in body.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            head = line[3:].strip()
            tag = None
            tm = re.search(r"\{([\w=-]+)\}\s*$", head)
            if tm:
                tag = tm.group(1).replace("layout=", "")
                head = head[:tm.start()].strip()
            slides.append({"n": len(slides) + 1, "section": cur_sec, "headline": head, "tag": tag, "body": [], "notes": []})
        elif line.startswith("# "):
            cur_sec = line[2:].strip()
            sections.append(cur_sec)
        elif line.startswith(">") and slides:
            slides[-1]["notes"].append(line.lstrip("> ").strip())
        elif line.strip() and slides:
            slides[-1]["body"].append(line.strip())
    return meta, sections, slides


def check_outline(meta, sections, slides):
    issues = []
    add = lambda lv, code, msg, n=None: issues.append({"level": lv, "code": code, "msg": msg, "slide": n})
    if not meta.get("title"):
        add("warn", "no-title", "머리말에 title 이 없습니다 — 표지 제목")
    if not meta.get("presenter") and not meta.get("intent"):
        add("warn", "no-intent", "프리젠터 의도(presenter/intent)가 없습니다 — 「이 문서의 핵심이 무엇인가?」를 먼저 적는다(p75)")
    if len(slides) >= 8 and len(sections) < 2:
        add("warn", "no-dividers", f"{len(slides)}장인데 간지(# 장 제목)가 {len(sections)}개 — 흐름을 크게 나누고 간지로 표시한다(p76)")
    for s in slides:
        h = s["headline"]
        if not h:
            add("error", "no-headline", "헤드라인이 비었습니다", s["n"])
            continue
        if len(h) > 42:
            add("warn", "long-headline", f"헤드라인 {len(h)}자 — 두 줄을 넘기면 핵심 줄만 크게, 세 줄이면 점층(p190~191)", s["n"])
        bullets = [b for b in s["body"] if re.match(r"^([-*•]|\d+[.)])\s", b)]
        if len(bullets) > 5:
            add("warn", "too-many-points", f"근거 {len(bullets)}개 — 1 slide 1 idea: 핵심만 강조, 나머지는 박스·다음 장으로(p79)", s["n"])
        if sum(1 for b in s["body"] if b.startswith("|")) >= 2:
            add("info", "table", "표가 있습니다 — 가능하면 그래프로, 안 되면 선을 최소화(p228)", s["n"])
        words = sum(len(b) for b in s["body"])
        if words > 260:
            add("warn", "dense", f"본문 {words}자 — 프리젠터가 말할 것을 노트(>)로 옮긴다", s["n"])
    if slides:
        last = slides[-1]
        is_sum = lambda s: s["tag"] == "summary" or re.search(r"요약|정리|결론|summary|오늘 드린", s["headline"], re.I)
        tail = [s for s in slides[-3:] if is_sum(s)]
        if not tail:
            add("warn", "no-summary", "끝에 요약 장이 없습니다 — 마지막으로 요약하라(p82). ## 헤드라인 {summary}", last["n"])
    return issues


def jev_slide_checks(slides, meta, layouts_avail=None, template=None):
    """장마다 Jev: 한 장 한 메시지(noul) · 헤드라인이 메시지인가(noul) · 레이아웃(choice)
    · ② 인포그래픽으로 보여 줄 만한가(noul) · ③ 어느 인포그래픽 계열(choice) → 그 계열 안 모양(choice, 둘째 호출). 장끼리 병렬."""
    jev = load_jev()
    cat = load_ig()
    fams = ig_families(cat)
    fam_opts = {k: f"{v['desc']} ({len(v['names'])}종)" for k, v in fams.items()}
    style = f"{template['name']} — {template.get('tagline', '')}" if template else ""
    opts = {k: v for k, v in LAYOUTS.items() if (not layouts_avail or k in layouts_avail)}
    if len(opts) < 2:
        opts = dict(LAYOUTS)

    def one(s):
        state = {"deck_title": meta.get("title", ""), "section": s["section"] or "", "headline": s["headline"],
                 "body": "\n".join(s["body"])[:1500]}
        q = {"one_idea": jev.noul("이 슬라이드가 하나의 메시지(아이디어)만 전달하는가? 서로 다른 주장이 둘 이상 섞여 있으면 아니오."),
             "message_headline": jev.noul("헤드라인이 「현황」「배경」 같은 주제 이름표가 아니라, 듣는 사람이 가져갈 결론·주장을 문장으로 말하는가?"),
             "layout": jev.choice("이 슬라이드 내용을 가장 잘 보여 줄 장 레이아웃을 하나 고른다. 핵심이 둘 이상이면 도식, 숫자가 주인공이면 숫자·그래프, 표는 가능하면 그래프.", opts),
             "infographic": jev.noul("이 슬라이드의 본문이 단계·순서·흐름·비교·구성 요소·계층·관계·비중·추이처럼 구조가 있는 정보라서, "
                                     "글 목록 대신 인포그래픽(도식·차트)으로 보여 주면 더 빨리 이해되는가? 한 문장 주장·인용·표지·간지는 아니오."),
             "ig_family": jev.choice("이 슬라이드 본문을 인포그래픽으로 그린다면 가장 맞는 형태를 하나 고른다. 본문 항목의 관계(차례·대등·대립·포함·연결·수치)로 판단한다.", fam_opts)}
        try:
            a = jev.ask(state, q, timeout_s=60)
            lay, lc = jev.choice_of(a, "layout")
            fam, fc = jev.choice_of(a, "ig_family")
            ig_p = jev.noul_of(a, "infographic")
            out = {"n": s["n"], "one_idea": jev.noul_of(a, "one_idea"), "message_headline": jev.noul_of(a, "message_headline"),
                   "layout": lay, "layout_confidence": round(lc, 3), "infographic": ig_p, "ig_family": fam, "ig_family_confidence": round(fc, 3)}
            text_first = {"cover", "divider", "statement", "quote", "summary", "closing", "agenda", "number"}
            if s["tag"] in text_first or (not s["tag"] and lay in text_first - {"number"}):
                ig_p = out["infographic"] = None  # 글이 주인공인 장 — 원칙: 한 줄 메시지·요약은 글로
            if ig_p is not None and ig_p >= IG_MIN and fam in fams:
                names = fams[fam]["names"]
                if len(names) == 1:
                    out["ig"] = names[0]
                else:
                    a2 = jev.ask({**state, "deck_style": style}, {"v": jev.choice(
                        "이 슬라이드 내용과 덱의 시각 스타일에 가장 어울리는 인포그래픽 모양을 하나 고른다. 항목 수·글 길이·아이콘 필요 여부와 덱의 분위기로 판단한다.",
                        {nm: cat[nm]["desc"] for nm in names[:250]})}, timeout_s=60)
                    v, vc = jev.choice_of(a2, "v")
                    out["ig"], out["ig_confidence"] = (v if v in cat else names[0]), round(vc, 3)
            return out
        except Exception as e:
            return {"n": s["n"], "error": f"{type(e).__name__}: {str(e)[:120]}"}

    with ThreadPoolExecutor(max_workers=6) as ex:
        return list(ex.map(one, slides))


def map_layouts(slides, template, judged=None):
    """장마다 템플릿의 어느 장을 복제할지. 태그 > Jev 레이아웃 > 기본(points). 없으면 LAYOUT_FALLBACK 순서."""
    lay = template.get("layouts") or []
    by = {}
    for x in lay:
        by.setdefault(x["layout"], []).append(x)
    jmap = {j["n"]: j for j in (judged or [])}
    out = []
    use = {}
    for s in slides:
        want = s["tag"] or (jmap.get(s["n"], {}).get("layout")) or "points"
        got, chain = None, [want] + LAYOUT_FALLBACK.get(want, []) + ["points", "statement"]
        for w in chain:
            if by.get(w):
                k = use.get(w, 0)
                got = by[w][k % len(by[w])]
                use[w] = k + 1
                break
        out.append({"n": s["n"], "want": want, "use": got["layout"] if got else None,
                    "template_slide": got["i"] + 1 if got else None, "label": got.get("label") if got else None})
    return out


def cmd_outline(argv):
    args = positional(argv)
    if not args:
        raise SystemExit("사용: outline <개요.md> [--template id] [--jev]")
    meta, sections, slides = parse_outline(read_text_arg(args[0]))
    issues = check_outline(meta, sections, slides)
    templates = load_templates()
    tpl = templates.get(opt(argv, "--template")) if opt(argv, "--template") else None
    judged = None
    if "--jev" in argv:
        avail = {x["layout"] for x in (tpl.get("layouts") or [])} if tpl else None
        judged = jev_slide_checks(slides, meta, avail, tpl)
        for j in judged:
            if j.get("error"):
                issues.append({"level": "info", "code": "jev-error", "msg": j["error"], "slide": j["n"]})
                continue
            if j["one_idea"] is not None and j["one_idea"] < 0.5:
                issues.append({"level": "warn", "code": "multi-idea", "msg": f"한 장에 메시지가 둘 이상으로 보입니다(Jev {j['one_idea']:.2f}) — 나누거나 도식화(p79·p81)", "slide": j["n"]})
            if j["message_headline"] is not None and j["message_headline"] < 0.5:
                issues.append({"level": "warn", "code": "label-headline", "msg": f"헤드라인이 이름표처럼 보입니다(Jev {j['message_headline']:.2f}) — 결론을 문장으로", "slide": j["n"]})
    mapping = map_layouts(slides, tpl, judged) if tpl else None
    if "--json" in argv:
        print(json.dumps({"meta": meta, "sections": sections, "slides": slides, "issues": issues, "jev": judged, "mapping": mapping},
                         ensure_ascii=False, indent=2))
        return
    print(f"■ {meta.get('title', '(제목 없음)')} — {len(slides)}장 · 간지 {len(sections)}개")
    print("\n[헤드라인만 읽기 — 이것만으로 스토리가 되면 OK (p94)]")
    sec = object()
    for s in slides:
        if s["section"] != sec:
            sec = s["section"]
            if sec:
                print(f"  ── {sec}")
        print(f"  {s['n']:>2}. {s['headline']}")
    if mapping:
        print(f"\n[장 레이아웃 → {tpl['slug']} 의 몇 번 장을 복제할지]")
        for m in mapping:
            alt = "" if m["want"] == m["use"] else f" (원함 {m['want']} → 대체)"
            print(f"  {m['n']:>2}. {m['use']} ← 템플릿 {m['template_slide']}번 「{m['label']}」{alt}")
    if judged:
        igs = [j for j in judged if j.get("ig") and j.get("infographic") is not None]
        print(f"\n[인포그래픽 — {len(igs)}장]" + ("" if igs else " 없음(글·숫자 장으로 충분)"))
        for j in igs:
            print(f"  {j['n']:>2}. {j['ig']}  (인포그래픽 적합 {j['infographic']:.2f} · 계열 {j['ig_family']} {j['ig_family_confidence']})"
                  f" — 예시: python3 slide.py ig {j['ig']}")
    print("\n[점검]" + (" 문제 없음" if not issues else ""))
    for i in issues:
        where = f"{i['slide']}장 " if i.get("slide") else ""
        print(f"  {i['level']:5s} {where}{i['msg']}")


# ── shots: 캡처 + 자동 검사 ─────────────────────────────────────

SLIDE_COUNT_JS = """() => {
  const ds = document.querySelector('deck-stage'); if (ds) return ds.children.length;
  const dk = document.querySelectorAll('.deck > section, .deck > .slide'); if (dk.length) return dk.length;
  const s = [...document.querySelectorAll('.slide')].filter(e => !e.parentElement.closest('.slide')); if (s.length) return s.length;
  return document.querySelectorAll('section').length || 1;
}"""

# deck-stage 의 장 번호·조작 안내 오버레이(그림자 DOM)는 발표용 UI 라 캡처에서 뺀다
HIDE_UI_JS = """() => document.querySelectorAll('deck-stage').forEach(d => d.shadowRoot &&
  d.shadowRoot.querySelectorAll('.overlay').forEach(o => { o.style.display = 'none'; }))"""

# 등장 애니메이션(타자기·페이드)을 끝 상태로 — 캡처가 애니메이션 도중이면 글이 잘려 보인다. 무한 반복은 finish 가 안 돼 건너뛴다.
FINISH_ANIM_JS = r"""() => { for (const a of document.getAnimations()) { try { a.finish(); } catch (e) {} } return true; }"""

KO_SAMPLE_JS = r"""() => {
  const SAMPLE = '발표자료핵심메시지한장한생각강약조절도식요약간지구도헤드라인근거숫자비교정리마무리';
  let k = 0;
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const nodes = []; while (walk.nextNode()) nodes.push(walk.currentNode);
  for (const n of nodes) {
    const p = n.parentElement; if (!p || p.closest('script,style,template,svg,.ms-ig,code,pre')) continue;
    const t = n.nodeValue; if (!/[A-Za-z]{2,}|[぀-ヿ一-鿿]/.test(t)) continue;  // 한 글자 한자·가나도 바꾼다
    n.nodeValue = t.replace(/[A-Za-z]{2,}|[぀-ヿ一-鿿]+/g, w => {
      const len = /[぀-ヿ一-鿿]/.test(w) ? w.length : Math.max(1, Math.round(w.length * 0.6));
      let out = ''; for (let i = 0; i < len; i++) { out += SAMPLE[(k++) % SAMPLE.length]; if (i % 4 === 3 && i < len - 1) out += ' '; }
      return out;  // 실제 한국어처럼 3~4글자마다 띄어 쓴다(띄어쓰기 없는 원문을 그대로 옮기면 keep-all 로 줄이 안 바뀐다)
    });
    // 원문에 남은 전각 문장부호(：，。；！？「」)는 일반 부호로 — 한국어 덱에는 없다
    n.nodeValue = n.nodeValue.replace(/[：]/g, ':').replace(/[，、]/g, ',').replace(/[。]/g, '.')
      .replace(/[；]/g, ';').replace(/[！]/g, '!').replace(/[？]/g, '?').replace(/[「」『』]/g, '"');
  }
  if (window.metaSlideFix) window.metaSlideFix(document);
  return nodes.length;
}"""

CHECK_JS = r"""() => {
  const HANGUL = /[가-힣]/;
  const own = el => { let s=''; for (let n=el.firstChild;n;n=n.nextSibling) if (n.nodeType===3) s+=n.nodeValue; return s; };
  const W = innerWidth, H = innerHeight, out = [], ko = [];
  let k = 0;
  document.querySelectorAll('[data-ms-k]').forEach(e => e.removeAttribute('data-ms-k'));
  for (const el of document.querySelectorAll('body *')) {
    const t = own(el).trim(); if (!t) continue;
    if (el.closest('aside.notes, .notes, [data-notes], script, style, template')) continue;  // 발표자 노트는 화면 밖에 숨겨 둔 글
    if (el.checkVisibility && !el.checkVisibility({opacityProperty: true, visibilityProperty: true})) continue;
    const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1) continue;
    if (r.right <= 1 || r.bottom <= 1 || r.left >= W - 1 || r.top >= H - 1) continue;  // 화면 완전히 밖(노트 서랍 등)은 의도된 것
    const cs = getComputedStyle(el);
    // 「01」「26」「A」「GO!」처럼 일부러 밖으로 걸친 장식 글자(견본 치환 뒤 한두 글자 한글 포함)
    const core = t.replace(/[\s.,:;!?'"()\[\]\/%+\-–—·•&@#*]/g, '');
    const deco = (!HANGUL.test(t) && core.length <= 3) || core.length <= 2;
    if (!deco && (r.left < -2 || r.right > W + 2 || r.bottom > H + 2 || r.top < -2)) out.push({kind: 'out-of-canvas', text: t.slice(0, 40)});
    const clip = /(hidden|clip)/.test(cs.overflow + cs.overflowX + cs.overflowY) || cs.textOverflow === 'ellipsis';
    const fpx = parseFloat(cs.fontSize) || 16;  // 한 줄 글은 한글 글리프가 줄 높이 위아래로 조금 걸쳐도 잘린 것이 아니다
    if (clip && (el.scrollWidth > el.clientWidth + 2 || el.scrollHeight > el.clientHeight + Math.max(2, fpx * 0.35))) out.push({kind: 'clipped', text: t.slice(0, 40)});
    if (HANGUL.test(t) && k < 12) {
      // 기호(◎·⬇·이모지 등 한글·영문·숫자·흔한 부호가 아닌 글자) 수 — 그만큼의 시스템 서체 사용은 한글 대체가 아니다
      const sym = [...t].filter(c => !/[\uac00-\ud7a3A-Za-z0-9\s.,:;!?'"()\[\]\/%+\-–—·•&@#*=<>_~|]/.test(c)).length;
      el.setAttribute('data-ms-k', String(k++)); ko.push({t: t.slice(0, 30), sym});
    }
  }
  return {issues: out, ko};
}"""


def contact_sheet(paths, out, cols=4, width=480):
    from PIL import Image, ImageDraw
    ims = [Image.open(p) for p in paths]
    if not ims:
        return None
    h = int(width * ims[0].height / ims[0].width)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * width + (cols + 1) * 8, rows * (h + 26) + 8), "white")
    d = ImageDraw.Draw(sheet)
    for i, im in enumerate(ims):
        x, y = 8 + (i % cols) * (width + 8), 8 + (i // cols) * (h + 26)
        sheet.paste(im.convert("RGB").resize((width, h)), (x, y + 18))
        d.text((x, y + 2), str(i + 1), fill="black")
    sheet.save(out)
    return out


def shots(deck, out_dir=None, pdf=False, wait_ms=700, ko_sample=False):
    from playwright.sync_api import sync_playwright
    deck = os.path.abspath(deck)
    out_dir = os.path.abspath(out_dir or os.path.join(os.path.dirname(deck), "shots"))
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):
        if re.fullmatch(r"slide-\d+\.png", f):
            os.remove(os.path.join(out_dir, f))
    fonts = load_fonts()
    want = set()
    meta_p = os.path.join(os.path.dirname(deck), "meta-slide.json")
    if os.path.exists(meta_p):
        m = json.loads(_read(meta_p))
        want = {fonts[m["title_font"]]["family"], fonts[m["body_font"]]["family"]}
    report = {"deck": deck, "slides": [], "shots": [], "fonts_expected": sorted(want)}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.goto(file_url(deck), wait_until="networkidle", timeout=60000)
        pg.evaluate("document.fonts.ready.then(() => true)")
        pg.wait_for_timeout(600)
        if ko_sample:  # 템플릿 검사용 — 예시 글을 비슷한 폭의 한글로 바꿔 한국어 덱처럼 본다
            pg.evaluate(KO_SAMPLE_JS)
            pg.evaluate("document.fonts.ready.then(() => true)")
            pg.wait_for_timeout(500)
        n = pg.evaluate(SLIDE_COUNT_JS)
        cdp = pg.context.new_cdp_session(pg)
        cdp.send("DOM.enable")
        cdp.send("CSS.enable")
        prev = None
        for i in range(n):
            if i:
                pg.keyboard.press("ArrowRight")
                pg.wait_for_timeout(wait_ms)
            pg.evaluate(FINISH_ANIM_JS)
            pg.evaluate("() => window.metaSlideFit && window.metaSlideFit(document)")
            pg.evaluate(HIDE_UI_JS)
            path = os.path.join(out_dir, f"slide-{i + 1:02d}.png")
            png = pg.screenshot(path=path)
            if prev is not None and png == prev:  # 넘기기 잠금(전환 중 키 무시 등)에 걸렸을 수 있어 한 번 더 기다렸다 넘긴다
                pg.wait_for_timeout(1200)
                pg.keyboard.press("ArrowRight")
                pg.wait_for_timeout(wait_ms)
                pg.evaluate(FINISH_ANIM_JS)
                pg.evaluate("() => window.metaSlideFit && window.metaSlideFit(document)")
                pg.evaluate(HIDE_UI_JS)
                png = pg.screenshot(path=path)
            if prev is not None and png == prev:
                os.remove(path)
                report["note"] = f"{i + 1}장에서 화면이 바뀌지 않아 멈춤(내비게이션 확인)"
                break
            prev = png
            report["shots"].append(path)
            chk = pg.evaluate(CHECK_JS)
            used = {}
            if chk["ko"]:
                doc = cdp.send("DOM.getDocument", {"depth": -1})
                ids = cdp.send("DOM.querySelectorAll", {"nodeId": doc["root"]["nodeId"], "selector": "[data-ms-k]"})["nodeIds"]
                sysfont = re.compile(r"(Apple ?SD|Gothic Neo|Malgun|Gulim|Batang|Dotum|Arial Unicode)", re.I)
                fallback = set()
                unchecked = 0
                for nid in ids:
                    try:
                        attrs = cdp.send("DOM.describeNode", {"nodeId": nid})["node"].get("attributes", [])
                        kk = int(attrs[attrs.index("data-ms-k") + 1])
                        fonts_n = cdp.send("CSS.getPlatformFontsForNode", {"nodeId": nid})["fonts"]
                    except Exception:  # 장을 넘기는 사이 사라진 요소 등 — 건너뛰되 센다(조용히 숨기지 않게)
                        unchecked += 1
                        continue
                    sym = chk["ko"][kk]["sym"] if kk < len(chk["ko"]) else 0
                    for f in fonts_n:
                        used[f["familyName"]] = used.get(f["familyName"], 0) + f["glyphCount"]
                        if want and sysfont.search(f["familyName"]) and f["glyphCount"] > sym:
                            fallback.add(f["familyName"])
                fallback = sorted(fallback)
            else:
                fallback, unchecked = [], 0
            fixes = pg.evaluate("() => document.querySelectorAll('[data-ms-fix]').length")
            report["slides"].append({"n": i + 1, "issues": chk["issues"][:8], "fonts_used": used, "fallback_fonts": fallback,
                                     "ms_fixes": fixes, "ko_unchecked": unchecked})
        if pdf:
            from PIL import Image
            ims = [Image.open(s).convert("RGB") for s in report["shots"]]
            if ims:
                pdf_path = os.path.join(out_dir, "deck.pdf")
                ims[0].save(pdf_path, save_all=True, append_images=ims[1:], resolution=144)
                report["pdf"] = pdf_path
        b.close()
    report["sheet"] = contact_sheet(report["shots"], os.path.join(out_dir, "sheet.png"))
    return report


def cmd_shots(argv):
    args = positional(argv)
    if not args:
        raise SystemExit("사용: shots <덱.html> [--out 폴더] [--pdf]")
    r = shots(args[0], opt(argv, "--out"), "--pdf" in argv, ko_sample="--ko-sample" in argv)
    _write(os.path.join(os.path.dirname(r["shots"][0]) if r["shots"] else ".", "report.json"), json.dumps(r, ensure_ascii=False, indent=2))
    if "--json" in argv:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    print(f"캡처 {len(r['shots'])}장 · 한 장 모음 {r['sheet']}" + (f" · PDF {r['pdf']}" if r.get("pdf") else ""))
    if r.get("note"):
        print("주의: " + r["note"])
    bad = 0
    for s in r["slides"]:
        msgs = [f"{x['kind']}「{x['text']}」" for x in s["issues"]]
        if s["fallback_fonts"]:
            msgs.append("한글이 대체 서체로 그려짐: " + ", ".join(s["fallback_fonts"]))
        if s.get("ko_unchecked"):
            msgs.append(f"한글 요소 {s['ko_unchecked']}개는 서체를 재지 못함(다시 shots)")
        if msgs:
            bad += 1
            print(f"  {s['n']:>2}장: " + " · ".join(msgs))
    print("자동 검사: " + ("문제 없음" if not bad else f"{bad}장에 문제") + " — 그래도 sheet.png 를 눈으로 본다(강약·도식·자간)")


# ── 목록·이력 ───────────────────────────────────────────────────


def cmd_templates(argv):
    ts = load_templates()
    if "--json" in argv:
        print(json.dumps({k: {x: v[x] for x in v if x not in ("dir",)} for k, v in ts.items()}, ensure_ascii=False, indent=2))
        return
    for k, t in ts.items():
        tag = "사내" if t["house"] else "MIT"
        print(f"{k:20s} {t.get('scheme', ''):5s} {tag:3s} {t.get('tagline_ko') or t.get('tagline', '')}")
    print(f"\n{len(ts)}종 · house={sum(1 for t in ts.values() if t['house'])} · 레이아웃 색인 {'있음' if os.path.exists(INDEX_PATH) else '없음(build_index.py)'}")


def cmd_layouts(argv):
    args = positional(argv)
    ts = load_templates()
    t = ts.get(args[0] if args else "")
    if not t:
        raise SystemExit("사용: layouts <템플릿>")
    for x in t.get("layouts") or []:
        print(f"{x['i'] + 1:>2}. {x['layout']:10s} 「{x.get('label', '')}」 {x.get('text', '')[:70]}")


def cmd_colors(argv):
    scheme = opt(argv, "--scheme")
    for k, c in load_colors().items():
        if scheme and c["scheme"] != scheme:
            continue
        print(f"{k:34s} {c['scheme']:5s} 주 {c['primary']} 강조 {c['accent']} 바탕 {c['bg']} 글자 {c['fg']} 대비 {contrast(c['fg'], c['bg']):.1f}")


def cmd_ig(argv):
    """인포그래픽: 인자 없으면 계열 목록, 계열이면 그 모양 목록, 템플릿 이름이면 문법 예시."""
    args = positional(argv)
    cat = load_ig()
    fams = ig_families(cat)
    if not args:
        for k, v in sorted(fams.items(), key=lambda kv: -len(kv[1]["names"])):
            print(f"{k:30s} {len(v['names']):>3}종  {v['desc']}")
        bad = [k for k, v in cat.items() if v.get("qa", "ok") != "ok"]
        print(f"\n쓸 수 있는 {len(cat) - len(bad)}종 / 전체 {len(cat)}종(영문 고정 문구 등 {len(bad)}종 제외) · AntV Infographic (MIT) · python3 slide.py ig <계열|템플릿>")
        return
    a = args[0]
    if a in cat:
        warn = f" · ⚠ 영문 고정 문구 {cat[a].get('fixed_latin')}" if cat[a].get("qa") == "fixed_latin" else ""
        print(f"# {a} — {cat[a]['desc']} · 데이터 필드 {cat[a]['field']}{warn}")
        print("# 흐름형 장(헤드라인 아래로 요소가 쌓이는 템플릿)은 아래처럼 블록으로, 절대 위치 장(deck-stage 1920x1080 좌표)은 "
              "style 을 position:absolute; left/top/width/height 로 바꾼다. 헤드라인과 겹치지 않게 shots 로 확인")
        print('<div class="ms-ig" style="width:100%; height:600px; margin-top:28px">')
        print('<script type="text/x-infographic">')
        print(ig_example(a, cat))
        print("</script></div>")
        return
    if a in fams or a in ig_families(cat, usable_only=False):
        for nm in ig_families(cat, usable_only=False)[a]["names"]:
            flag = "" if cat[nm].get("qa", "ok") == "ok" else f"  ⚠ {cat[nm]['qa']}"
            print(f"{nm:60s} {cat[nm]['desc']}{flag}")
        return
    raise SystemExit(f"모르는 계열·템플릿: {a}")


def cmd_fonts(argv):
    for k, f in load_fonts().items():
        print(f"{k:22s} {f['role']:5s} {f['kind']:7s} {f['name']} — {f['desc'][:60]}")


def cmd_record(argv):
    args = positional(argv)
    if not args:
        raise SystemExit("사용: record <덱폴더> [--series 이름] [--title 제목]")
    m = json.loads(_read(os.path.join(args[0], "meta-slide.json")))
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "deck": os.path.abspath(args[0]), "series": opt(argv, "--series"),
           "title": opt(argv, "--title", ""), "template": m["template"], "color": m.get("color"), "title_font": m["title_font"], "body_font": m["body_font"]}
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"이력 기록: {HISTORY_PATH}")


def cmd_history(argv):
    for h in load_history():
        print(f"{h['at'][:16]}  {h.get('series') or '-':14s} {h['template']:20s} {h['title_font']}/{h['body_font']}  {h.get('title', '')}")


def main(argv):
    utf8_console()
    cmds = {"templates": cmd_templates, "layouts": cmd_layouts, "pick": cmd_pick, "new": cmd_new, "outline": cmd_outline,
            "shots": cmd_shots, "fonts": cmd_fonts, "colors": cmd_colors, "ig": cmd_ig, "record": cmd_record, "history": cmd_history}
    if not argv or argv[0].startswith("--") and argv[0] not in ("--help",):  # 인자 없이(옵션만) — 갤러리 띄우기
        import serve
        return serve.main(argv)
    if argv[0] not in cmds:
        print(__doc__)
        return 0 if not argv or argv[0] in ("help", "-h", "--help") else 2
    cmds[argv[0]](argv[1:])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
