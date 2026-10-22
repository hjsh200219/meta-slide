#!/usr/bin/env python3
"""직접 그리는 도식(diagram-design 참조)을 data/diagrams/ 에 만든다.

  python3 build_diagrams.py <diagram-design 저장소 폴더>
    # git clone https://github.com/cathrynlavery/diagram-design 한 폴더(루트)

결과: types/*.md(유형별 배치 문법) · examples/*.html(영문·hex 색 원본 예시 — 참고용) · verify/*.py(수치 검증) · LICENSE · SOURCE.md · catalog.json
AntV 런타임에 없는 계열만 가져온다(사분면·순환·피라미드·깔때기·타임라인은 AntV 에 있다). 장에는 Claude 가 이 문법을 읽고
덱 색·서체·20px 하한으로 인라인 SVG 를 새로 그린다 — 예시를 그대로 붙이지 않는다(SKILL.md 7단계 「직접 그린 도식」).
"""
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "diagrams")

sys.path.insert(0, HERE)
from slide import _read, _write  # noqa: E402

# 계열 id → (한글 설명 · 유형 문서 · 문서 안 시작/끝 제목 · 대표 예시 · 수치 검증 · 장 하나의 상한)
DIAGRAMS = {
    "venn": ("벤 다이어그램 — 2~3개 집합의 겹침·공통 영역(「A 와 B 가 만나는 곳」)", "type-venn.md", None, None,
             "example-venn.html", None, "집합 3개까지"),
    "waterfall": ("폭포 차트 — 시작값에서 항목별 증감을 거쳐 끝값으로(예산·매출·인원 증감 다리)", "type-waterfall.md", None, None,
                  "example-waterfall.html", "verify-waterfall.py", "막대 8개까지(소계 1개)"),
    "line": ("꺾은선 그래프 — 시간에 따른 연속 추이", "type-line.md", None, "## Variants",
             "example-line.html", None, "계열 3개까지"),
    "slopegraph": ("기울기 그래프 — 두 시점 사이 항목별 변화(전후 비교)", "type-line.md", "### Slopegraph", "### Ridgeline",
                   "example-slopegraph.html", "verify-slopegraph.py", "항목 4~6개(3개 이하는 문장·막대가 낫다)"),
    "radar": ("레이더 차트 — 여러 대상을 3~5개 기준 점수로 비교", "type-radar.md", None, None,
              "example-radar.html", None, "축 5개 · 대상 3개까지"),
    "treemap": ("트리맵 — 전체 중 비중(면적 크기가 이야기)", "type-treemap.md", None, "## Variants",
                "example-treemap.html", "verify-treemap.py", "칸 8개까지"),
    "gantt": ("간트 차트 — 작업·단계의 기간 일정", "type-gantt.md", None, None,
              "example-gantt.html", None, "행 6개까지"),
    "layers": ("레이어 스택 — 아래에서 위로 쌓인 계층(기술 스택·통제 층·추상 수준)", "type-layers.md", None, None,
               "example-layers.html", None, "층 5개까지"),
    "fishbone": ("피시본 — 한 결과의 원인을 범주별로(근본 원인 분석)", "type-fishbone.md", None, None,
                 "example-fishbone.html", None, "범주 4개 · 범주마다 원인 2개까지"),
    "heatmap": ("히트맵 — 행×열 교차 값의 세기(색 농도가 값)", "type-heatmap.md", None, None,
                "example-heatmap.html", None, "6행 × 6열까지"),
}


# 원본 검증은 문서 크기(8px 값 라벨·hex 강조색)에 맞춰져 있다 — 장표 규약(20px 이상·덱 변수 색)에서도 같은 판정이 되게 두 곳만 고친다
PATCHES = {
    "verify-waterfall.py": [
        ('ACCENT_STROKES = {"#bf4520", "#f08a59"}',
         'ACCENT_STROKES = {"#bf4520", "#f08a59", "var(--ms-ig-1)"}  # meta-slide: 덱 주색 변수도 강조'),
        ("        if abs(x - (bar.x + bar.w / 2)) > GEOMETRY_TOLERANCE or abs(y - expected_y) > GEOMETRY_TOLERANCE:",
         "        # meta-slide: 감소 막대 아래 값은 글자 크기만큼 내려 쓴다(장표 글자 20px 이상 — 원본 +12 는 8px 글자 기준)\n"
         "        fs = parse_number(attrs.get(\"font-size\", \"\")) or 8\n"
         "        below = bar.role == \"delta\" and bar.value < 0 and abs(y - (bar.bottom + 8 + fs)) <= GEOMETRY_TOLERANCE\n"
         "        if abs(x - (bar.x + bar.w / 2)) > GEOMETRY_TOLERANCE or (abs(y - expected_y) > GEOMETRY_TOLERANCE and not below):"),
    ],
}


def aspect_of(html):
    m = re.search(r'<svg[^>]*viewBox="-?[\d.]+ -?[\d.]+ ([\d.]+) ([\d.]+)"', html)  # 원점이 음수인 예시도 있다(fishbone -40 0 …)
    return round(float(m[1]) / float(m[2]), 2) if m else None


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    src = os.path.abspath(argv[0])
    skill = os.path.join(src, "skills", "diagram-design")
    if not os.path.isdir(os.path.join(skill, "references")):
        raise SystemExit(f"diagram-design 저장소 루트가 아닙니다: {src}")
    commit = subprocess.run(["git", "-C", src, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or "미확인"
    version = re.search(r'version:\s*"([^"]+)"', _read(os.path.join(skill, "SKILL.md")))
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    for d in ("types", "examples", "verify"):
        os.makedirs(os.path.join(OUT, d))
    cat = {}
    for key, (desc, doc, start, stop, ex, ver, limit) in DIAGRAMS.items():
        shutil.copy(os.path.join(skill, "references", doc), os.path.join(OUT, "types", doc))
        html = _read(os.path.join(skill, "assets", ex))
        shutil.copy(os.path.join(skill, "assets", ex), os.path.join(OUT, "examples", ex))
        if ver:
            code = _read(os.path.join(src, "scripts", ver))
            for old, new in PATCHES.get(ver, []):
                if code.count(old) != 1:
                    raise SystemExit(f"{ver}: 패치 자리를 못 찾음(원본이 바뀜) — {old[:60]}")
                code = code.replace(old, new)
            _write(os.path.join(OUT, "verify", ver), code)
        cat[key] = {"family": key, "desc": desc, "doc": doc, "start": start, "stop": stop, "example": ex,
                    "verify": ver, "limit": limit, "aspect": aspect_of(html)}
    shutil.copy(os.path.join(src, "LICENSE"), os.path.join(OUT, "LICENSE"))
    _write(os.path.join(OUT, "catalog.json"), json.dumps(cat, ensure_ascii=False, indent=1) + "\n")
    _write(os.path.join(OUT, "SOURCE.md"), (
        "# 출처\n\n"
        f"- https://github.com/cathrynlavery/diagram-design · 커밋 `{commit}` · 스킬 판 {version[1] if version else '미확인'} · MIT(`LICENSE`)\n"
        "- `types/` 유형 문서 · `examples/` 대표 예시(밝은 판) — 원문 그대로. `verify/` 수치 검증 — 원문에서 `verify-waterfall.py` 두 곳만 고쳤다"
        "(강조색에 덱 변수 `var(--ms-ig-1)` 추가 · 감소 막대 아래 값 라벨 위치를 글자 크기에 맞춤, `# meta-slide:` 주석). `build_diagrams.py` 의 `PATCHES`.\n"
        "- 원본의 브랜드 설정·온보딩·프로필 절차는 가져오지 않았다. 덱 색·서체가 우선이다.\n"
        f"- 다시 만들기: `python3 build_diagrams.py <diagram-design 저장소>`\n"))
    print(f"data/diagrams/: 계열 {len(cat)} · 문서 {len(set(v['doc'] for v in cat.values()))} · 예시 {len(cat)} · 검증 "
          f"{sum(1 for v in cat.values() if v['verify'])} · 커밋 {commit[:7]}")


if __name__ == "__main__":
    main(sys.argv[1:])
