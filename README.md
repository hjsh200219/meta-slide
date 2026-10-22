# meta-slide

발표 자료를 사내 「전략적 Presentation 기법」 원칙대로 만드는 Claude Code 플러그인입니다. 개요(시놉)만 쓰면 Jev 가 내용에 맞는 **템플릿 → 인포그래픽 여부 → 인포그래픽 → 색 체계 → 한글 서체**를 고르고, 덱을 만든 뒤 장마다 캡처해 자동 검사합니다.

```bash
python3 skills/meta-slide/slide.py      # 인자 없이 → 템플릿·인포그래픽·색·서체 갤러리를 로컬 브라우저로 연다
```

> 비공개 repo · 사내용입니다. 원칙 요약(`data/principles.md`)은 사내 자료라 밖으로 보내지 않습니다.

## 목차

- [설치](#설치)
- [처음 한 번 — Jev 키 저장](#처음-한-번--jev-키-저장)
- [빠른 시작](#빠른-시작)
- [로컬 갤러리](#로컬-갤러리)
- [명령 모음](#명령-모음)
- [Windows 에서 쓰기](#windows-에서-쓰기)
- [외부 전송](#외부-전송)
- [출처·라이선스](#출처라이선스)
- [시험·자료 다시 만들기](#시험자료-다시-만들기)

## 설치

```bash
claude plugin marketplace add hjsh200219/meta-slide
claude plugin install meta-slide@meta-slide
```

| 필요한 것 | 어디에 | 없으면 |
|---|---|---|
| Python 3.9 이상(표준 라이브러리) | 전부 | 동작 안 함 |
| 이 repo 협업자(collaborator) 권한 · GitHub 로그인된 git | 설치 | `git ls-remote https://github.com/hjsh200219/meta-slide.git` 로 확인 |
| Jev(TypeSafe) API 키 | `pick`·`outline --jev`(Jev 가 고르기) | `--no-jev` 로 기본값만 — [키 저장](#처음-한-번--jev-키-저장) |
| Playwright(python) + Chromium · Pillow | `shots`(캡처·검사·PDF)·QA 스크립트 | `python3 -m pip install --user playwright pillow` → `python3 -m playwright install chromium` |
| Tailscale | `--local`(SSH 로 붙은 내 PC 에서 갤러리 보기) | `--local` 만 안 됨 |

- 업데이트: `claude plugin update meta-slide@meta-slide` → 떠 있는 세션은 `/reload-plugins`
- 덱은 웹 서체 CSS 를 인터넷에서 불러옵니다(fonts.googleapis.com · cdn.jsdelivr.net).

## 처음 한 번 — Jev 키 저장

Claude Code 에서 `/meta-slide:setup`, 또는 터미널에서:

```bash
python3 skills/meta-slide/setup.py            # 키 입력(화면에 안 보임) → Jev 1회 확인 → 저장
python3 skills/meta-slide/setup.py --check    # 어디서 읽는지만(값은 안 찍음)
python3 skills/meta-slide/setup.py --force    # 새 키로 바꾸기 · --forget 지우기
```

- 저장 위치: macOS 키체인(서비스 `typesafe-jev`) · Windows 자격 증명 관리자(`typesafe-jev/JEV_API_KEY`) · 그 밖 `~/.config/typesafe-jev/key`(0600).
- 읽는 순서: 환경변수 `JEV_API_KEY` → 위 저장소 → `~/workspace/.env`.
- **meta-motion 과 같은 저장소**라 한 번 저장하면 두 플러그인 모두 씁니다. meta-slide 는 Jev 키만 씁니다(Fish Audio 키는 meta-motion 내레이션용이라 여기서는 묻지 않습니다).
- 키는 채팅에 붙여 넣지 마세요. Claude 가 실행하면 OS 입력 창이 뜹니다. SSH 로 붙어 있으면 창이 원격 화면에 뜨므로 그 SSH 터미널에서 직접 실행하세요.
- 키 발급: https://typesafe.ai (사내는 관리자에게 받습니다).

## 빠른 시작

| 하고 싶은 일 | 이렇게 |
|---|---|
| 템플릿·인포그래픽 둘러보기 | `python3 skills/meta-slide/slide.py` (또는 `/meta-slide` 를 인자 없이) |
| 발표 자료 만들기 | 「신사업 보고 슬라이드 만들어줘」 — 개요 점검 → 다섯 가지 고르기 → 덱 → 캡처 검사 |
| SSH 로 붙어 있는데 내 PC 에서 보기 | `/meta-slide --local` |
| 키 없이 만들기 | 「…슬라이드, Jev 없이」 → `--no-jev` 기본값(어두운 `broadside`, 밝은 바탕은 `blue-professional`) |

| 고르는 것 | 후보 | 어떻게 |
|---|---|---|
| ① 덱 템플릿 | 230종 — 인터넷 MIT | Jev choice — 많으면 묶음 예선 → 결승 |
| ② 인포그래픽으로 보여 줄지 | 장마다 | Jev noul 0.6 이상 · 표지·간지·한 문장·요약은 제외 |
| ③ 인포그래픽 | AntV Infographic 265종(276종 중 한글 렌더 검사 통과분) + 직접 그린 도식 10계열(AntV 에 없는 벤·폭포·꺾은선·기울기·레이더·트리맵·간트·레이어·피시본·히트맵) | Jev choice — 계열 → 모양. 직접 그린 도식은 Claude 가 `diagram` 규약대로 SVG 로 그린다 |
| ④ 색 체계 | 161종 + 템플릿 원래 색 | Jev choice — 템플릿과 같은 바탕 밝기, 대비 기준 통과분만 |
| ⑤ 한글 서체 | 17종(제목·본문) | Jev choice — 템플릿 영문 서체 성격에 맞춰 |

원칙 정본은 `skills/meta-slide/data/principles.md`(사내 Keynote PDF 373쪽 요약, 쪽 번호 포함)입니다. 프리젠터 의도 파악 → 간지로 전체 구도 → 1 slide 1 idea → 핵심이 둘 이상이면 도식화 → 마지막에 요약, 단색 + 포인트, 흑백 먼저, 자간, 굴림·바탕 금지, 표는 그래프로.

## 로컬 갤러리

- `http://127.0.0.1:8766/` 에 띄우고 브라우저를 엽니다. 끄기 `Ctrl-C` · 다른 포트 `--port 9000` · 브라우저 안 열기 `--no-open`.
- 탭 넷: **템플릿 230**(표지 썸네일 · 바탕·출처·장 구성으로 거르기 · 누르면 장 구성·색·원본 서체·만들기 명령, 「한글 서체 적용해 열기」·「원본 열기」) · **인포그래픽 265**(한글 예시로 실제 렌더) · **색 체계 161** · **한글 서체 17**.
- 실행할 때마다 `~/.cache/meta-slide/gallery/` 에 새로 만듭니다. 「한글 서체 적용해 열기」는 처음 누를 때 `~/.cache/meta-slide/preview/<id>/` 를 만듭니다.
- **`--local`**: 원격 컴퓨터에 SSH 로 붙어 쓰는 경우, 그 컴퓨터의 Tailscale 주소(`http://<컴퓨터>.<tailnet>.ts.net:8766/`)에도 띄워 내 PC 브라우저에서 엽니다.
  - 들어올 수 있는 것은 **같은 Tailscale 계정의 기기**(내 PC·폰)뿐입니다. 같은 tailnet 의 다른 사람 기기는 403 입니다.
  - 2시간 동안 요청이 없으면 스스로 꺼집니다. 포트를 다른 프로그램이 쓰고 있으면 다음 포트로 옮깁니다.
  - 마지막 줄 `LOCAL_URL=` 이 열 주소입니다. Claude Code 에서는 Claude 가 내 PC 크롬(claude-in-chrome)에서 열어 줍니다.

## 명령 모음

`S=skills/meta-slide/slide.py` 기준입니다. 전체 사용법은 `python3 $S help`.

| 명령 | 하는 일 |
|---|---|
| `python3 $S [--local]` | 로컬 갤러리 |
| `outline 개요.md` | 원칙 점검(간지·한 장 한 메시지·글 양·요약) + 헤드라인만 읽기 |
| `pick 개요.md [--no-jev]` | ① ④ ⑤ — 템플릿(후보 3)·색 체계·서체 |
| `new 덱/ --template <id> --color <id\|template> --title-font <id> --body-font <id>` | 덱 만들기(한글 서체·색·인포그래픽 런타임 넣기) |
| `outline 개요.md --template <id> --jev` | ② ③ + 장마다 한 메시지·헤드라인·레이아웃 |
| `ig <인포그래픽>` | 장에 붙일 인포그래픽 조각 |
| `diagram [계열]` | AntV 에 없는 계열의 장표 규약(20px 이상·덱 색·서체)·배치 문법·수치 선언 규칙 |
| `shots 덱/deck.html --pdf` | 장마다 캡처 · 넘침·잘림·대체 서체·인포그래픽 글자 크기·겹침·수치 도식 합계/척도/면적 검사 · `sheet.png` · `deck.pdf` |
| `record 덱/ --series <이름>` · `history` | 이력(같은 시리즈는 같은 템플릿·색·서체) |
| `templates` · `layouts <id>` · `colors` · `fonts` | 목록 |

## Windows 에서 쓰기

- 명령은 같고 `python3` 대신 `python`(또는 `py`)을 씁니다. 예: `python skills\meta-slide\slide.py`.
- 키는 Windows 자격 증명 관리자에 저장합니다(SSH 로 붙은 세션처럼 자격 증명 관리자를 못 쓰면 `%APPDATA%\typesafe-jev\key`).
- 경로·한글 파일 이름·콘솔 출력(UTF-8)·`file://` 주소는 OS 에 맞춰 처리합니다. Windows 11 · Python 3.12 에서 시험 22건이 통과했습니다(2026-10-21).
- `--local` 은 Windows 용 Tailscale(`C:\Program Files\Tailscale\tailscale.exe`)이 있으면 같게 동작합니다.

## 외부 전송

- Jev(api.typesafe.ai)로 나가는 것: `pick`·`outline --jev` 의 개요 글, `build_index.py` 의 템플릿 예시 글, `setup.py` 의 키 확인용 짧은 문장. 원칙 문서 원문은 보내지 않습니다. 개요에 사내 수치가 있어도 Jev 를 씁니다(같은 내용이 Claude 로도 가므로). `--no-jev` 는 키가 없을 때나 Jev 없이 하라고 할 때만.
- 인포그래픽은 로컬에서 렌더합니다. AntV 기본 동작(아이콘을 weavefox.cn 검색 API 로, 서체를 antgroup CDN 에서)은 `meta-slide-ig.js` 가 막습니다.
- 덱·갤러리는 웹 서체 CSS(fonts.googleapis.com · cdn.jsdelivr.net)를 불러옵니다.

## 출처·라이선스

| 자원 | 출처 | 라이선스 |
|---|---|---|
| 덱 템플릿 230종 | codesstar/next-slide 57 · lewislulu/html-ppt-skill 50 · zarazhangrui/beautiful-html-templates 34 · Akxan/ppt-agent-skill 26 · alchaincyf/huashu-design 23 · zarazhangrui/frontend-slides 12 · archlizheng/frontend-slides-editable 11 · vigorX777/ppt-svg-generator 5 · hugohe3/ppt-master 4 · open-slide/open-slide 3 · edu-ai-builders/visual-cognition-slides 2 · FeeiCN/slide-writer 1 · nicobailon/visual-explainer 1 · WayneZhon/KingDee-PPT-Skill 1(벤토 구성만, 브랜드 표기 없음) | MIT |
| 인포그래픽 | antvis/Infographic 0.2.20 | MIT |
| 아이콘 | tabler/tabler-icons 3.49.0 | MIT |
| 도식 배치 문법·수치 검증 10계열 | cathrynlavery/diagram-design `7a12007`(스킬 2.6) — `data/diagrams/SOURCE.md` | MIT |
| 색 체계 | nextlevelbuilder/ui-ux-pro-max-skill colors.csv | MIT |
| 한글 서체 | Google Fonts · Pretendard | SIL OFL |
| 덱 런타임 | beautiful-html-templates `deck-stage.js` | MIT |

- 라이선스 원문: 접두어가 붙은 196종은 템플릿 폴더마다 `LICENSE`·`template.json` 의 `source`(저장소·커밋·원본 경로). 접두어 없는 beautiful-html-templates 34종은 `data/templates/LICENSE`·`SOURCE.md` 한 벌.
- AGPL 등 사내 재배포가 곤란한 라이선스(예: op7418/guizang-ppt-skill)는 넣지 않았습니다.
- 한 장짜리 견본·스타일 사양만 있던 원본(ppt-agent-skill·huashu-design·frontend-slides·ppt-svg-generator·ppt-master·open-slide·KingDee)은 그 색·서체·장식 값을 그대로 써서 장을 늘렸고 `tagline` 에 표시했습니다.
- 실존 브랜드 이름이 붙었던 6종은 중립 이름으로 바꿨습니다(`renamed_from`).

## 시험·자료 다시 만들기

```bash
python3 skills/meta-slide/test_slide.py      # 결정론 부분 28건(Jev·네트워크 없음)
python3 skills/meta-slide/qa_templates.py    # 템플릿 전부를 한글 견본 글로 캡처·검사 → data/qa_templates.json
python3 skills/meta-slide/qa_infographics.py # 인포그래픽 전부 한글 렌더 검사
python3 skills/meta-slide/build_diagrams.py <diagram-design 저장소>  # 직접 그린 도식 참조(data/diagrams/)
python3 skills/meta-slide/build_thumbs.py    # 갤러리 표지 썸네일(data/thumbs/)
```

- `qa_templates.py` 는 예시 글을 한글 견본으로 바꾼 뒤, 장마다 한글이 시스템 서체로 그려졌는지와 글이 장 밖으로 넘치거나 잘렸는지 봅니다. 2026-10-21 전수: 당시 231종 2255장, 대체 서체 0 · 넘침 0(그중 사내 템플릿 1종 14장은 10-22 뺐습니다).
- 템플릿을 넣거나 고친 뒤에는 그 템플릿만 다시 돌립니다: `build_index.py <id>` → `qa_templates.py <id>` → `build_thumbs.py <id>`.
