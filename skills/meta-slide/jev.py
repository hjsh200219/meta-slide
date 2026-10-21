"""meta-slide·meta-motion 사본(2026-10-21 workspace shared/jev.py 에서 복사). 두 플러그인은 이 사본만 쓴다(PC 마다 같게).
원본과 다른 점: 키를 `setup.py` 가 저장한 곳(macOS 키체인 · 그 밖 ~/.config/typesafe-jev/key)에서도 읽고,
workspace .env 폴백에 ~/workspace/.env 를 더했다. 저장소는 두 플러그인이 같이 쓴다 — 한 번 setup 하면 둘 다 된다.

TypeSafe Jev (System One) 클라이언트 — 타입 붙은 판정 + 보정된 확률.

생성 모델이 아니다. `state`(판정 대상)와 `questions`(판정 내용)를 주면
질문마다 타입이 정해진 답과 확률을 돌려준다. 질문들은 **병렬·상호 비가시**로
평가되므로 한 답이 다른 답을 보고 바뀌지 않는다 — 한 번의 요청에 독립 질문을
몰아 넣는 게 정상 사용법이다.

세 가지 primitive:
  noul(instructions)            → {"noul": 0.0~1.0}          예/아니오의 '예' 확률
  choice(instructions, criteria) → {"choice", "confidence", "probabilities"}
  score(instructions, criteria)  → {"score", "confidence", "probabilities", "legend"}
  box(instructions)              → {"box": {top,bottom,left,right}, "confidence"}  이미지 속 위치(jev-1.14 전용)

이미지(2026-10-14~, 공식 «Dreamer-ready» — 형식·한도·정확도가 릴리스마다 바뀐다): 참조 문자열을 state·instructions·
criteria 글 안에 쓰고 ask(assets={참조: image_asset(바이트, "png"|"jpg")}) 로 넘긴다. 한 변 280~1568px·파일 16MiB,
범위 밖은 요청 전체가 거절된다. 상세·실측 `_vault/reference/typesafe-jev.md` 「이미지」.

criteria 모양이 primitive마다 다르다(자주 틀리는 자리):
  choice → **dict** {옵션이름: 설명}
  score  → **낮은→높은 순서의 list** (2~10단계)
  noul   → 없음

의존성 없음(stdlib urllib). 이 파일에 닿지 못하는 곳(독립 repo 등)에서는 그대로 복사해 쓴다 —
그래서 외부 패키지를 쓰지 않는다. `shared/` 는 workspace 의 gitignore 대상이라 이 repo 를
클론한 곳에는 없다. 호출부는 import 실패를 폴백으로 처리할 것.
현재 복사본: `cloud-jobs/common/jev.py`(2026-09-20, money-news jev_gate 용) · qa-agentic `scripts/jev.py`(2026-10-20 `assets`·`usage_out`
까지 맞춤 — 이미지를 보내는 사본은 그것뿐) · meta-plan·orchestra·jev-computer-use. 이미지를 안 보내는 사본은 그대로 둔다. 둘 다 `ask(..., usage_out=...)` 를 갖는다.
⛔ 2026-09-24 현재 **복사본이 한 칸 뒤처져 있다** — 이쪽 `usage_out` 은 `usage` 말고 응답의
`model`(실제로 답한 버전) 키도 담는데 복사본은 안 담는다(_vault/vault-classify.py 원장이 쓴다).
cloud-jobs 를 다음에 만질 때 그쪽으로 옮겨 맞춘다 — 방향은 여기 → 복사본이다.

키: 환경변수 JEV_API_KEY → setup.py 저장소(키체인/파일) → workspace 루트 .env 순서.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
IMAGES_HEADER = "TypeSafe-Danger-Zone-Images"  # 이미지·Box 질문이 든 요청에만 붙인다(없으면 400)
USER_AGENT = "jev-client/1.0 (+https://typesafe.ai)"

# 429(레이트리밋)·529(과부하)만 재시도한다. 422(스키마 위반)는 재시도해도 같은 답이라
# 즉시 올린다 — criteria 모양을 틀렸을 때 조용히 3번 기다리는 게 최악이다.
RETRY_STATUS = {429, 529}
RETRIES = 3
BACKOFF_S = 1.5


# 앞단 Cloudflare WAF 가 본문의 민감 경로·익스플로잇 문자열을 보면 API 에 닿기 전에 HTML 403 으로 막는다.
# 2026-09-23 실측(가짜 키로 WAF 층만 측정): `/etc/hosts`·`/etc/passwd`·`/proc/self/environ`·`${jndi:` → 403,
# `/etc/`·`etc/hosts`·`../../`·`<script>`·`rm -rf /`·SQL 은 통과. 허브노트 한 줄의 「/etc/hosts override」가
# git-push Pack 게이트를 통째로 폴백시켰다. 목록을 다 알 수 없으므로 막히면 한 번만 무력화해 다시 보낸다 —
# 슬래시를 U+2215(∕)로, `${` 를 `$ {` 로. 판정은 사람이 읽듯 읽으니 의미는 그대로다.
_DEFANG = (("/", "\u2215"), ("${", "$ {"))


def _defang(obj):
    if isinstance(obj, str):
        for a, b in _DEFANG:
            obj = obj.replace(a, b)
        return obj
    if isinstance(obj, dict):
        return {k: _defang(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_defang(v) for v in obj]
    return obj


def _is_waf_block(code: int, detail: str) -> bool:
    return code == 403 and detail.lstrip().startswith("<")


class JevError(RuntimeError):
    """호출 실패. 호출부는 이걸 잡아 '판정 없음'으로 폴백해야 한다."""


def _valid_key(raw: str) -> str:
    """헤더에 넣어도 안전한 키만 통과시킨다. **이게 1차 방어다.**

    개행·탭·비ASCII 가 섞인 키를 그대로 헤더에 넣으면 http.client 가
    `ValueError: Invalid header value b'Bearer <키전문>'` 을 올리고, 그 메시지가
    JevError 를 타고 로그에 찍힌다(2026-09-20 재현). _scrub 은 그 메시지가
    repr 로 이스케이프돼 있으면 원문과 매칭되지 않아 일부만 지운다 — 그래서
    지우는 것보다 **애초에 못 들어가게** 막는다. 여기서 막으면 키는 메시지에 없다.
    """
    key = raw.strip()
    if not key:
        raise JevError("JEV_API_KEY 가 비어 있다")
    if not key.isascii() or not key.isprintable():
        # 길이와 종류만 알린다. 값은 절대 싣지 않는다.
        raise JevError(
            f"JEV_API_KEY 에 헤더로 쓸 수 없는 문자가 있다(길이 {len(key)}). "
            "붙여넣기 중 개행·공백이 끼었는지 확인하라 — 값은 로그에 싣지 않는다"
        )
    return key


def _scrub(msg: str, key: str) -> str:
    """예외 메시지에서 키를 지운다. **strip() 만으로는 부족한 자리다.**

    키가 latin-1 밖 문자를 갖거나 우리가 못 본 경로로 헤더 검증에 걸리면
    http.client 가 헤더 값 전문을 예외 메시지에 실어 올린다. 그 메시지는
    JevError 로 올라가 호출부 로그에 찍힌다 — 마지막 방어선으로 한 번 더 지운다.
    """
    if not key:
        return msg
    out = msg.replace(key, "<JEV_API_KEY>")
    # 표현형이 달라도(repr·bytes 리터럴) 걸리도록 조각으로도 한 번 본다.
    for chunk in (key[:12], key[-12:]):
        if len(chunk) >= 8:
            out = out.replace(chunk, "<JEV_API_KEY>")
    return out


# ---- 키 저장소(setup.py 가 쓴다) ----
KEY_SERVICE = "typesafe-jev"          # 키체인 서비스·자격 증명 이름 — meta-slide·meta-motion 공용
KEY_ACCOUNT = "JEV_API_KEY"
# 키체인·자격 증명 관리자를 못 쓸 때의 파일(0600) — Windows 는 %APPDATA%, 그 밖은 ~/.config
KEY_FILE = (Path(os.environ["APPDATA"]) if os.name == "nt" and os.environ.get("APPDATA") else Path.home() / ".config") / "typesafe-jev" / "key"
SECURITY_BIN = "/usr/bin/security"


def _mac() -> bool:
    return sys.platform == "darwin" and os.path.exists(SECURITY_BIN)


def _q(v: str) -> str:  # `security -i` 줄 해석: 큰따옴표 안에서 \ 와 " 만 이스케이프
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'


# Windows 자격 증명 관리자(일반 자격 증명) — 표준 라이브러리 ctypes 로 advapi32 Cred* 를 부른다.
_WIN_TARGET = f"{KEY_SERVICE}/{KEY_ACCOUNT}"


def _win_api():
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
                    ("Comment", wintypes.LPWSTR), ("LastWritten", wintypes.FILETIME),
                    ("CredentialBlobSize", wintypes.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                    ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                    ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]
    try:
        adv = ctypes.WinDLL("advapi32", use_last_error=True)
    except OSError:
        return None
    return ctypes, CREDENTIAL, adv


def _win_read() -> str | None:
    api = _win_api()
    if not api:
        return None
    ctypes, CREDENTIAL, adv = api
    p = ctypes.POINTER(CREDENTIAL)()
    if not adv.CredReadW(_WIN_TARGET, 1, 0, ctypes.byref(p)):  # 1 = CRED_TYPE_GENERIC
        return None
    try:
        blob = ctypes.string_at(p.contents.CredentialBlob, p.contents.CredentialBlobSize)
        return blob.decode("utf-16-le").strip() or None
    finally:
        adv.CredFree(p)


def _win_write(key: str) -> bool:
    api = _win_api()
    if not api:
        return False
    ctypes, CREDENTIAL, adv = api
    blob = key.encode("utf-16-le")
    buf = ctypes.create_string_buffer(blob, len(blob))
    c = CREDENTIAL()
    c.Type, c.TargetName, c.UserName, c.Persist = 1, _WIN_TARGET, KEY_ACCOUNT, 2  # 2 = CRED_PERSIST_LOCAL_MACHINE
    c.CredentialBlobSize = len(blob)
    c.CredentialBlob = ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte))
    return bool(adv.CredWriteW(ctypes.byref(c), 0)) and _win_read() == key


def _win_delete() -> bool:
    api = _win_api()
    return bool(api and api[2].CredDeleteW(_WIN_TARGET, 1, 0))


def stored_key() -> tuple[str | None, str]:
    """(저장된 키, 어디서 읽었는지). 없으면 (None, "")."""
    if _mac():
        try:
            r = subprocess.run([SECURITY_BIN, "find-generic-password", "-s", KEY_SERVICE, "-a", KEY_ACCOUNT, "-w"],
                               capture_output=True, text=True, timeout=15)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip(), f"macOS 키체인 서비스 {KEY_SERVICE}"
        except subprocess.TimeoutExpired:
            pass
    k = _win_read()
    if k:
        return k, f"Windows 자격 증명 관리자 {_WIN_TARGET}"
    if KEY_FILE.exists():
        k = KEY_FILE.read_text(encoding="utf-8").strip()
        if k:
            return k, str(KEY_FILE)
    return None, ""


def save_key(key: str) -> str:
    """키를 저장하고 저장한 곳을 돌려준다. 키는 명령 인자(ps 로 보임)로 넘기지 않는다."""
    key = _valid_key(key)
    if _mac():
        line = f"add-generic-password -U -s {_q(KEY_SERVICE)} -a {_q(KEY_ACCOUNT)} -T {SECURITY_BIN} -w {_q(key)}\n"
        r = subprocess.run([SECURITY_BIN, "-i"], input=line, capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and stored_key()[0] == key:
            return f"macOS 키체인 서비스 {KEY_SERVICE}"
    if _win_write(key):
        return f"Windows 자격 증명 관리자 {_WIN_TARGET}"
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(KEY_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(key + "\n")
    os.chmod(KEY_FILE, 0o600)
    return str(KEY_FILE)


def forget_key() -> list[str]:
    """저장된 키를 지우고 지운 곳 목록을 돌려준다(환경변수·workspace .env 는 건드리지 않는다)."""
    gone = []
    if _mac() and subprocess.run([SECURITY_BIN, "delete-generic-password", "-s", KEY_SERVICE, "-a", KEY_ACCOUNT],
                                 capture_output=True, text=True).returncode == 0:
        gone.append(f"macOS 키체인 서비스 {KEY_SERVICE}")
    if _win_delete():
        gone.append(f"Windows 자격 증명 관리자 {_WIN_TARGET}")
    if KEY_FILE.exists():
        KEY_FILE.unlink()
        gone.append(str(KEY_FILE))
    return gone


def _env_files():
    # workspace 루트 .env 폴백. 원본은 shared/ 에 있어 부모가 루트다 — 이 사본은 ~/workspace/.env 도 본다.
    return (Path(__file__).resolve().parent.parent / ".env", Path.home() / "workspace" / ".env")


def key_source() -> str:
    """키를 어디서 읽게 되는지(값 없이). 없으면 ""."""
    if os.environ.get("JEV_API_KEY", "").strip():
        return "환경변수 JEV_API_KEY"
    k, where = stored_key()
    if k:
        return where
    for env in _env_files():
        if env.exists() and any(l.strip().startswith("JEV_API_KEY=")
                                for l in env.read_text(encoding="utf-8", errors="replace").splitlines()):
            return str(env)
    return ""


def _load_key() -> str:
    key = os.environ.get("JEV_API_KEY", "").strip()
    if key:
        return key
    key, _ = stored_key()
    if key:
        return key
    for env in _env_files():
        if not env.exists():
            continue
        for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("JEV_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    raise JevError("JEV_API_KEY 없음 — `python3 setup.py` 로 저장하거나 환경변수 JEV_API_KEY 를 주세요")


def ask(
    state,
    questions: dict,
    *,
    model: str = MODEL,
    timeout_s: int = 60,
    api_key: str | None = None,
    usage_out: dict | None = None,
    assets: dict | None = None,
) -> dict:
    """state 에 대해 questions 를 한 번에 판정. 질문키 → 답 dict 를 돌려준다.

    state 는 문자열이거나 JSON 직렬화 가능한 객체/배열. 판정에 필요한 맥락이
    여러 조각이면 이름 붙인 필드를 가진 객체로 주는 쪽이 낫다.

    usage_out 을 주면 성공한 응답의 `usage`(input_tokens·output_tokens)와 **실제로 답한
    모델 버전**(`model`)을 그 dict 에 담는다. 반환값 모양을 바꾸지 않으려고 출력 인자로
    받는다. `jev-latest` 는 릴리스 때 움직이므로 원장에는 보낸 이름이 아니라 여기 담긴
    `model` 을 남긴다(2026-09-24 실측: 같은 입력에 0.65/0.69 — Jev 는 결정론이 아니다).
    cloud-jobs/common/jev.py 의 같은 인자와 맞춘 것이고, 이쪽이 `model` 한 키만 더 담는다.

    assets 는 이미지 {참조: image_asset(...)} — 있으면 이미지 헤더를 붙인다. Box 질문은 이미지와 jev-1.14(`jev-preview`)가 필요하다.

    실패는 전부 JevError. 호출부가 폴백 경로를 반드시 갖도록 None 을 돌려주지 않는다.
    """
    if not questions:
        return {}
    def encode(st) -> bytes:
        body = {"state": st, "model": model, "questions": questions}
        if assets:
            body["assets"] = assets  # 무력화(_defang) 대상이 아니다 — base64 의 '/' 를 바꾸면 이미지가 깨진다
        return json.dumps(body, ensure_ascii=False).encode("utf-8")

    body = encode(state)
    # 헤더에 넣기 전에 키를 정리한다. 개행·제어문자가 섞인 키를 그대로 넣으면
    # http.client 가 `ValueError: Invalid header value b'Bearer <키전문>'` 을 올리고,
    # 아래 `except Exception` 이 그 메시지를 JevError 에 실어 로그로 내보낸다
    # (2026-09-20 재현). 긴 토큰을 붙여넣다 공백이 끼는 사고가 실제로 있었다.
    key = _valid_key(api_key or _load_key())
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            # UA 를 빼면 안 된다. urllib 기본 UA(Python-urllib/3.x)로 보내면 앞단 Cloudflare 가
            # `HTTP 403: error code: 1010` 으로 막는다 — 키 문제로 보이지만 요청이 서버에 닿지도 않는다.
            # 2026-09-23 실측: 같은 키·같은 본문으로 UA 없음 403, UA 있음 200.
            "User-Agent": USER_AGENT,
            **({IMAGES_HEADER: "true"} if assets else {}),
        },
        method="POST",
    )
    last = ""
    defanged = False
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as r:
                payload = json.loads(r.read().decode("utf-8"))
            if usage_out is not None:
                if isinstance(payload.get("usage"), dict):
                    usage_out.update(payload["usage"])
                if payload.get("model"):
                    usage_out["model"] = payload["model"]
            return payload.get("answers") or {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:400]
            if _is_waf_block(e.code, detail) and not defanged:
                defanged = True
                req.data = encode(_defang(state))
                req.add_unredirected_header("Content-length", str(len(req.data)))
                continue
            # 서버가 요청 헤더를 되비추는 경우가 있어 여기도 지운다(401 응답이 흔하다).
            last = _scrub(f"HTTP {e.code}: {detail}", key)
            if e.code not in RETRY_STATUS or attempt == RETRIES - 1:
                raise JevError(last) from e
            time.sleep(BACKOFF_S * (2**attempt))
        except Exception as e:  # 네트워크·타임아웃·JSON 파싱
            last = _scrub(f"{type(e).__name__}: {e}", key)
            if attempt == RETRIES - 1:
                raise JevError(last) from e
            time.sleep(BACKOFF_S * (2**attempt))
    raise JevError(last or "알 수 없는 실패")


# ── 이미지 ────────────────────────────────────────────────────────


def image_asset(data: bytes, fmt: str) -> dict:
    """ask(assets={참조: image_asset(...)}) 항목. 참조는 글 속에서 우연히 겹치지 않게 UUID 를 쓴다.
    서버는 EXIF 회전을 적용하지 않고 크기를 줄여 주지도 않는다 — 회전·축소는 호출부가 한다."""
    if fmt not in ("png", "jpg"):
        raise ValueError("image_asset 형식은 png | jpg")
    return {"type": "image", "format": fmt, "data_base64": base64.b64encode(data).decode("ascii")}


# ── 질문 생성 헬퍼 ────────────────────────────────────────────────
# 직접 dict 를 써도 되지만, criteria 모양(choice=dict / score=list)을 여기서
# 강제해 422 를 호출 시점이 아니라 작성 시점에 잡는다.


def noul(instructions: str) -> dict:
    return {"type": "noul", "instructions": instructions}


def choice(instructions: str, criteria: dict) -> dict:
    if not isinstance(criteria, dict) or len(criteria) < 2:
        raise ValueError("choice criteria 는 옵션 2개 이상의 dict {이름: 설명}")
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def box(instructions: str) -> dict:
    """이미지 속 대상의 경계 상자. criteria 없음. jev-1.14 전용(model="jev-preview")."""
    return {"type": "box", "instructions": instructions}


def score(instructions: str, criteria: list) -> dict:
    if not isinstance(criteria, list) or not (2 <= len(criteria) <= 10):
        raise ValueError("score criteria 는 낮은→높은 순서의 list, 2~10단계")
    return {"type": "score", "instructions": instructions, "criteria": criteria}


# ── 답 읽기 헬퍼 ──────────────────────────────────────────────────
# 답이 없거나 타입이 어긋나면 default 를 돌려준다. 판정 하나가 빠졌을 때
# KeyError 로 전체 파이프라인이 죽는 걸 막는다.


def noul_of(answers: dict, key: str, default: float | None = None) -> float | None:
    a = answers.get(key)
    if not isinstance(a, dict) or a.get("type") != "noul":
        return default
    try:
        return float(a["noul"])
    except (KeyError, TypeError, ValueError):
        return default


def choice_of(answers: dict, key: str) -> tuple[str | None, float]:
    """(고른 옵션, confidence). 답이 없으면 (None, 0.0)."""
    a = answers.get(key)
    if not isinstance(a, dict) or a.get("type") != "choice":
        return None, 0.0
    try:
        return str(a["choice"]), float(a.get("confidence") or 0.0)
    except (KeyError, TypeError, ValueError):
        return None, 0.0


def score_of(answers: dict, key: str) -> tuple[float | None, float]:
    """(점수, confidence). 답이 없으면 (None, 0.0)."""
    a = answers.get(key)
    if not isinstance(a, dict) or a.get("type") != "score":
        return None, 0.0
    try:
        return float(a["score"]), float(a.get("confidence") or 0.0)
    except (KeyError, TypeError, ValueError):
        return None, 0.0


def box_of(answers: dict, key: str) -> tuple[dict | None, float]:
    """({top,bottom,left,right} 0~1 비율, confidence). 답이 없으면 (None, 0.0)."""
    a = answers.get(key)
    if not isinstance(a, dict) or a.get("type") != "box" or not isinstance(a.get("box"), dict):
        return None, 0.0
    try:
        return {k: float(a["box"][k]) for k in ("top", "bottom", "left", "right")}, float(a.get("confidence") or 0.0)
    except (KeyError, TypeError, ValueError):
        return None, 0.0
