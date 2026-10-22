#!/usr/bin/env python3
"""meta-slide 자원 갤러리를 로컬에서 띄운다 — `python3 slide.py`(인자 없음)가 부른다. 표준 라이브러리만 쓴다.

  python3 serve.py [--port 8766] [--no-open] [--out <폴더>] [--local]
  --local  SSH 로 붙은 사용자 PC 브라우저용 — 이 Mac 의 Tailscale 주소에도 띄운다(같은 Tailscale 계정 기기만 · 2시간 쉬면 꺼짐).
           마지막 줄 LOCAL_URL= 이 PC 에서 열 주소, LOCAL_BROWSER= 가 짝지은 PC 크롬(SKILL.md 대로 Claude 가 연다).
탭 다섯: 시놉시스 전략(장 구성·규칙·같은 주제 예시) · 템플릿(썸네일·장 구성·색·서체·원본/한글 서체 미리보기) · 인포그래픽(한글 예시로 실제 렌더) · 색 체계 · 한글 서체.
갤러리 페이지는 매번 ~/.cache/meta-slide/gallery/ 에 다시 만든다(데이터를 고친 뒤에도 바로 보이게). 경로:
  /            갤러리            /data/...      repo 의 data/ 그대로(템플릿 원본·썸네일·인포그래픽 런타임)
  /preview/<id>/deck.html        그 템플릿에 `slide.py new`(기본 한글 서체)를 적용한 덱 — 처음 열 때 만든다
Ctrl-C 로 끈다. 밖으로 나가는 요청은 웹 서체 CSS(fonts.googleapis.com·cdn.jsdelivr.net)와 템플릿 원본이 부르는 자원뿐이다.
"""
import contextlib
import http.server
import io
import json
import os
import sys
import threading
import urllib.parse
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import localnet  # noqa: E402
import slide  # noqa: E402
from slide import _write  # noqa: E402

OUT = os.path.expanduser("~/.cache/meta-slide")
PORT = 8766  # meta-motion 갤러리가 8765
BHT_SOURCE = "zarazhangrui/beautiful-html-templates"  # 이 묶음 34종은 template.json 에 source 가 없다(data/templates/SOURCE.md)
_build_lock = threading.Lock()


def _source(t):
    if t.get("house"):
        return "사내 키노트 기반"
    s = t.get("source")
    return s.get("repo", "") if isinstance(s, dict) else (s or BHT_SOURCE)


def _list(v):
    """template.json 의 목록 칸은 출처마다 목록·문자열·없음이 섞여 있다 — 늘 문자열 목록으로."""
    if not v:
        return []
    return [str(x) for x in v] if isinstance(v, (list, tuple)) else [str(v)]


def gallery_data():
    """갤러리에 넣을 자료(JSON 으로 직렬화 가능한 것만)."""
    ts = []
    thumbs = os.path.join(slide.DATA, "thumbs")
    for slug, t in slide.load_templates().items():
        kinds = {}
        for l in t.get("layouts") or []:
            kinds[l["layout"]] = kinds.get(l["layout"], 0) + 1
        ts.append({
            "slug": slug, "name": t.get("name", slug), "tagline": t.get("tagline", ""),
            "mood": _list(t.get("mood")), "scheme": t.get("scheme") or "", "house": bool(t.get("house")),
            "best_for": _list(t.get("best_for")), "avoid_for": _list(t.get("avoid_for")),
            "palette": {k: v for k, v in (t.get("palette") or {}).items() if isinstance(v, str) and v.startswith("#")},
            "typography": t.get("typography") if isinstance(t.get("typography"), dict) else {}, "source": _source(t),
            "slides": t.get("slide_total") or t.get("slide_count") or 0, "kinds": kinds,
            "path": os.path.relpath(os.path.join(t["dir"], "template.html"), slide.DATA),
            "thumb": os.path.exists(os.path.join(thumbs, slug + ".jpg")),
        })
    cat = slide.load_ig()
    igs = []
    for fam, v in slide.ig_families(cat).items():
        for n in v["names"]:
            igs.append({"name": n, "family": fam, "desc": cat[n].get("desc", ""), "src": slide.ig_example(n, cat)})
    colors = [dict(id=k, **v) for k, v in slide.load_colors().items()]
    fonts = [dict(id=k, **v) for k, v in slide.load_fonts().items()]
    layouts = {k: v.split(" — ")[0] for k, v in slide.LAYOUTS.items()}
    syns = [{k: s.get(k) for k in slide.SYN_FIELDS + ("inspired_by",)} for s in slide.load_synopses().values()]
    return {"templates": ts, "igs": igs, "colors": colors, "fonts": fonts, "layouts": layouts, "synopses": syns}


def build(out_dir):
    """갤러리 index.html 을 만든다. 경로를 돌려준다."""
    d = gallery_data()
    links = "\n".join(f'<link rel="stylesheet" href="{f["css"]}">' for f in d["fonts"] if f.get("css"))
    html = PAGE.replace("/*DATA*/", json.dumps(d, ensure_ascii=False).replace("</", "<\\/")).replace("<!--FONTS-->", links)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "index.html")
    _write(path, html)
    return path


def preview(slug, root):
    """템플릿에 기본 한글 서체를 넣은 덱을 root/preview/<slug>/ 에 만든다(이미 있으면 그대로)."""
    dest = os.path.join(root, "preview", slug)
    if not os.path.exists(os.path.join(dest, "deck.html")):
        with _build_lock, contextlib.redirect_stdout(io.StringIO()):
            slide.cmd_new([dest, "--template", slug, "--force"])
    return dest


class Handler(http.server.SimpleHTTPRequestHandler):
    root = OUT
    gate = None  # localnet.Gate — 들어온 기기·Host 머리글 검사

    def log_message(self, *a):  # 요청마다 찍히는 줄로 터미널을 덮지 않는다
        pass

    def _ok(self):
        if self.gate is None or self.gate.allowed(self.client_address[0], self.headers.get("Host")):
            return True
        self.send_error(403, "Invalid local request")
        return False

    def do_GET(self):  # noqa: N802
        if self._ok():
            super().do_GET()

    def do_HEAD(self):  # noqa: N802
        if self._ok():
            super().do_HEAD()

    def translate_path(self, path):
        p = urllib.parse.unquote(urllib.parse.urlsplit(path).path)
        parts = [x for x in p.split("/") if x and x not in (".", "..")]
        if parts[:1] == ["data"]:
            return os.path.join(slide.DATA, *parts[1:])
        if parts[:1] == ["preview"] and len(parts) >= 2:
            if parts[1] not in slide.load_templates():
                return os.path.join(self.root, "_none")
            return os.path.join(preview(parts[1], self.root), *parts[2:]) if len(parts) > 2 else os.path.join(preview(parts[1], self.root), "deck.html")
        return os.path.join(self.root, "gallery", *parts)


def main(argv):
    slide.utf8_console()
    opt = {"port": str(PORT), "out": OUT}
    it = iter(argv)
    for a in it:
        if a in ("--no-open", "--local"):
            opt[a[2:]] = True
        elif a.startswith("--"):
            opt[a[2:]] = next(it, "")
    root = os.path.expanduser(opt["out"])
    build(os.path.join(root, "gallery"))
    port = int(opt["port"])
    if opt.get("local"):
        return serve_local(root, port)
    gate = localnet.Gate(port)
    cls = type("H", (Handler,), {"root": root, "gate": gate})
    try:
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), cls)
    except OSError:  # 포트를 쓰고 있으면 빈 포트로
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cls)
    gate.port = srv.server_address[1]
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"meta-slide 갤러리 → {url}  (끄기 Ctrl-C · 사용법은 slide.py help)", flush=True)
    if not opt.get("no-open"):
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def serve_local(root, port):
    """127.0.0.1 + Tailscale IP 두 입구. 포트는 고정이어야 PC 가 늘 같은 주소로 연다 — 옛 갤러리가 잡고 있으면 끄고 연다."""
    status = localnet.tailscale_status()
    why = localnet.refuse_reason(status)
    if why:
        print(f"--local 입구를 열지 않았습니다 — {why}", file=sys.stderr)
        return 1
    ip, dns, hosts, peers = localnet.allowlist(status)
    pidfile = os.path.join(root, "serve.pid")
    port = localnet.pick_port(port, pidfile)
    if port is None:
        print("포트를 열 수 없습니다 — --port 로 바꿔 주세요", file=sys.stderr)
        return 1
    localnet.claim(pidfile, port)
    gate = localnet.Gate(port, hosts, peers)
    cls = type("H", (Handler,), {"root": root, "gate": gate})
    servers = [http.server.ThreadingHTTPServer(("127.0.0.1", port), cls), http.server.ThreadingHTTPServer((ip, port), cls)]
    localnet.idle_watch(gate, servers)
    threading.Thread(target=servers[1].serve_forever, daemon=True).start()
    url = f"http://{dns or ip}:{port}/"
    print(f"내 PC 에서 열기: {localnet.osc8(url)}  (같은 Tailscale 계정 기기만 · 2시간 쉬면 꺼짐)", flush=True)
    dev = localnet.pc_browser()
    if dev:
        print(f"LOCAL_BROWSER={dev}", flush=True)
    print(f"LOCAL_URL={url}", flush=True)
    try:
        servers[0].serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


PAGE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>meta-slide 갤러리</title>
<!--FONTS-->
<style>
:root{--bg:#f6f6f4;--panel:#fff;--ink:#16181d;--sub:#5d626c;--line:#e3e3df;--chip:#efefec;--point:#e0322b;
  --ms-ig-1:#2b59c3;--ms-ig-2:#e0322b;--ms-ig-3:#1f9d74;--ms-ig-4:#f2a81d;--ms-body:'Pretendard';color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#121316;--panel:#1b1d21;--ink:#ecedef;--sub:#a1a6b0;--line:#2c2f35;--chip:#25282d;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 'Pretendard',system-ui,sans-serif;word-break:keep-all}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line)}
.bar{max-width:1440px;margin:0 auto;padding:14px 20px 0;display:flex;align-items:baseline;gap:16px;flex-wrap:wrap}
h1{font-size:19px;margin:0;font-weight:800;letter-spacing:-.01em}
h1 b{color:var(--point)}
.lead{color:var(--sub);font-size:13px}
nav{max-width:1440px;margin:0 auto;padding:8px 20px 0;display:flex;gap:4px;overflow-x:auto}
nav a{padding:9px 14px;border-radius:8px 8px 0 0;color:var(--sub);text-decoration:none;font-weight:600;white-space:nowrap;border-bottom:2px solid transparent}
nav a.on{color:var(--ink);border-bottom-color:var(--point)}
nav a small{font-weight:500;color:var(--sub);margin-left:4px}
main{max-width:1440px;margin:0 auto;padding:16px 20px 60px}
.tools{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
.tools input,.tools select{font:inherit;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--panel);color:var(--ink)}
.tools input{flex:1 1 220px;min-width:0}
.count{color:var(--sub);font-size:13px;margin-left:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;cursor:pointer;display:flex;flex-direction:column;text-align:left;font:inherit;color:inherit;padding:0}
.card:hover{border-color:var(--sub)}
.card:focus-visible{outline:2px solid var(--point);outline-offset:2px}
.thumb{aspect-ratio:16/9;background:var(--chip) center/cover no-repeat;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:center;color:var(--sub);font-size:12px}
.body{padding:10px 12px 12px;display:flex;flex-direction:column;gap:4px}
.name{font-weight:700;font-size:14px;line-height:1.35}
.meta{color:var(--sub);font-size:12px}
.chips{display:flex;flex-wrap:wrap;gap:4px;margin-top:2px}
.chip{background:var(--chip);border-radius:999px;padding:1px 8px;font-size:11.5px;color:var(--sub)}
.chip.house{background:var(--point);color:#fff}
.sw{display:flex;gap:3px;margin-top:4px}
.sw i{width:16px;height:16px;border-radius:4px;border:1px solid rgba(0,0,0,.12)}
.igcard{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.igview{height:230px;background:#fff;border-bottom:1px solid var(--line)}
.igview.ms-ig[data-ms-ig=error]::after{content:'렌더 실패';display:block;padding:20px;color:#b00}
.color{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.cprev{padding:14px;min-height:120px;display:flex;flex-direction:column;gap:8px}
.cprev .t{font-weight:800;font-size:17px}
.cprev .btns{display:flex;gap:6px}
.cprev .btns span{padding:3px 10px;border-radius:6px;font-size:12px;font-weight:600}
.font{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.fsample{font-size:30px;line-height:1.25;margin:6px 0 4px;font-weight:700;letter-spacing:-.01em}
.fbody{font-size:15px;color:var(--sub)}
dialog{width:min(1100px,calc(100vw - 32px));max-height:calc(100dvh - 32px);border:1px solid var(--line);border-radius:14px;padding:0;background:var(--panel);color:var(--ink)}
dialog::backdrop{background:rgba(0,0,0,.55)}
.dlg{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:0}
.dlg img{width:100%;display:block;aspect-ratio:16/9;object-fit:cover;background:var(--chip)}
.dlg.syn{grid-template-columns:1fr}
.beats{display:flex;flex-wrap:wrap;gap:4px;align-items:center;font-size:12px;color:var(--sub)}
.beats .req{color:var(--ink);font-weight:600}
.beatlist{margin:0;padding-left:20px;display:flex;flex-direction:column;gap:3px}
pre.ex{white-space:pre-wrap;margin:0;font:12.5px/1.55 ui-monospace,Menlo,monospace;background:var(--chip);padding:12px;border-radius:8px}
.dinfo{padding:18px 20px;display:flex;flex-direction:column;gap:10px;overflow:auto}
.dinfo h2{margin:0;font-size:20px}
.dinfo .row b{display:block;font-size:12px;color:var(--sub);font-weight:600;margin-bottom:2px}
.acts{display:flex;gap:8px;flex-wrap:wrap;padding:12px 20px 16px;border-top:1px solid var(--line);grid-column:1/-1}
.acts a,.acts button{font:inherit;font-weight:600;padding:8px 14px;border-radius:8px;border:1px solid var(--line);background:var(--chip);color:var(--ink);text-decoration:none;cursor:pointer}
.acts a.primary{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.acts .x{margin-left:auto}
code{font:12.5px ui-monospace,Menlo,monospace;background:var(--chip);padding:2px 6px;border-radius:5px;word-break:break-all}
.empty{color:var(--sub);padding:40px 0;text-align:center}
@media (max-width:720px){.dlg{grid-template-columns:1fr}.bar,nav,main{padding-left:16px;padding-right:16px}.grid{grid-template-columns:repeat(auto-fill,minmax(220px,1fr))}}
</style>
</head>
<body>
<header>
  <div class="bar"><h1>meta-<b>slide</b> 갤러리</h1><span class="lead">Jev 가 고르는 것 — 시놉시스 전략 · 템플릿 · 인포그래픽 · 색 체계 · 한글 서체</span></div>
  <nav id="tabs"></nav>
</header>
<main id="main"></main>
<dialog id="dlg"></dialog>
<script>
const D = /*DATA*/;
const TABS = [['synopses','시놉시스',D.synopses.length],['templates','템플릿',D.templates.length],['ig','인포그래픽',D.igs.length],['colors','색 체계',D.colors.length],['fonts','한글 서체',D.fonts.length]];
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const SCHEME = {light:'밝은 바탕', dark:'어두운 바탕', mixed:'섞임'};
const $ = s => document.querySelector(s);
let state = {};
try { state = JSON.parse(sessionStorage.getItem('ms-gallery') || '{}'); } catch (e) {}
const save = () => { try { sessionStorage.setItem('ms-gallery', JSON.stringify(state)); } catch (e) {} };

function tab() { return (location.hash.slice(1) || 'templates').split('/')[0]; }
function renderTabs() {
  $('#tabs').innerHTML = TABS.map(([k, l, n]) => `<a href="#${k}" class="${tab() === k ? 'on' : ''}">${l}<small>${n}</small></a>`).join('');
}
function tools(html) { return `<div class="tools">${html}<span class="count" id="count"></span></div>`; }
function opts(list, cur, all) { return `<option value="">${all}</option>` + list.map(([v, l]) => `<option value="${esc(v)}"${v === cur ? ' selected' : ''}>${esc(l)}</option>`).join(''); }
function match(q, ...fields) { q = (q || '').trim().toLowerCase(); return !q || fields.join(' ').toLowerCase().includes(q); }

function viewTemplates() {
  const srcs = [...new Set(D.templates.map(t => t.source))].sort().map(s => [s, s + ' (' + D.templates.filter(t => t.source === s).length + ')']);
  const kinds = Object.entries(D.layouts).map(([k, l]) => [k, l + ' 장이 있는']);
  $('#main').innerHTML = tools(`<input id="q" type="search" placeholder="이름·분위기·설명 검색" value="${esc(state.q || '')}">
    <select id="sc">${opts(Object.entries(SCHEME), state.sc, '바탕 전체')}</select>
    <select id="src">${opts(srcs, state.src, '출처 전체')}</select>
    <select id="kd">${opts(kinds, state.kd, '장 구성 전체')}</select>`) + '<div class="grid" id="grid"></div>';
  const draw = () => {
    const list = D.templates.filter(t => match(state.q, t.slug, t.name, t.tagline, t.mood.join(' '), t.best_for.join(' '))
      && (!state.sc || t.scheme === state.sc) && (!state.src || t.source === state.src) && (!state.kd || t.kinds[state.kd]));
    $('#count').textContent = `${list.length} / ${D.templates.length}종`;
    $('#grid').innerHTML = list.length ? list.map(t => `<button class="card" data-slug="${esc(t.slug)}">
      <div class="thumb" ${t.thumb ? `style="background-image:url('data/thumbs/${encodeURIComponent(t.slug)}.jpg')"` : ''}>${t.thumb ? '' : '썸네일 없음'}</div>
      <div class="body"><div class="name">${esc(t.name)}</div>
      <div class="meta">${esc(SCHEME[t.scheme] || t.scheme)} · ${t.slides}장 · ${esc(t.source)}</div>
      <div class="chips">${t.house ? '<span class="chip house">사내</span>' : ''}${t.mood.slice(0, 3).map(m => `<span class="chip">${esc(m)}</span>`).join('')}</div>
      <div class="sw">${Object.values(t.palette).slice(0, 7).map(c => `<i style="background:${esc(c)}"></i>`).join('')}</div></div></button>`).join('')
      : '<p class="empty">맞는 템플릿이 없습니다.</p>';
  };
  ['q', 'sc', 'src', 'kd'].forEach(id => $('#' + id).addEventListener('input', e => { state[id] = e.target.value; save(); draw(); }));
  $('#grid').addEventListener('click', e => { const c = e.target.closest('.card'); if (c) openTemplate(c.dataset.slug); });
  draw();
}

function openTemplate(slug) {
  const t = D.templates.find(x => x.slug === slug); if (!t) return;
  const kinds = Object.entries(t.kinds).map(([k, n]) => `${D.layouts[k] || k} ${n}`).join(' · ') || '색인 없음';
  const typo = Object.entries(t.typography).filter(([k, v]) => typeof v === 'string').map(([k, v]) => `${k}: ${v}`).join(' · ');
  const cmd = `python3 slide.py new 덱폴더 --template ${t.slug}`;
  $('#dlg').innerHTML = `<div class="dlg">
    <img src="${t.thumb ? 'data/thumbs/' + encodeURIComponent(t.slug) + '.jpg' : ''}" alt="${esc(t.name)} 표지">
    <div class="dinfo"><h2>${esc(t.name)}</h2><div class="meta">${esc(t.tagline)}</div>
      <div class="row"><b>id</b><code>${esc(t.slug)}</code></div>
      <div class="row"><b>장 구성 (${t.slides}장)</b>${esc(kinds)}</div>
      ${t.best_for.length ? `<div class="row"><b>어울리는 자리</b>${esc(t.best_for.join(', '))}</div>` : ''}
      ${t.avoid_for.length ? `<div class="row"><b>피할 자리</b>${esc(t.avoid_for.join(', '))}</div>` : ''}
      ${typo ? `<div class="row"><b>원본 서체</b>${esc(typo)}</div>` : ''}
      <div class="row"><b>색</b><div class="sw">${Object.entries(t.palette).map(([k, c]) => `<i title="${esc(k)} ${esc(c)}" style="background:${esc(c)}"></i>`).join('')}</div></div>
      <div class="row"><b>출처</b>${esc(t.source)}${t.house ? '' : ' · MIT'}</div>
      <div class="row"><b>만들기</b><code>${esc(cmd)}</code></div>
    </div>
    <div class="acts"><a class="primary" href="preview/${encodeURIComponent(t.slug)}/deck.html" target="_blank" rel="noopener">한글 서체 적용해 열기</a>
      <a href="data/${t.path.split('/').map(encodeURIComponent).join('/')}" target="_blank" rel="noopener">원본 열기</a>
      <button type="button" id="cp">명령 복사</button><button type="button" class="x" id="cl">닫기</button></div></div>`;
  $('#cl').onclick = () => $('#dlg').close();
  $('#cp').onclick = () => { navigator.clipboard && navigator.clipboard.writeText(cmd).then(() => { $('#cp').textContent = '복사됨'; }); };
  $('#dlg').showModal();
}

function viewSynopses() {
  const fams = [...new Set(D.synopses.map(s => s.family))].map(f => [f, f + ' (' + D.synopses.filter(s => s.family === f).length + ')']);
  $('#main').innerHTML = tools(`<input id="sq" type="search" placeholder="이름·쓰임·연설가 검색 (예: 투자, 강연, Jobs)" value="${esc(state.sq || '')}">
    <select id="sf">${opts(fams, state.sf, '계열 전체')}</select>`) + '<div class="grid" id="grid"></div>';
  const draw = () => {
    const list = D.synopses.filter(s => match(state.sq, s.slug, s.name, s.name_ko, s.tagline_ko, s.best_for_ko, s.inspired_by || '', s.source_ko)
      && (!state.sf || s.family === state.sf));
    $('#count').textContent = `${list.length} / ${D.synopses.length}종 · 원고에 맞는 전략은 Jev 가 고른다`;
    $('#grid').innerHTML = list.map(s => `<button class="card" data-slug="${esc(s.slug)}"><div class="body">
      <div class="chips"><span class="chip">${esc(s.family)}</span></div>
      <div class="name">${esc(s.name_ko)}</div>
      ${s.inspired_by ? `<div class="meta">본보기: ${esc(s.inspired_by)}</div>` : ''}
      <div class="meta">${esc(s.tagline_ko)}</div>
      <div class="beats">${s.beats.map(b => `<span class="${b.required ? 'req' : ''}">${esc(b.name)}</span>`).join('<span>→</span>')}</div>
      </div></button>`).join('') || '<p class="empty">맞는 전략이 없습니다.</p>';
  };
  ['sq', 'sf'].forEach(id => $('#' + id).addEventListener('input', e => { state[id] = e.target.value; save(); draw(); }));
  $('#grid').addEventListener('click', e => { const c = e.target.closest('.card'); if (c) openSynopsis(c.dataset.slug); });
  draw();
}

function openSynopsis(slug) {
  const s = D.synopses.find(x => x.slug === slug); if (!s) return;
  const k = s.knobs || {}, h = s.template_hints || {};
  const cmd = `python3 slide.py synopsis ${s.slug}`;
  $('#dlg').innerHTML = `<div class="dlg syn"><div class="dinfo"><h2>${esc(s.name_ko)}</h2><div class="meta">${esc(s.tagline_ko)}</div>
    ${s.inspired_by ? `<div class="row"><b>본보기</b>${esc(s.inspired_by)}</div>` : ''}
    <div class="row"><b>어울리는 자리</b>${esc(s.best_for_ko)}</div>
    <div class="row"><b>피할 자리</b>${esc(s.avoid_for_ko)}</div>
    <div class="row"><b>헤드라인 문체</b>${esc(s.headline_style)}</div>
    <div class="row"><b>장 구성 (굵게 = 꼭 있어야 할 단계)</b><ol class="beatlist">${s.beats.map(b => `<li>${b.required ? '<strong>' : ''}${esc(b.name)}${b.required ? '</strong>' : ''}
      <span class="meta">· ${esc(D.layouts[b.layout] || b.layout)}${b.count ? ' · ' + esc(b.count) : ''} — ${esc(b.goal)}</span></li>`).join('')}</ol></div>
    <div class="row"><b>장 규칙</b><ol class="beatlist">${(s.rules_ko || []).map(r => `<li>${esc(r)}</li>`).join('')}</ol></div>
    <div class="row"><b>점검 기준</b>헤드라인 ${k.max_headline_chars}자 · 근거 ${k.max_bullets}개 · 본문 ${k.max_body_chars}자 · 요약 ${({front: '앞', end: '끝', none: '없음'})[k.summary] || k.summary}</div>
    <div class="row"><b>어울리는 덱</b>${esc(h.style_ko || '')}</div>
    <div class="row"><b>출처</b>${esc(s.source_ko)}</div>
    <div class="row"><b>예시 개요 — 모든 전략이 같은 주제(약국 재고 자동 발주)</b><pre class="ex">${esc(s.example)}</pre></div>
    <div class="row"><b>보기</b><code>${esc(cmd)}</code></div></div>
    <div class="acts"><button type="button" id="cp">명령 복사</button><button type="button" class="x" id="cl">닫기</button></div></div>`;
  $('#cl').onclick = () => $('#dlg').close();
  $('#cp').onclick = () => { navigator.clipboard && navigator.clipboard.writeText(cmd).then(() => { $('#cp').textContent = '복사됨'; }); };
  $('#dlg').showModal();
}

let io = null;
function viewIg() {
  const fams = [...new Set(D.igs.map(g => g.family))].map(f => [f, f + ' (' + D.igs.filter(g => g.family === f).length + ')']);
  $('#main').innerHTML = tools(`<input id="iq" type="search" placeholder="이름·설명 검색 (예: 타임라인, swot, 깔때기)" value="${esc(state.iq || '')}">
    <select id="if">${opts(fams, state.if, '계열 전체')}</select>`) + '<div class="grid" id="grid"></div>';
  const draw = () => {
    const list = D.igs.filter(g => match(state.iq, g.name, g.desc) && (!state.if || g.family === state.if));
    $('#count').textContent = `${list.length} / ${D.igs.length}종 · 한글 예시로 실제 렌더`;
    $('#grid').innerHTML = list.map((g, i) => `<div class="igcard"><div class="igview lazy" data-i="${D.igs.indexOf(g)}"></div>
      <div class="body"><div class="name">${esc(g.name)}</div><div class="meta">${esc(g.desc)}</div>
      <div><code>python3 slide.py ig ${esc(g.name)}</code></div></div></div>`).join('') || '<p class="empty">맞는 인포그래픽이 없습니다.</p>';
    if (io) io.disconnect();
    io = new IntersectionObserver(es => es.forEach(e => {
      if (!e.isIntersecting) return;
      const el = e.target; io.unobserve(el); el.classList.remove('lazy'); el.classList.add('ms-ig');
      const s = document.createElement('script'); s.type = 'text/x-infographic'; s.textContent = D.igs[+el.dataset.i].src; el.appendChild(s);
      if (window.metaSlideRenderInfographics) window.metaSlideRenderInfographics(el.parentNode);
    }), {rootMargin: '300px'});
    document.querySelectorAll('.igview.lazy').forEach(el => io.observe(el));
  };
  ['iq', 'if'].forEach(id => $('#' + id).addEventListener('input', e => { state[id] = e.target.value; save(); draw(); }));
  draw();
}

function viewColors() {
  $('#main').innerHTML = tools(`<input id="cq" type="search" placeholder="이름·설명 검색" value="${esc(state.cq || '')}">
    <select id="cs">${opts([['light', '밝은 바탕'], ['dark', '어두운 바탕']], state.cs, '바탕 전체')}</select>`) + '<div class="grid" id="grid"></div>';
  const draw = () => {
    const list = D.colors.filter(c => match(state.cq, c.id, c.name, c.notes) && (!state.cs || c.scheme === state.cs));
    $('#count').textContent = `${list.length} / ${D.colors.length}종`;
    $('#grid').innerHTML = list.map(c => `<div class="color"><div class="cprev" style="background:${esc(c.bg)};color:${esc(c.fg)}">
      <div class="t">한 장에 한 생각</div><div style="color:${esc(c.muted_fg || c.fg)};font-size:13px">강약으로 말하고 포인트는 하나만</div>
      <div class="btns"><span style="background:${esc(c.primary)};color:${esc(c.on_primary || '#fff')}">주색</span>
      <span style="background:${esc(c.secondary)};color:${esc(c.on_secondary || '#fff')}">보조</span>
      <span style="background:${esc(c.accent)};color:${esc(c.on_accent || '#fff')}">강조</span></div></div>
      <div class="body"><div class="name">${esc(c.name)}</div><div class="meta">${esc(c.notes || '')}</div><div><code>--color ${esc(c.id)}</code></div></div></div>`).join('') || '<p class="empty">맞는 색 체계가 없습니다.</p>';
  };
  ['cq', 'cs'].forEach(id => $('#' + id).addEventListener('input', e => { state[id] = e.target.value; save(); draw(); }));
  draw();
}

function viewFonts() {
  const ROLE = {title: '제목 전용', body: '본문', both: '제목·본문'};
  $('#main').innerHTML = tools('<span class="lead">모두 무료(SIL OFL) · 굴림·바탕은 원칙상 넣지 않았습니다</span>') + '<div class="grid" id="grid"></div>';
  $('#count').textContent = `${D.fonts.length}종`;
  $('#grid').innerHTML = D.fonts.map(f => `<div class="font"><div class="meta">${esc(f.kind)} · ${esc(ROLE[f.role] || f.role)} · ${esc(f.weights || '')}</div>
    <div class="fsample" style="font-family:'${esc(f.family)}'">한 장에 한 생각</div>
    <div class="fbody" style="font-family:'${esc(f.family)}'">강약으로 말한다. 2026년 매출 182억, 전년보다 35% 늘었다.</div>
    <div class="body" style="padding:10px 0 0"><div class="name">${esc(f.name)}</div><div class="meta">${esc(f.desc)}</div>
    <div><code>--title-font ${esc(f.id)}</code></div></div></div>`).join('');
}

function route() {
  renderTabs();
  ({synopses: viewSynopses, templates: viewTemplates, ig: viewIg, colors: viewColors, fonts: viewFonts}[tab()] || viewTemplates)();
  window.scrollTo(0, 0);
}
addEventListener('hashchange', route);
route();
</script>
<script src="data/infographics/infographic.min.js"></script>
<script src="data/infographics/icons.js"></script>
<script src="data/infographics/meta-slide-ig.js"></script>
</body>
</html>
"""

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
