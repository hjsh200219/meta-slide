#!/usr/bin/env python3
"""모든 템플릿을 한국어 덱처럼 만들어 검사한다 — new(기본 서체) → shots --ko-sample(예시 글을 한글 견본으로).

  python3 qa_templates.py [slug ...] [--workers 4]
결과: data/qa_templates.json — 템플릿마다 캡처 장 수 · 한글이 시스템 서체로 그려진 장 · 넘침/잘림 장 · 한 장 모음 경로.
Jev 호출 없음. Playwright·Pillow 필요. 한 장 모음은 META_SLIDE_QA_DIR(기본: 시스템 임시 폴더의 meta-slide-qa)에 둔다.
"""
import json
import os
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slide  # noqa: E402
from slide import _read, _write  # noqa: E402

OUT = os.path.join(slide.DATA, "qa_templates.json")
QA_DIR = os.environ.get("META_SLIDE_QA_DIR", os.path.join(tempfile.gettempdir(), "meta-slide-qa"))


def one(slug):
    import contextlib
    import io
    dest = os.path.join(QA_DIR, slug)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            slide.cmd_new([dest, "--template", slug, "--force"])
        r = slide.shots(os.path.join(dest, "deck.html"), os.path.join(dest, "shots"), ko_sample=True)
    except Exception as e:
        return slug, {"error": f"{type(e).__name__}: {str(e)[:200]}"}
    fb = [s["n"] for s in r["slides"] if s["fallback_fonts"]]
    ov = [s["n"] for s in r["slides"] if s["issues"]]
    return slug, {"shots": len(r["shots"]), "fallback_slides": fb, "fallback_fonts": sorted({f for s in r["slides"] for f in s["fallback_fonts"]}),
                  "overflow_slides": ov, "overflow_kinds": sorted({i["kind"] for s in r["slides"] for i in s["issues"]}),
                  "note": r.get("note"), "sheet": os.path.relpath(r["sheet"], QA_DIR) if r.get("sheet") else None,  # META_SLIDE_QA_DIR 기준
                  "detail": [{"n": s["n"], "issues": s["issues"][:3], "fallback": {k: v for k, v in s["fonts_used"].items() if k in s["fallback_fonts"]}}
                             for s in r["slides"] if s["issues"] or s["fallback_fonts"]]}


def main(argv):
    slide.utf8_console()
    workers = int(argv[argv.index("--workers") + 1]) if "--workers" in argv else 4
    only = [a for a in argv if not a.startswith("--") and not a.isdigit()]
    slugs = only or list(slide.load_templates())
    res = json.loads(_read(OUT)) if os.path.exists(OUT) else {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for slug, row in ex.map(one, slugs):
            res[slug] = row
            flag = row.get("error") or (f"대체서체 {row['fallback_slides']} {row['fallback_fonts']}" if row["fallback_slides"] else "") \
                or (f"넘침 {row['overflow_slides']}" if row["overflow_slides"] else "ok")
            print(f"{slug:36s} {row.get('shots', '-'):>3}장  {flag}", flush=True)
    _write(OUT, json.dumps(dict(sorted(res.items())), ensure_ascii=False, indent=1))
    bad = [k for k, v in res.items() if v.get("error") or v.get("fallback_slides")]
    print(f"\n검사 {len(slugs)}종 · 오류·대체 서체 {len(bad)}종 → {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
