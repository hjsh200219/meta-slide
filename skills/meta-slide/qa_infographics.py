#!/usr/bin/env python3
"""인포그래픽 276종을 한글 예시 데이터로 렌더해 catalog.json 에 품질 표시를 붙인다.

  python3 qa_infographics.py [--thumbs]
- ok: 렌더 성공 · 그림 크기 0 아님
- fixed_latin: 데이터에 없는 영문 낱말이 그림에 박혀 나옴(예: Pros/Cons) — 한국어 덱에서는 피한다
- error: 렌더 예외
outline --jev 는 ok 이고 fixed_latin 없는 것만 후보로 쓴다. Jev 호출 없음(로컬 렌더만).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slide  # noqa: E402
from slide import _read, _write  # noqa: E402

IG = slide.IG_DIR


def main(argv):
    from playwright.sync_api import sync_playwright
    cat = slide.load_ig()
    page_html = os.path.join(IG, "_qa.html")
    open(page_html, "w").write('<!doctype html><meta charset="utf-8"><style>:root{--ms-body:"Pretendard";--ms-ig-1:#2563EB;--ms-ig-2:#EA580C;--ms-ig-3:#64748B;--ms-ig-4:#334155}'
                               'body{margin:0}.ms-ig{width:1600px;height:700px}</style>'
                               '<script src="infographic.min.js"></script><script src="icons.js"></script>'
                               '<div class="ms-ig" id="box"></div><script src="meta-slide-ig.js"></script>')
    thumbs = "--thumbs" in argv
    tdir = os.path.join(IG, "thumbs")
    if thumbs:
        os.makedirs(tdir, exist_ok=True)
    stats = {"ok": 0, "fixed_latin": 0, "error": 0, "empty": 0}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1600, "height": 700})
        pg.goto("file://" + page_html)
        for name in cat:
            src = slide.ig_example(name, cat)
            data_words = set(re.findall(r"[A-Za-z]{3,}", src.split("\n", 1)[1]))
            res = pg.evaluate("""(src) => new Promise(done => {
              const box = document.getElementById('box'); box.replaceChildren();
              const s = document.createElement('script'); s.type = 'text/x-infographic'; s.textContent = src; box.appendChild(s);
              window.metaSlideRenderInfographics();
              setTimeout(() => {
                const svg = box.querySelector('svg'); const r = svg ? svg.getBoundingClientRect() : {width: 0, height: 0};
                done({state: box.getAttribute('data-ms-ig'), w: r.width, h: r.height, text: svg ? svg.textContent : ''});
              }, 350);
            })""", src)
            latin = sorted(set(re.findall(r"[A-Za-z]{3,}", res["text"])) - data_words)
            v = cat[name]
            v.pop("qa", None)
            if res["state"] != "ok":
                v["qa"] = "error"
            elif res["w"] < 10 or res["h"] < 10 or not re.search(r"[가-힣]", res["text"]):
                v["qa"] = "empty"
            elif latin:
                v["qa"] = "fixed_latin"
                v["fixed_latin"] = latin[:6]
            else:
                v["qa"] = "ok"
                v.pop("fixed_latin", None)
            stats[v["qa"]] += 1
            if thumbs and v["qa"] == "ok":
                pg.screenshot(path=os.path.join(tdir, name + ".jpg"), type="jpeg", quality=60)
        b.close()
    os.remove(page_html)
    _write(os.path.join(IG, "catalog.json"), json.dumps(cat, ensure_ascii=False, indent=1))
    print(" · ".join(f"{k} {v}" for k, v in stats.items()))


if __name__ == "__main__":
    main(sys.argv[1:])
