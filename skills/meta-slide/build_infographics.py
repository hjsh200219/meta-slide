#!/usr/bin/env python3
"""인포그래픽 자원을 data/infographics/ 에 만든다.

  python3 build_infographics.py <antv 패키지 폴더> <tabler 패키지 폴더>
    # npm pack @antv/infographic@0.2.20 · npm pack @tabler/icons@3.49.0 을 풀어 둔 package/ 폴더
  python3 build_infographics.py --catalog        # 런타임에서 템플릿 목록을 뽑아 catalog.json (Playwright)

결과: infographic.min.js(AntV, MIT) · icons.js(Tabler outline, MIT — 이름·태그·경로) · LICENSE-* · catalog.json
아이콘을 로컬에서 찾게 해서 AntV 가 weavefox.cn 아이콘 검색 API 로 장의 글을 보내지 않게 한다(meta-slide-ig.js).
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "infographics")

def _read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# 템플릿 이름 앞부분 → 무엇을 보여 주는지(Jev choice 설명). 이름 뒤 낱말은 모양(카드·화살표·3D 등).
FAMILY = [
    ("sequence-interaction", "여러 역할·시스템이 주고받는 순서(스윔레인 상호작용) — sequences(레인) + relations"),
    ("sequence-funnel", "깔때기 — 단계마다 줄어드는 전환·선별 과정"),
    ("sequence-pyramid", "피라미드 — 아래에서 위로 쌓이는 위계·단계"),
    ("sequence-circular", "순환 — 처음으로 되돌아가는 반복 과정·사이클"),
    ("sequence-timeline", "타임라인 — 날짜·연도 순 사건"),
    ("sequence-roadmap", "로드맵 — 앞으로의 단계별 계획"),
    ("sequence-ascending", "오름 계단 — 단계가 올라가며 성장·발전"),
    ("sequence-stairs", "계단 — 단계별 진행"),
    ("sequence-mountain", "산 모양 — 단계별 고비·도전을 넘는 과정"),
    ("sequence-filter", "거름망 — 여러 단계로 걸러지는 과정"),
    ("sequence-cylinders", "원통 3D — 단계·수준"),
    ("sequence-snake", "뱀 모양 단계 — 긴 순서를 굽이쳐 배치"),
    ("sequence-color-snake", "색이 바뀌는 뱀 모양 단계"),
    ("sequence-zigzag", "지그재그 단계"),
    ("sequence-horizontal-zigzag", "가로 지그재그 단계"),
    ("sequence", "순서·단계 — 처음부터 끝까지 차례로 진행하는 과정"),
    ("list-row", "가로 한 줄 목록 — 나란한 요점 3~5개"),
    ("list-column", "세로 목록 — 차례로 읽는 요점·체크리스트"),
    ("list-grid", "격자 카드 — 대등한 항목 4~9개"),
    ("list-sector", "부채꼴 — 하나를 이루는 여러 구성 요소"),
    ("list-waterfall", "폭포형 카드 — 높낮이가 다른 카드 목록"),
    ("list-zigzag", "지그재그 목록"),
    ("list", "목록 — 대등한 요점 나열"),
    ("compare-binary", "두 쪽 비교 — A 안 vs B 안, 전후, 장단점(뿌리 정확히 2개)"),
    ("compare-hierarchy-left-right", "좌우 계층 비교 — 두 대상을 항목별로 맞대어 비교(뿌리 2개)"),
    ("compare-swot", "SWOT — 강점·약점·기회·위협"),
    ("compare-quadrant", "2x2 사분면 매트릭스 — 두 기준으로 나눈 네 영역"),
    ("compare", "비교"),
    ("hierarchy-mindmap", "마인드맵 — 중심 주제에서 뻗는 생각 가지"),
    ("hierarchy-tree", "계층 트리 — 조직도·분류 체계·상하 구조"),
    ("hierarchy-structure", "구조도 — 층으로 쌓인 시스템·아키텍처 구성"),
    ("hierarchy", "계층 구조"),
    ("relation-dagre-flow", "흐름도 — 노드와 화살표로 이은 의존·처리 흐름"),
    ("relation", "관계도 — 요소 사이의 연결"),
    ("chart-line", "선 그래프 — 시간에 따른 추이"),
    ("chart-bar", "가로 막대 그래프 — 항목별 크기 비교"),
    ("chart-column", "세로 막대 그래프 — 항목별 크기 비교"),
    ("chart-pie", "원 그래프 — 전체 중 비중"),
    ("chart-wordcloud", "워드 클라우드 — 키워드 빈도"),
    ("chart", "그래프 — 수치 자료"),
]
FIELD = [("sequence-interaction", "sequences+relations"), ("sequence", "sequences"), ("list", "lists"), ("compare", "compares"),
         ("hierarchy-structure", "items"), ("hierarchy", "root"), ("relation", "nodes+relations"), ("chart", "values")]


def family_of(name):
    for k, v in FAMILY:
        if name == k or name.startswith(k + "-") or name.startswith(k):
            return k, v
    return name.split("-")[0], "인포그래픽"


def field_of(name):
    for k, v in FIELD:
        if name.startswith(k):
            return v
    return "items"


def build_assets(antv_pkg, tabler_pkg):
    os.makedirs(OUT, exist_ok=True)
    shutil.copy2(os.path.join(antv_pkg, "dist", "infographic.min.js"), os.path.join(OUT, "infographic.min.js"))
    antv_ver = json.load(open(os.path.join(antv_pkg, "package.json")))["version"]
    tab_ver = json.load(open(os.path.join(tabler_pkg, "package.json")))["version"]
    lic_src = os.path.join(antv_pkg, "LICENSE")
    if os.path.exists(lic_src):
        shutil.copy2(lic_src, os.path.join(OUT, "LICENSE-antv-infographic"))
    shutil.copy2(os.path.join(tabler_pkg, "LICENSE"), os.path.join(OUT, "LICENSE-tabler-icons"))
    meta = json.load(open(os.path.join(tabler_pkg, "icons.json")))
    nodes = json.load(open(os.path.join(tabler_pkg, "tabler-nodes-outline.json")))
    icons = {}
    for name, ns in nodes.items():
        body = "".join("<%s %s/>" % (tag, " ".join(f'{k}="{v}"' for k, v in attrs.items() if k != "key")) for tag, attrs in ns)
        tags = [t for t in (meta.get(name, {}).get("tags") or []) if isinstance(t, str)][:12]
        icons[name] = [body, " ".join(tags)]
    js = ("/* Tabler Icons %s (MIT, https://tabler.io/icons) — outline 아이콘 이름·태그·경로. meta-slide 가 로컬 아이콘 검색에 쓴다. */\n"
          "window.MS_ICONS=%s;\n") % (tab_ver, json.dumps(icons, ensure_ascii=False, separators=(",", ":")))
    _write(os.path.join(OUT, "icons.js"), js)
    json.dump({"antv_infographic": antv_ver, "tabler_icons": tab_ver, "icons": len(icons)},
              open(os.path.join(OUT, "versions.json"), "w"), indent=1)
    print(f"AntV {antv_ver} · Tabler {tab_ver} 아이콘 {len(icons)}개 → {OUT}")


def build_catalog():
    from playwright.sync_api import sync_playwright
    html = os.path.join(OUT, "_probe.html")
    open(html, "w").write('<!doctype html><meta charset="utf-8"><script src="infographic.min.js"></script>')
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto("file://" + html)
        names = pg.evaluate("() => { const t = AntVInfographic.getTemplates(); return Array.isArray(t) ? t : Object.keys(t); }")
        b.close()
    os.remove(html)
    cat = {}
    for n in sorted(set(names)):
        fam, desc = family_of(n)
        shape = n[len(fam):].strip("-").replace("-", " ")
        cat[n] = {"family": fam, "field": field_of(n), "desc": desc + (f" · 모양: {shape}" if shape else "")}
    _write(os.path.join(OUT, "catalog.json"), json.dumps(cat, ensure_ascii=False, indent=1))
    print(f"인포그래픽 템플릿 {len(cat)}개 → catalog.json")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--catalog"]:
        build_catalog()
    elif len(sys.argv) == 3:
        build_assets(sys.argv[1], sys.argv[2])
        build_catalog()
    else:
        print(__doc__)
