#!/usr/bin/env python3
"""meta-slide·meta-motion 에 필요한 API 키를 이 PC 에 저장한다(두 플러그인 공용 저장소 — 한 번이면 둘 다 된다). 표준 라이브러리만 쓴다.

  python3 setup.py              필요한 키마다: 없으면 받아서 확인 뒤 저장 · 있으면 확인만
  python3 setup.py --check      어디서 읽는지만(값은 찍지 않는다) · 꼭 필요한 키가 없으면 종료 코드 1
  python3 setup.py --force      새 키로 바꾼다          --forget   저장한 키를 지운다(환경변수·workspace .env 는 그대로)
  python3 setup.py --only fish  그 키만(jev · fish)

키:
  jev   Jev(TypeSafe) — meta-slide pick·outline --jev, meta-motion recommend·색·서체 템플릿 고르기. 발급 https://typesafe.ai
  fish  Fish Audio — meta-motion 내레이션(narrate · 기본 보이스). meta-motion 에서만 묻는다. 발급 https://fish.audio → API Keys
저장 위치: macOS 키체인 · Windows 자격 증명 관리자 · 그 밖(또는 SSH 로 붙은 Windows) <~/.config 또는 %APPDATA%>/<서비스>/key(0600).
읽는 순서: 환경변수 → 위 저장소 → ~/workspace/.env.
키는 채팅·명령 인자로 받지 않는다 — 터미널이면 화면에 안 찍히는 입력, 터미널이 없으면 OS 입력 창(macOS·Windows).
SSH 로 붙어 있으면 입력 창이 원격 화면에 떠 보이지 않으므로 SSH 터미널에서 직접 실행한다.
"""
import getpass
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jev  # noqa: E402

HERE = os.path.abspath(__file__)
PY = "python" if os.name == "nt" else "python3"  # Windows 는 python(또는 py)


def _verify_jev(key):
    old = os.environ.get("JEV_API_KEY")
    os.environ["JEV_API_KEY"] = key
    try:
        jev.ask("확인용 문장: 하늘은 파랗다.", {"ok": jev.noul("이 문장은 한국어인가?")})
        return True, ""
    except jev.JevError as e:
        return False, str(e)[:200]
    finally:
        if old is None:
            os.environ.pop("JEV_API_KEY", None)
        else:
            os.environ["JEV_API_KEY"] = old


def _verify_fish(key):
    """과금 없는 잔액 조회로 확인한다(맞으면 200, 틀리면 401 — 2026-10-21 실측). 잔액이 0 이면 합성 때 402 가 난다."""
    req = urllib.request.Request("https://api.fish.audio/wallet/self/api-credit", headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.loads(r.read().decode("utf-8", "replace") or "{}")
        credit = body.get("credit")
        return True, (f"API 크레딧 {credit}" if credit is not None else "")
    except urllib.error.HTTPError as e:
        return False, f"Fish Audio {e.code}" + (" — 키가 틀렸거나 만료" if e.code in (401, 403) else "")
    except (urllib.error.URLError, OSError, ValueError) as e:
        return False, f"Fish Audio 연결 실패: {type(e).__name__}"


KEYS = {
    "jev": {"label": "Jev(TypeSafe) API 키", "service": jev.KEY_SERVICE, "account": jev.KEY_ACCOUNT, "env": "JEV_API_KEY",
            "verify": _verify_jev, "url": "https://typesafe.ai", "required": True},
    "fish": {"label": "Fish Audio API 키(내레이션)", "service": "fish-audio", "account": "FISH_AUDIO_API_KEY", "env": "FISH_AUDIO_API_KEY",
             "verify": _verify_fish, "url": "https://fish.audio", "required": False},
}


def plugin_keys():
    """이 플러그인이 쓰는 키 — 내레이션 도구(narrate/)가 옆에 있으면 meta-motion 이라 fish 도 묻는다."""
    here = os.path.dirname(HERE)
    return ["jev", "fish"] if os.path.isdir(os.path.join(here, "narrate")) else ["jev"]


def ask_value(label, optional):
    msg = f"{label}" + (" — 없으면 비워 두세요" if optional else "")
    if sys.stdin.isatty():
        return getpass.getpass(f"{msg}(입력은 화면에 안 보입니다): ")
    if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"):
        raise SystemExit(f"✗ SSH 로 붙어 있어 입력 창을 띄울 수 없습니다(창이 원격 컴퓨터 화면에 뜹니다).\n"
                         f"  SSH 터미널에서 직접 실행하세요: {PY} {HERE}")
    if sys.platform == "darwin":
        script = (f'display dialog "{msg}를 넣어 주세요. 이 PC 에만 저장됩니다." default answer "" with hidden answer '
                  'with title "meta-slide · meta-motion" buttons {"취소", "확인"} default button "확인" cancel button "취소"\n'
                  "text returned of result")
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise SystemExit("✗ 입력을 취소했습니다")
        return r.stdout.rstrip("\n")
    if os.name == "nt":
        ps = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
              f"$c=Get-Credential -UserName 'API_KEY' -Message '{msg}';"
              "if(-not $c){exit 1};[Console]::Out.Write($c.GetNetworkCredential().Password)")
        r = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps], capture_output=True, timeout=600)
        if r.returncode != 0:
            raise SystemExit("✗ 입력을 취소했습니다")
        return r.stdout.decode("utf-8", "replace")
    raise SystemExit(f"✗ 입력 창을 띄울 수 없습니다. 터미널에서 직접 실행하세요: {PY} {HERE}")


def setup_one(name, force):
    k = KEYS[name]
    value, src = jev.load_secret(k["service"], k["account"], k["env"])
    if value and not force:
        ok, note = k["verify"](value)
        if ok:
            print(f"✓ {k['label']} — 이미 설정돼 있습니다({src}) · 확인 통과" + (f" · {note}" if note else ""))
            return True
        print(f"△ {k['label']} — 있지만 확인 실패({src}): {note}\n  바꾸려면 {PY} {HERE} --force --only {name}")
        return False
    value = ask_value(k["label"], not k["required"]).strip()
    if not value:
        print(f"- {k['label']} — 건너뜀" + ("" if k["required"] else " (내레이션 없이 쓰거나 나중에 --only " + name + ")"))
        return not k["required"]
    try:
        jev._valid_key(value)
    except jev.JevError as e:
        print(f"✗ {k['label']} — 저장하지 않았습니다: {str(e).replace('JEV_API_KEY', k['env'])}")
        return False
    ok, note = k["verify"](value)
    if not ok:
        print(f"✗ {k['label']} — 저장하지 않았습니다(확인 실패: {note}) · 발급 {k['url']}")
        return False
    print(f"✓ {k['label']} — 저장했습니다({jev.save_secret(k['service'], k['account'], value)}) · 확인 통과" + (f" · {note}" if note else ""))
    return True


def main(argv):
    if os.name == "nt":  # cp949 콘솔·파이프에서 ✓ 같은 기호가 깨지지 않게
        for s in (sys.stdout, sys.stderr):
            try:
                s.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass
    names = plugin_keys()
    if "--only" in argv:
        only = argv[argv.index("--only") + 1] if argv.index("--only") + 1 < len(argv) else ""
        if only not in KEYS:
            print(f"--only 는 {' · '.join(KEYS)} 중 하나")
            return 2
        names = [only]
    if "--forget" in argv:
        for n in names:
            gone = jev.forget_secret(KEYS[n]["service"], KEYS[n]["account"])
            print(f"✓ {KEYS[n]['label']} 지움: " + ", ".join(gone) if gone else f"- {KEYS[n]['label']} 저장된 것 없음")
        return 0
    if "--check" in argv:
        missing = False
        for n in names:
            src = jev.load_secret(KEYS[n]["service"], KEYS[n]["account"], KEYS[n]["env"])[1]
            req = KEYS[n]["required"]
            print(f"✓ {KEYS[n]['label']} — {src}" if src else f"{'✗' if req else '-'} {KEYS[n]['label']} — 없음({PY} {HERE}" + ("" if req else f" --only {n}") + ")")
            missing |= req and not src
        return 1 if missing else 0
    ok = all([setup_one(n, "--force" in argv) for n in names])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
