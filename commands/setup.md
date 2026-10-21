---
description: Jev(TypeSafe) API 키를 이 PC 에 저장한다(macOS 키체인 · Windows 자격 증명 관리자 · 그 밖 0600 파일) — meta-motion 과 같은 저장소라 한 번이면 둘 다 된다. 키는 채팅으로 받지 않는다
argument-hint: "[--check|--force|--forget]"
allowed-tools: Bash(python3:*), Bash(python:*)
---

# meta-slide 키 등록

**키를 채팅으로 묻지 않는다. 사용자가 채팅에 키를 붙여 넣으면 쓰지 말고, 노출됐으니 TypeSafe 에서 키를 새로 발급받으라고 안내한다.**

사전 점검 없이 아래 명령 하나를 바로 실행한다(인자를 받았으면 그대로 붙인다). Bash `timeout` 은 **600000** — 사람이 입력하는 동안 끊기지 않게.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/meta-slide/setup.py" $ARGUMENTS || python "${CLAUDE_PLUGIN_ROOT}/skills/meta-slide/setup.py" $ARGUMENTS
```

실행 직전에 한 줄만 말한다:
> 화면에 「meta-slide · meta-motion」 입력 창이 뜨면 Jev API 키를 넣어 주세요. 키는 이 대화에 남지 않고 이 PC 에만 저장됩니다. (이미 등록돼 있으면 창 없이 끝납니다)

결과 읽기:
- `✓ 저장했습니다` / `✓ 이미 설정돼 있습니다` → 한 줄로 알리고 끝.
- `✗ SSH 로 붙어 있어 입력 창을 띄울 수 없습니다` → 사용자가 **그 SSH 터미널에서 직접** 출력에 찍힌 명령을 실행하게 안내한다(키는 화면에 안 찍히는 프롬프트로 받는다).
- `✗ 저장하지 않았습니다 — Jev 확인 실패` → 키가 틀렸거나 만료됐다. 다시 할지 묻는다(자동으로 다시 돌리지 않는다).
- `✗ 입력을 취소했습니다` → 그대로 끝낸다.

키가 없으면 슬라이드는 `--no-jev`(기본값으로 고름)로만 만들 수 있다. 키 발급: https://typesafe.ai (사내는 관리자에게 받는다).
