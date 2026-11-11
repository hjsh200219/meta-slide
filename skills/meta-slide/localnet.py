"""`--local` 입구 — SSH 로 이 Mac(edb-mac)에 붙어 쓰는 사용자의 PC 브라우저에서 로컬 갤러리를 열게 한다. 표준 라이브러리만 쓴다.

127.0.0.1 입구에 더해 이 Mac 의 Tailscale IP 에도 같은 포트로 띄운다. 들어올 수 있는 것은 이 Mac 과 Tailscale 계정(UserID)이 같은
기기(본인 PC·폰)뿐이다 — tailnet 출발 IP 는 WireGuard 로 인증되므로 IP 허용 목록이 실제 관문이다. 같은 tailnet 의 동료 기기는 403.
Host 머리글도 허용 이름(localhost·127.0.0.1·이 Mac 의 tailnet 이름·IP)만 받는다(DNS rebinding 막기).
요청이 IDLE_SECONDS 동안 없으면 스스로 꺼진다(밖으로 열린 입구를 상주시키지 않는다).
같은 판단을 bizmonitor 뷰어(cloud-jobs/jobs/bizmonitor/viewer/server.py --tailnet)가 쓴다. 이 파일은 meta-slide·meta-motion 에 같은 사본이 있다.
"""
import json
import os
import shutil
import signal
import subprocess
import threading
import time
from urllib.parse import urlsplit

TAILSCALE_CLI = ("tailscale", "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
                 os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Tailscale", "tailscale.exe"))
LOCAL_HOSTS = {"localhost", "127.0.0.1"}
IDLE_SECONDS = 2 * 3600
# 사용자 PC 크롬(claude-in-chrome 짝) — /bizmonitor --local 때 한 번 짝지었다. Claude 가 select_browser 에 넘긴다.
PC_BROWSER = os.path.expanduser("~/workspace/_vault/skills/bizmonitor/local-browser.json")


def tailscale_status():
    for cli in TAILSCALE_CLI:
        path = shutil.which(cli) or (cli if os.path.exists(cli) else None)
        if not path:
            continue
        try:
            out = subprocess.run([path, "status", "--json"], capture_output=True, text=True, timeout=10, check=True)
            return json.loads(out.stdout)
        except (OSError, subprocess.SubprocessError, ValueError):
            continue
    return {}


def refuse_reason(status):
    """--local 을 열면 안 되는 이유(없으면 None). 태그 기기는 사람 계정이 아니라 tailnet 공용 「tagged-devices」 UserID 를
    함께 쓰므로, 이 기기에 태그가 있으면 「같은 계정」 판단이 다른 사람의 태그 기기까지 통과시킨다 — 열지 않는다(fail-closed)."""
    me = status.get("Self") or {}
    if not me:
        return "tailscale 상태를 읽지 못했습니다(tailscale status 확인)"
    if me.get("Tags"):
        return "이 기기에 Tailscale 태그가 있어 같은 계정 기기만 받는 관문을 만들 수 없습니다 — 태그 없는 기기에서 실행하세요"
    if me.get("UserID") is None or not [ip for ip in me.get("TailscaleIPs") or [] if ":" not in ip]:
        return "이 기기의 Tailscale 계정·주소를 읽지 못했습니다(tailscale status 확인)"
    return None


def allowlist(status):
    """`tailscale status --json` → (내 IPv4, 내 tailnet 이름, Host 로 받을 이름·IP, 들어올 수 있는 IP). 열면 안 되면 (None, None, set(), set()).
    들어올 수 있는 IP = 이 기기와 UserID 가 같고 태그가 없는 기기(본인 PC·폰)와 이 기기 자신."""
    if refuse_reason(status):
        return None, None, set(), set()
    me = status.get("Self") or {}
    uid = me.get("UserID")
    ips = [ip for ip in me.get("TailscaleIPs") or [] if ":" not in ip]
    if uid is None or not ips:
        return None, None, set(), set()
    dns = (me.get("DNSName") or "").rstrip(".") or None
    hosts = {ips[0]} | ({dns, dns.split(".")[0]} if dns else set())
    peers = set(me.get("TailscaleIPs") or [])
    for peer in (status.get("Peer") or {}).values():
        if peer.get("UserID") == uid and not peer.get("Tags"):  # 태그 기기는 공용 UserID — 넣지 않는다
            peers |= set(peer.get("TailscaleIPs") or [])
    return ips[0], dns, hosts, peers


class Gate:
    """요청마다 부르는 관문. hosts·peers 가 비어 있으면 127.0.0.1 입구만 있는 것으로 본다."""

    def __init__(self, port, hosts=(), peers=()):
        self.port, self.hosts, self.peers = port, set(hosts), set(peers)
        self.last = time.monotonic()

    def allowed(self, client, host_header):
        self.last = time.monotonic()
        if client not in ("127.0.0.1", "::1") and client not in self.peers:
            return False
        try:
            u = urlsplit("http://" + (host_header or ""))
            return (u.hostname in (LOCAL_HOSTS | self.hosts) and u.port == self.port and u.netloc == host_header
                    and not u.username and not u.path and not u.query and not u.fragment)
        except ValueError:
            return False


def _listeners(port):
    """그 포트에서 듣는 프로세스 pid 목록. 확인할 도구가 없으면 None. Windows 는 PowerShell, 그 밖은 lsof."""
    if os.name == "nt":
        cmd = ["powershell.exe", "-NoProfile", "-Command",
               f"(Get-NetTCPConnection -State Listen -LocalPort {port} -ErrorAction SilentlyContinue).OwningProcess | Select-Object -Unique"]
    else:
        cmd = ["lsof", "-nP", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return sorted({int(x) for x in out.split() if x.strip().isdigit()})


def _bindable(port):
    import socket
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _read_pid(pidfile):
    try:
        with open(pidfile, encoding="utf-8") as f:
            return int(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def _is_ours(pid):
    """그 pid 가 지금도 이 도구의 서버인가 — pidfile 이 남은 채 pid 가 다른 프로그램에 재사용됐으면 끄지 않는다.
    명령줄에 서버 스크립트 이름이 있는지로 본다. 확인할 수 없으면(Windows·ps 실패) 남의 것으로 보고 다음 포트로 넘어간다."""
    if os.name == "nt":
        return False
    try:
        cmd = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return any(n in cmd for n in ("serve.py", "motion.py", "slide.py", "meta-slide", "meta-motion"))


def claim(pidfile, port):
    """이 서버가 그 포트를 쓴다고 적는다 — 다음 실행이 옛 서버를 알아보고 끈다(다른 프로그램은 건드리지 않게)."""
    os.makedirs(os.path.dirname(pidfile), exist_ok=True)
    with open(pidfile, "w", encoding="utf-8") as f:
        f.write(f"{os.getpid()} {port}\n")


def free_port(port, pidfile):
    """그 포트를 이 도구의 옛 서버(pidfile 에 적힌 pid)가 잡고 있으면 끈다. 비었으면 True, 다른 프로그램이 쓰면 False."""
    pids = _listeners(port)
    if pids is None:
        return _bindable(port)
    if not pids:
        return True
    mine = _read_pid(pidfile)
    if mine is None or mine == os.getpid() or pids != [mine] or not _is_ours(mine):
        return False
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(mine), "/F"], capture_output=True)
    else:
        os.kill(mine, signal.SIGTERM)
    for _ in range(20):
        time.sleep(0.2)
        if _bindable(port):
            return True
    return False


def pick_port(port, pidfile, tries=10):
    """port 부터 차례로 — 이 도구의 옛 서버면 끄고 쓰고, 다른 프로그램이 쓰면 다음 포트. 쓸 포트(없으면 None)."""
    for p in range(port, port + tries):
        if free_port(p, pidfile) and _bindable(p):
            return p
    return None


def idle_watch(gate, servers):
    def run():
        while True:
            time.sleep(60)
            if time.monotonic() - gate.last > IDLE_SECONDS:
                for s in servers:
                    s.shutdown()
                return
    threading.Thread(target=run, daemon=True).start()


def pc_browser():
    try:
        with open(PC_BROWSER, encoding="utf-8") as f:
            return json.load(f).get("deviceId")
    except (OSError, ValueError):
        return None


def osc8(url):
    """터미널에서 눌러 열 수 있는 링크."""
    return f"\033]8;;{url}\033\\{url}\033]8;;\033\\"
