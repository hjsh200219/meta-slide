# 시놉시스 전략 아카이브

원고(스크립트·대본·메모)를 슬라이드 개요로 옮길 때 쓰는 장 구성 전략이다. 전략 하나에 파일 하나(`<slug>.json`)를 두고, `slide.py synopsis 원고.md` 를 실행하면 Jev 가 원고에 맞는 전략을 고른다(choice). 원고를 그 전략대로 개요에 옮기는 일은 Claude 가 한다.

- 목록: `python3 slide.py synopsis` · 한 전략: `python3 slide.py synopsis <slug>` · 갤러리 「시놉시스」 탭
- 모든 전략의 `example` 은 같은 주제(약국 재고 자동 발주)로 써서 전략 사이의 차이가 바로 보이게 했다.
- 전략은 공개된 방법론·책·연설을 요약해 새로 쓴 것이다. 원문을 옮기지 않았고 출처는 `source_ko`·`inspired_by` 에 적었다. 사내 원칙 PDF(`../principles.md`)의 내용은 넣지 않는다 — 전략 설명은 Jev 로 나간다.

## 칸

| 칸 | 뜻 |
|---|---|
| `slug` · `name` · `name_ko` · `family` | id(파일 이름과 같게) · 영문 이름 · 한국어 이름 · 계열(컨설팅·광고·키노트·투자·보고·제안·기획·교육·학술·데이터·스토리·카피 공식·속도형·소개·강연·명연설·세미나) |
| `inspired_by` | (선택) 본보기로 삼은 연설가·세미나·책 |
| `tagline_ko` · `best_for_ko` · `avoid_for_ko` · `signals_ko` · `audience_ko` | Jev 가 고를 때 보는 설명 — 한 줄 요약 · 어울리는 자리 · 피할 자리 · 원고에 보이는 신호 낱말 · 청중 |
| `headline_style` | 이 전략의 헤드라인 문체(`outline --jev` 의 「이름표 헤드라인」 판정에 쓴다) |
| `beats` | 장 구성 순서. 단계마다 `id` · `name` · `goal` · `layout`(`slide.py` 의 `LAYOUTS` 16종) · `section`(간지 이름) · `required`(꼭 있어야 할 단계) · `count`(선택, 장 수) |
| `rules_ko` | 장 규칙 3~5줄 |
| `knobs` | 점검 기준 — `max_headline_chars` · `max_bullets` · `max_body_chars` · `summary`(`front` 첫 세 장 안 / `end` 끝 세 장 안 / `none`) · `summary_words`(선택, 요약으로 볼 낱말 정규식) · `ig_min`(인포그래픽 적합 기준) · `image_ratio_min`(선택, 사진 장 비율) |
| `layout_prefer` | `outline --jev` 레이아웃 고르기에서 앞세울 장 |
| `template_hints` | `pick` 의 템플릿 고르기에 넘기는 덱 성격 — `scheme`(light·dark·null) · `density` · `style_ko` |
| `source_ko` | 출처 |
| `example` | 그 전략의 예시 개요(머리말 `synopsis: <slug>` 포함). `test_slide.py` 가 자기 전략 점검을 경고 없이 통과하는지 본다 |
