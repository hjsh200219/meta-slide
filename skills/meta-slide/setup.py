#!/usr/bin/env python3
"""Jev(TypeSafe) API 키를 이 PC 에 저장한다 — meta-slide·meta-motion 공용(같은 저장소라 한 번이면 둘 다 된다). 표준 라이브러리만 쓴다.

  python3 setup.py            키가 없으면 받아서 확인(Jev 1회 호출) 뒤 저장 · 이미 있으면 확인만
  python3 setup.py --check    어디서 읽는지만(값은 찍지 않는다) · 없으면 종료 코드 1
  python3 setup.py --force    새 키로 바꾼다
  python3 setup.py --forget   저장한 키를 지운다(환경변수·workspace .env 는 건드리지 않는다)

저장 위치: macOS 키체인 서비스 typesafe-jev(계정 JEV_API_KEY) · 그 밖의 OS ~/.config/typesafe-jev/key(0600).
읽는 순서: 환경변수 JEV_API_KEY → 위 저장소 → ~/workspace/.env.
키는 채팅·명령 인자로 받지 않는다 — 터미널이면 화면에 안 찍히는 입력, 터미널이 없으면 OS 입력 창(macOS·Windows).
SSH 로 붙어 있으면 입력 창이 원격 Mac 화면에 떠 보이지 않으므로 SSH 터미널에서 직접 실행한다.
키 발급: https://typesafe.ai (사내는 관리자에게 받는다).
"""
import getpass
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jev  # noqa: E402

HERE = os.path.abspath(__file__)
PY = "python" if os.name == "nt" else "python3"  # Windows 는 python(또는 py)


def ask_key():
    msg = "Jev(TypeSafe) API 키"
    if sys.stdin.isatty():
        return getpass.getpass(f"{msg}(입력은 화면에 안 보입니다): ")
    if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"):
        raise SystemExit(f"✗ SSH 로 붙어 있어 입력 창을 띄울 수 없습니다(창이 원격 Mac 화면에 뜹니다).\n"
                         f"  SSH 터미널에서 직접 실행하세요: {PY} {HERE}")
    if sys.platform == "darwin":
        script = (f'display dialog "{msg}를 넣어 주세요. 이 PC 키체인에만 저장됩니다." default answer "" with hidden answer '
                  'with title "meta-slide · meta-motion" buttons {"취소", "확인"} default button "확인" cancel button "취소"\n'
                  "text returned of result")
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise SystemExit("✗ 입력을 취소했습니다")
        return r.stdout.rstrip("\n")
    if os.name == "nt":
        ps = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
              f"$c=Get-Credential -UserName 'JEV_API_KEY' -Message '{msg}';"
              "if(-not $c){exit 1};[Console]::Out.Write($c.GetNetworkCredential().Password)")
        r = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps], capture_output=True, timeout=600)
        if r.returncode != 0:
            raise SystemExit("✗ 입력을 취소했습니다")
        return r.stdout.decode("utf-8", "replace")
    raise SystemExit(f"✗ 입력 창을 띄울 수 없습니다. 터미널에서 직접 실행하세요: {PY} {HERE}")


def verify(key=None):
    """Jev 에 아주 작은 질문 하나를 보내 키가 맞는지 본다. (맞음, 사유)."""
    old = os.environ.get("JEV_API_KEY")
    if key is not None:
        os.environ["JEV_API_KEY"] = key
    try:
        jev.ask("확인용 문장: 하늘은 파랗다.", {"ok": jev.noul("이 문장은 한국어인가?")})
        return True, ""
    except jev.JevError as e:
        return False, str(e)[:200]
    finally:
        if key is not None:
            if old is None:
                os.environ.pop("JEV_API_KEY", None)
            else:
                os.environ["JEV_API_KEY"] = old


def main(argv):
    if os.name == "nt":  # cp949 콘솔·파이프에서 ✓ 같은 기호가 깨지지 않게
        for s in (sys.stdout, sys.stderr):
            try:
                s.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass
    if "--forget" in argv:
        gone = jev.forget_key()
        print("✓ 지웠습니다: " + ", ".join(gone) if gone else "저장된 키가 없습니다")
        return 0
    src = jev.key_source()
    if "--check" in argv:
        print(f"✓ 키 있음 — {src}" if src else f"✗ 키 없음 — {PY} {HERE} 로 저장하세요")
        return 0 if src else 1
    if src and "--force" not in argv:
        ok, why = verify()
        if ok:
            print(f"✓ 이미 설정돼 있습니다 — {src} (Jev 확인 통과)")
            return 0
        print(f"△ 키가 있지만 Jev 확인에 실패했습니다 — {src}: {why}\n  새 키로 바꾸려면 {PY} {HERE} --force")
        return 1
    key = ask_key().strip()
    try:
        key = jev._valid_key(key)
    except jev.JevError as e:
        print(f"✗ 저장하지 않았습니다 — {e}")
        return 1
    ok, why = verify(key)
    if not ok:
        print(f"✗ 저장하지 않았습니다 — Jev 확인 실패: {why}")
        return 1
    print(f"✓ 저장했습니다 — {jev.save_key(key)} (Jev 확인 통과 · meta-slide·meta-motion 공용)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
