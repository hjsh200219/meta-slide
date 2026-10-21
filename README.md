# meta-slide

발표 자료를 사내 「전략적 Presentation 기법」 원칙대로 만드는 Claude Code 플러그인입니다. 개요(시놉)만 쓰면 Jev 가 내용에 맞는 **템플릿 → 인포그래픽 여부 → 인포그래픽 → 색 체계 → 한글 서체**를 고르고, 덱을 만든 뒤 장마다 캡처해 자동 검사합니다.

| 고르는 것 | 후보 | 어떻게 |
|---|---|---|
| ① 덱 템플릿 | 인터넷 MIT 템플릿 + 사내 키노트 기반 `cheil-dark-point` (`slide.py templates`) | Jev choice — 많으면 묶음 예선 → 결승 |
| ② 인포그래픽으로 보여 줄지 | 장마다 | Jev noul 0.6 이상 · 표지·간지·한 문장·요약은 제외 |
| ③ 인포그래픽 | AntV Infographic 265종(276종 중 한글 렌더 검사 통과분) | Jev choice — 계열 → 모양 |
| ④ 색 체계 | 161종 + 템플릿 원래 색 | Jev choice — 템플릿과 같은 바탕 밝기, 대비 기준 통과분만 |
| ⑤ 한글 서체 | 17종(제목·본문) | Jev choice — 템플릿 영문 서체 성격에 맞춰 |

## 쓰는 법

```bash
S=skills/meta-slide/slide.py
python3 $S outline 개요.md                         # 원칙 점검 + 헤드라인만 읽기
python3 $S pick 개요.md                            # ① ④ ⑤
python3 $S new deck/ --template <id> --color <id|template> --title-font <id> --body-font <id>
python3 $S outline 개요.md --template <id> --jev  # ② ③ + 장마다 한 메시지·헤드라인·레이아웃
python3 $S ig <인포그래픽>                          # 장에 붙일 인포그래픽 조각
python3 $S shots deck/deck.html --pdf             # 캡처·자동 검사·PDF
```

Claude Code 에서는 `/meta-slide` 또는 「슬라이드 만들어」로 부르면 `skills/meta-slide/SKILL.md` 순서대로 진행합니다.

## 원칙

정본은 `skills/meta-slide/data/principles.md`(사내 Keynote PDF 373쪽 요약, 쪽 번호 포함)입니다. 프리젠터 의도 파악 → 간지로 전체 구도 → 1 slide 1 idea → 핵심이 둘 이상이면 도식화 → 마지막에 요약, 단색 + 포인트, 흑백 먼저, 자간, 굴림·바탕 금지, 표는 그래프로.

## 외부 전송

- Jev(api.typesafe.ai)로 나가는 것: `pick`·`outline --jev` 의 개요 글, `build_index.py` 의 템플릿 예시 글. 원칙 문서 원문은 보내지 않습니다. 미공개 자료는 `--no-jev`.
- 인포그래픽은 로컬에서 렌더합니다. AntV 기본 동작(아이콘을 weavefox.cn 검색 API 로, 서체를 antgroup CDN 에서)은 `meta-slide-ig.js` 가 막습니다.
- 덱은 웹 서체 CSS(fonts.googleapis.com · cdn.jsdelivr.net)를 불러옵니다.

## 출처·라이선스

| 자원 | 출처 | 라이선스 |
|---|---|---|
| 덱 템플릿 230종 | codesstar/next-slide 57 · lewislulu/html-ppt-skill 50 · zarazhangrui/beautiful-html-templates 34 · Akxan/ppt-agent-skill 26 · alchaincyf/huashu-design 23 · zarazhangrui/frontend-slides 12 · archlizheng/frontend-slides-editable 11 · vigorX777/ppt-svg-generator 5 · hugohe3/ppt-master 4 · open-slide/open-slide 3 · edu-ai-builders/visual-cognition-slides 2 · FeeiCN/slide-writer 1 · nicobailon/visual-explainer 1 · WayneZhon/KingDee-PPT-Skill 1(벤토 구성만, 브랜드 표기 없음) — 템플릿마다 `LICENSE`·`template.json` `source`(저장소·커밋·원본 경로) | MIT |
| 사내 템플릿 1종 | `cheil-dark-point` — 사내 Keynote 「전략적 Presentation 기법」의 바탕·간지·강조 방식 | 사내 |
| 인포그래픽 | antvis/Infographic 0.2.20 | MIT |
| 아이콘 | tabler/tabler-icons 3.49.0 | MIT |
| 색 체계 | nextlevelbuilder/ui-ux-pro-max-skill colors.csv | MIT |
| 한글 서체 | Google Fonts · Pretendard | SIL OFL |
| 덱 런타임 | beautiful-html-templates `deck-stage.js` | MIT |

AGPL 등 사내 재배포가 곤란한 라이선스(예: op7418/guizang-ppt-skill)는 넣지 않았습니다. 한 장짜리 견본·스타일 사양만 있던 원본(ppt-agent-skill·huashu-design·frontend-slides·ppt-svg-generator·ppt-master·open-slide·KingDee)은 그 색·서체·장식 값을 그대로 써서 장을 늘렸고 `tagline` 에 표시했습니다. 실존 브랜드 이름이 붙었던 6종은 중립 이름으로 바꿨습니다(`renamed_from`).

## 시험

```bash
python3 skills/meta-slide/test_slide.py     # 결정론 부분(Jev·네트워크 없음)
python3 skills/meta-slide/qa_infographics.py # 인포그래픽 전부 한글 렌더 검사(Playwright)
python3 skills/meta-slide/qa_templates.py    # 템플릿 전부를 한글 견본 글로 바꿔 캡처·검사 → data/qa_templates.json
```

`qa_templates.py` 는 예시 글을 한글 견본으로 바꾼 뒤 장마다 한글이 시스템 서체로 그려졌는지, 글이 장 밖으로 넘치거나 잘렸는지 본다. 템플릿을 넣거나 고친 뒤에는 그 템플릿만 다시 돌린다(`qa_templates.py <id>`).
