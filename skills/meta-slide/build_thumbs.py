#!/usr/bin/env python3
"""템플릿 갤러리 썸네일을 만든다 — 템플릿마다 첫 장(표지)을 원본 그대로 찍어 data/thumbs/<slug>.jpg(480x270).

  python3 build_thumbs.py [slug ...] [--workers 6] [--force]
갤러리(`python3 slide.py` 인자 없이)가 쓴다. 템플릿을 넣거나 고친 뒤 그 템플릿만 다시 돌린다. Playwright·Pillow 필요.
"""
import io
import os
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slide  # noqa: E402

OUT = os.path.join(slide.DATA, "thumbs")
SIZE = (480, 270)


def one(args):
    slug, path = args
    from PIL import Image
    from playwright.sync_api import sync_playwright
    dest = os.path.join(OUT, slug + ".jpg")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1920, "height": 1080})
            pg.goto(slide.file_url(path), wait_until="load")
            pg.evaluate("document.fonts.ready.then(() => true)")
            pg.wait_for_timeout(900)
            pg.evaluate(slide.FINISH_ANIM_JS)
            pg.evaluate(slide.HIDE_UI_JS)
            png = pg.screenshot()
            b.close()
        im = Image.open(io.BytesIO(png)).convert("RGB").resize(SIZE, Image.LANCZOS)
        im.save(dest, "JPEG", quality=78, optimize=True, progressive=True)
        return slug, os.path.getsize(dest)
    except Exception as e:
        return slug, f"{type(e).__name__}: {str(e)[:120]}"


def main(argv):
    slide.utf8_console()
    workers = int(argv[argv.index("--workers") + 1]) if "--workers" in argv else 6
    only = [a for a in argv if not a.startswith("--") and not a.isdigit()]
    os.makedirs(OUT, exist_ok=True)
    ts = slide.load_templates()
    jobs = [(s, os.path.join(t["dir"], "template.html")) for s, t in ts.items()
            if (not only or s in only) and ("--force" in argv or only or not os.path.exists(os.path.join(OUT, s + ".jpg")))]
    bad = 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for slug, r in ex.map(one, jobs):
            if isinstance(r, str):
                bad += 1
                print(f"{slug:36s} 실패 {r}", flush=True)
    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT) if f.endswith(".jpg"))
    print(f"썸네일 {len(jobs) - bad}/{len(jobs)}장 만듦 · 전체 {len(os.listdir(OUT))}장 {total / 1e6:.1f}MB → {OUT}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
