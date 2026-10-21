---
name: meta-slide
description: 발표 자료(슬라이드·PPT·덱)를 만들 때, 사내 「전략적 Presentation 기법」 원칙(프리젠터 의도 → 간지로 구도 → 1 slide 1 idea 헤드라인 → 도식화 → 요약, 단색+포인트, 자간, 굴림·바탕 금지)대로 개요를 점검하고, Jev 가 ① 인터넷 MIT 템플릿·사내 키노트 기반 템플릿 중 내용에 맞는 덱 템플릿 → ② 장마다 인포그래픽으로 보여 줄지 → ③ AntV 인포그래픽 265종 중 맞는 것 → ④ 색 체계 161종(또는 템플릿 원래 색) → ⑤ 한글 제목·본문 서체를 고르고, 덱을 만들어 장마다 캡처·자동 검사(넘침·대체 서체·자간)까지 한다. 트리거 — "/meta-slide", "meta-slide", "메타 슬라이드", "슬라이드 만들어", "발표 자료 만들어", "PPT 만들어", "피피티", "덱 만들어", "deck", "slides", "프레젠테이션", "발표 슬라이드", "키노트", "제안서 슬라이드", "강의 자료", "슬라이드 템플릿", "발표 템플릿", "인포그래픽".
---

# meta-slide

**원칙 정본 `data/principles.md`** — 사내 Keynote PDF 「전략적 Presentation 기법」(Slack EDB `F0CAQJP6PLK`, 373쪽) 요약, 쪽 번호 포함. 장 구성은 모두 이 원칙을 기준으로 한다. 작업 전에 읽는다.

| 무엇 | 어디 | 출처·라이선스 |
|---|---|---|
| 덱 템플릿 | `data/templates/<slug>/`(인터넷) · `data/house/<slug>/`(사내 키노트 기반 `cheil-dark-point`) | 저장소마다 MIT — 각 폴더 `LICENSE`·`template.json` 의 `source`, 묶음 출처 `data/templates/SOURCE.md` |
| 장 레이아웃 색인 | `data/index.json` | `build_index.py`(장마다 Jev 로 레이아웃 16종 표시) |
| 인포그래픽 | `data/infographics/`(런타임 `infographic.min.js` · 목록 `catalog.json` 276종 중 쓸 수 있는 265종 · 예시 `examples.json`) | AntV Infographic 0.2.20 (MIT) · 아이콘 Tabler 3.49.0 (MIT) |
| 색 체계 | `data/colors.json` 161종(밝은 125 · 어두운 36) | ui-ux-pro-max-skill colors.csv (MIT) |
| 한글 서체 | `data/fonts.json` 17종 | Google Fonts·Pretendard (OFL) — 굴림·바탕 없음 |

```bash
S="<이 스킬 폴더>/slide.py"     # 스킬을 부르면 표시되는 Base directory
python3 $S templates | layouts <템플릿> | colors [--scheme dark] | fonts | ig [계열|인포그래픽]   # 목록
python3 $S outline 개요.md                                   # 원칙 점검 + 헤드라인만 읽기
python3 $S pick 개요.md                                      # Jev ①④⑤ — 템플릿(후보 3)·색 체계·서체
python3 $S new 덱폴더 --template <id> --color <id|template> --title-font <id> --body-font <id> [--brand '#hex']
python3 $S outline 개요.md --template <id> --jev            # Jev ②③ + 장마다 한 메시지·헤드라인·레이아웃 → 템플릿 몇 번 장
python3 $S ig <인포그래픽>                                    # 그 인포그래픽의 문법 예시(장에 붙일 조각)
python3 $S shots 덱폴더/deck.html --pdf                      # 장마다 캡처 + 자동 검사 + sheet.png + deck.pdf
python3 $S record 덱폴더 --series <이름> --title <제목>       # 이력 — 다음 같은 시리즈는 같은 템플릿·색·서체
```

⛔ `pick`·`outline --jev` 는 개요 글을 Jev(api.typesafe.ai)로 보낸다. 미공개 실적·개인정보·고객사 기밀이 든 개요는 `--no-jev`(기본값: 어두운 `cheil-dark-point`, `--scheme light` → `blue-professional`) 로 고르거나 사용자에게 `--template`·`--color` 를 받는다. `data/principles.md` 원문도 Jev 로 보내지 않는다. 인포그래픽은 장 안에서 로컬로만 렌더한다 — `meta-slide-ig.js` 가 AntV 기본 동작(아이콘을 weavefox.cn 검색 API 로, 서체를 antgroup CDN 에서)을 막고 로컬 Tabler 아이콘·덱 서체를 쓴다.

## 순서 — 원칙의 「일하는 순서」 + 다섯 가지 고르기

0. **원칙**: `data/principles.md` 를 읽는다.
1. **프리젠터 의도 파악**(p75). 누가 발표하고 누가 듣는지, 이 문서의 핵심 한 문장이 무엇인지 정한다. 요청에서 알 수 없고 추정하면 위험할 때만 묻는다. 발표자 성향(썰 풀기형·꽉 찬 자료형·도식 선호·글자 크기 취향)을 알면 반영한다(p23).
2. **시놉(개요) 먼저**(p85~86) — PPT 에 바로 올리며 생각하지 않는다. `개요.md`:
   ```markdown
   ---
   title: 발표 제목
   subtitle: 부제
   presenter: 발표자 · 의도(이 문서의 핵심 한 문장)
   audience: 듣는 사람
   date: 2026-10-21
   ---
   # 간지(장) 제목
   ## 헤드라인 — 이 장의 결론을 문장으로
   - 근거(3~5개, 한 줄에 한 생각)
   > 발표자 노트(말로 할 것)
   ## 마지막 요약 장 {summary}
   ```
   헤드라인은 이름표(「현황」「배경」)가 아니라 결론 문장. 장 태그 `{statement}` `{diagram}` `{compare}` `{number}` `{chart}` `{quote}` `{timeline}` `{summary}` … 로 레이아웃을 직접 정할 수 있다(`slide.py` 의 `LAYOUTS`).
3. **`outline` 점검**을 고칠 것이 없을 때까지 — 간지(8장 이상이면 2개 이상) · 헤드라인 길이 · 근거 5개 이하 · 표→그래프 · 끝 요약. 「헤드라인만 읽기」가 그대로 이야기가 되는지 직접 읽는다(p94).
4. **`pick` — ① 템플릿 → ④ 색 체계 → ⑤ 서체**. 템플릿이 200개를 넘으면 묶음 예선 → 결승으로 고른다. 색·서체는 고른 템플릿(분위기·영문 서체 성격·바탕 밝기)을 보여 주고 고른다. 색은 템플릿과 같은 밝기의 체계 중 글자 대비 7 이상·주색 대비 3 이상만 후보이고, 「템플릿 원래 색 유지」도 후보다. 우선순위: 사용자 지정(`--template`·`--color`·`--title-font`·`--body-font`) > 같은 시리즈 이력(`--series`) > Jev > 기본값. 사용자에게 고른 템플릿·후보 2개·색·서체를 한 줄씩 보여 주고, 다른 지시가 없으면 그대로 진행한다.
5. **`new`** — 템플릿 폴더를 복사해 `deck.html` 을 만든다.
   - 색(④): `--color <id>` 면 HTML·CSS 의 색 값을 역할대로 바꾼다 — 무채색은 바탕↔글자 사이 위치를 지켜 체계의 바탕·글자 색 사이로, 유채색은 많이 쓰인 순서대로 주색·강조·보조로(원래 명도는 지킨다). `--brand '#hex'` 는 포인트 색 하나만 브랜드 색(12% 톤 다운, p171)으로.
   - 서체(⑤): 모든 `font-family`·`--*font*` 선언(HTML 과 복사된 CSS 파일)의 템플릿 웹 서체 뒤·시스템 서체 앞에 한글 서체를 끼운다(제목 계열 → 제목 서체, 나머지 → 본문 서체). 영문은 템플릿 서체, 한글은 고른 서체로 그려진다.
   - `meta-slide.css`(단어 중간 줄바꿈 금지 `keep-all` · deck-stage 시스템 서체 덮기 · 인포그래픽 색 `--ms-ig-1..4`) · `meta-slide.js`(한글 글자의 넓은 자간 0.06em 초과 → 0.01em, 좁은 줄간격 → 1.18 — p187 · 40px 이상 한글 제목이 장 밖으로 넘치거나 아래 글을 밀어내면 글자 크기를 최소 55~70%까지 줄임 `data-ms-fit`) · `infographics/` 런타임을 붙인다.
6. **`outline --template <id> --jev` — ② ③ + 장 점검**. 장마다 Jev 가 한 장 한 메시지인가·헤드라인이 메시지인가(noul), 레이아웃(그 템플릿에 있는 종류만, choice)을 판정하고, **② 인포그래픽으로 보여 주면 더 잘 전달되는가**(noul, 0.6 이상 — 표지·간지·한 문장·인용·요약·마무리·숫자 장은 제외: 원칙상 글이 주인공) → **③ 계열**(순서·깔때기·피라미드·순환·타임라인·로드맵·격자·2자 비교·SWOT·사분면·트리·마인드맵·흐름도·그래프 …) → **그 계열 안 모양**(덱 스타일을 같이 보여 주고 choice)을 고른다. 출력: 템플릿 몇 번 장을 복제할지 + 인포그래픽을 넣을 장과 이름.
7. **덱 채우기**(Claude 가 직접 편집) — 대응표대로 템플릿 장(`<section>`·`.slide`)을 복제·배치하고 글을 바꾼 뒤 쓰지 않는 장은 지운다.
   - **지킨다**: 서체 선언·`:root` 변수 구조·격자·장 클래스·장식·내비게이션 런타임. 템플릿에 없는 레이아웃이 필요하면 같은 서체·색·장식 어휘로 새로 그린다.
   - **바꾼다**: 제목·본문·숫자·이름·날짜·장 번호·자리표시 이미지(같은 크기로). 템플릿 예시 문구(영어·중국어)가 남지 않게 한다.
   - **인포그래픽 장**: `python3 $S ig <이름>` 이 주는 조각(`<div class="ms-ig">` + `<script type="text/x-infographic">`)을 헤드라인 아래에 넣고 데이터만 그 장 내용으로 바꾼다. 흐름형 장은 블록(`width:100%; height:560~620px`), 1920x1080 좌표 장(deck-stage)은 `position:absolute` 로 헤드라인과 겹치지 않게. `theme` 블록은 쓰지 않는다(덱 색·서체가 자동). 아이콘은 영어 낱말(`rocket`·`chart line`)로 — 로컬 Tabler 에서 찾는다. 인포그래픽 안의 글도 한 줄 짧게.
   - **원칙 적용**: 장마다 헤드라인 하나 · 강조는 핵심 단어만(굵게 또는 포인트 색, 한 장에 한두 곳) · 두 줄이면 핵심 줄만 크게, 세 줄이면 점층(가장 중요한 것 맨 아래, p190~191) · 핵심이 둘 이상이면 도식 · 표는 그래프로, 안 되면 선 최소화 · 간지는 같은 레이아웃에 색만 바꿔 반복(p173) · 허전한 장은 아이콘·실루엣·뒤에 깐 그림(p198).
   - **한국어 줄바꿈은 직접 지정**(2026-10-21 사용자 「세 / 미나로」 지적): 제목·카드 문구가 두 줄이면 의미 단위에서 `<br>`. `keep-all` 은 단어 중간 끊김만 막는다.
   - 실제 화면 캡처를 넣으면 개인 이름·사진·약국명 같은 개인정보는 가린다.
8. **`shots --pdf`** — Playwright 로 장마다 1920x1080 캡처, `sheet.png`, `deck.pdf`, `report.json`. 캡처 전에 등장 애니메이션을 끝 상태로 돌린다. 자동 검사: 화면 밖·잘린 글(「01」「26」처럼 두세 글자 장식은 제외), **한글이 고른 서체가 아닌 시스템 서체로 그려진 장**(CDP 실측). 통과해도 `sheet.png` 를 직접 보고 강약·도식·자간·인포그래픽 겹침·남은 예시 문구를 확인한다. 고치면 다시 `shots`.
9. **보고 첫 줄**: 템플릿 id·이름 · 색 체계 · 제목/본문 서체 · 장 수 · 인포그래픽 장 수, 각 고른 경로(user·series·jev·default)와 확신도. 그다음 `deck.html`·`deck.pdf`·`sheet.png` 경로. 끝나면 `record`.

공유가 필요하면 `deck.pdf` 를 보내거나, 덱 폴더를 Artifact 로 게시한다(`deck.html` + `files` 에 같은 폴더의 js·css·자산).

## 템플릿·자원 추가

- 인터넷 템플릿: `template.html` + `template.json`(slug·name·tagline·mood·occasion·tone·formality·density·scheme·palette·typography·best_for·avoid_for·source) + 원본 `LICENSE` 를 `data/templates/<접두어>-<slug>/` 에 넣고 `python3 build_index.py <slug>` → `python3 qa_templates.py <slug>`(한글 견본 글로 캡처해 대체 서체·넘침이 0 인지). 16:9·5장 이상·키보드 → 로 넘어감·원격 스크립트 없음·중국어 서체 없음. AGPL 등 사내 재배포가 곤란한 라이선스는 넣지 않는다(op7418/guizang-ppt-skill AGPL-3.0 제외).
- 사내 템플릿: 실제 키노트·PPT 에서 바탕·간지·강조 방식만 옮겨 `data/house/<slug>/` 에 자리표시 글로(실제 내용·고객명 금지), `"source"`·`"house": true`.
- 인포그래픽: AntV 판을 올리면 `build_infographics.py <antv package> <tabler package>` → `qa_infographics.py`(한글 예시로 전부 렌더해 영문 고정 문구·실패 표시).
- 색 체계: `build_colors.py <colors.csv>`.
