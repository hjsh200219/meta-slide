#!/usr/bin/env python3
"""템플릿 색인 data/index.json 을 만든다 — 장(슬라이드)마다 레이아웃 종류(Jev choice)와 포인트 색 수.

  python3 build_index.py            # 전체(이미 있는 항목은 템플릿 파일이 그대로면 건너뜀)
  python3 build_index.py --force    # 전부 다시
  python3 build_index.py neo-grid-bold cheil-dark-point

Jev 로 나가는 것: 템플릿 예시 글(공개 MIT 템플릿·house 자리표시 글)뿐이다. Playwright(python) 필요.
"""
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slide  # noqa: E402
from slide import _write  # noqa: E402

SLIDES_JS = r"""() => {
  const ds = document.querySelector('deck-stage');
  const dk = [...document.querySelectorAll('.deck > section, .deck > .slide')];
  let els = ds ? [...ds.children] : (dk.length ? dk : [...document.querySelectorAll('.slide')].filter(e => !e.parentElement.closest('.slide')));
  if (!els.length) els = [...document.querySelectorAll('section')];
  return els.map((e, i) => ({i, label: (e.getAttribute('data-label') || e.getAttribute('aria-label') || e.className || '').toString().slice(0, 60),
    text: (e.innerText || e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 700)}));
}"""


def file_hash(path):
    return hashlib.sha1(open(path, "rb").read()).hexdigest()[:12]


def slides_of(page, html_path):
    page.goto(slide.file_url(html_path), wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(400)
    return page.evaluate(SLIDES_JS)


def classify(jev, t, slides_):
    q = {}
    for s in slides_:
        q[f"s{s['i']}"] = jev.choice(
            f"슬라이드 덱 「{t['name']}」의 {s['i'] + 1}번째 장이다(전체 {len(slides_)}장). 장 이름표와 글로 보아 이 장의 레이아웃 종류를 하나 고른다. "
            "첫 장은 대개 표지, 마지막 장은 대개 마무리다.",
            slide.LAYOUTS)
    state = {"deck": t["name"], "slides": [{"n": s["i"] + 1, "label": s["label"], "text": s["text"][:500]} for s in slides_]}
    out = []
    for chunk in range(0, len(slides_), 20):  # 한 요청에 질문 20개씩
        part = {k: v for k, v in list(q.items())[chunk:chunk + 20]}
        ans = jev.ask(state, part, timeout_s=120)
        for k in part:
            c, conf = jev.choice_of(ans, k)
            out.append((int(k[1:]), c, round(conf, 3)))
    return {i: (c, conf) for i, c, conf in out}


def main(argv):
    slide.utf8_console()
    force = "--force" in argv
    only = [a for a in argv if not a.startswith("--")]
    templates = slide.load_templates()
    idx = slide.load_index() if not force else {}
    jev = slide.load_jev()
    from playwright.sync_api import sync_playwright
    todo = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        for slug, t in templates.items():
            if only and slug not in only:
                continue
            html = os.path.join(t["dir"], "template.html")
            h = file_hash(html)
            if not force and not only and idx.get(slug, {}).get("hash") == h:
                continue
            todo.append((slug, t, h, slides_of(pg, html)))
        b.close()

    def run(item):
        slug, t, h, ss = item
        try:
            got = classify(jev, t, ss)
        except Exception as e:
            return slug, None, f"{type(e).__name__}: {str(e)[:160]}"
        lay = [{"i": s["i"], "label": s["label"], "layout": got.get(s["i"], (None, 0))[0] or "points",
                "conf": got.get(s["i"], (None, 0))[1], "text": s["text"][:160]} for s in ss]
        pal = t.get("palette") or {}
        accents = sum(1 for v in pal.values() if isinstance(v, str) and v.startswith("#") and len(v) == 7 and slide.saturation(v) > 0.35)
        return slug, {"hash": h, "layouts": lay, "accents": accents, "slide_total": len(ss)}, None

    with ThreadPoolExecutor(max_workers=4) as ex:
        for slug, row, err in ex.map(run, todo):
            if err:
                print(f"  실패 {slug}: {err}", file=sys.stderr)
                continue
            idx[slug] = row
            kinds = sorted({x["layout"] for x in row["layouts"]})
            print(f"  {slug}: {row['slide_total']}장 · 포인트 색 {row['accents']} · {', '.join(kinds)}")
    _write(slide.INDEX_PATH, json.dumps(dict(sorted(idx.items())), ensure_ascii=False, indent=1))
    print(f"색인 {len(idx)}종 → {slide.INDEX_PATH}")


if __name__ == "__main__":
    main(sys.argv[1:])
