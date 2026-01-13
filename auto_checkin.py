import os
import re
import sys
import requests
from urllib.parse import urlencode


# ---------- Config (edit here) ----------
# Environment-driven config; provide defaults only where safe.
LOGIN_URL = "https://69yun69.com/auth/login"
CHECKIN_URL = "https://69yun69.com/user/checkin"
PUSH_URL = os.getenv("PUSH_URL", "")
BARK_LEVEL = os.getenv("BARK_LEVEL", "passive")
BARK_NOTIFY_LEVEL = int(os.getenv("BARK_NOTIFY_LEVEL", "2")) # Notification level, 0- No notification, 1- Notification only failed, 2- All
LOGIN_EMAIL = os.getenv("LOGIN_EMAIL", "").strip()
LOGIN_PASS = os.getenv("LOGIN_PASS", "").strip()

LOGIN_PAYLOAD = {
    "email": LOGIN_EMAIL,
    "passwd": LOGIN_PASS,
    "remember_me": "on",
    "code": "",
}

LOGIN_HEADERS = {
    "Origin": "https://69yun69.com",
    "Referer": "https://69yun69.com/auth/login",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

CHECKIN_HEADERS = {
    "Origin": "https://69yun69.com",
    "Referer": "https://69yun69.com/user",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}
# ---------- End config ----------

if not LOGIN_EMAIL or not LOGIN_PASS:
    raise SystemExit("Missing LOGIN_EMAIL or LOGIN_PASS environment variables.")
if not PUSH_URL:
    raise SystemExit("Missing PUSH_URL environment variable.")


class PushClient:
    """Lightweight builder for Bark-style push URLs."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._path_parts = []
        self._query = {}

    def add_path(self, *parts: str):
        for p in parts:
            if p:
                self._path_parts.append(p.strip("/"))
        return self

    def add_query(self, **params):
        for k, v in params.items():
            if v is not None:
                self._query[k] = v
        return self

    def build(self) -> str:
        path = "/".join(self._path_parts)
        url = f"{self.base_url}/{path}" if path else self.base_url
        if self._query:
            url = f"{url}?{urlencode(self._query)}"
        return url


def send_push(
    session: requests.Session,
    title: str,
    body: str = "",
    level: str = "passive",
    notify_level: int,
):
    if BARK_NOTIFY_LEVEL == 0:
        return
    if BARK_NOTIFY_LEVEL == 1 and notify_level == 2:
        return
    url = (
        PushClient(PUSH_URL)
        .add_path(title, body)
        .add_query(level=level or BARK_LEVEL)
        .build()
    )
    session.get(url)


def post_json(session: requests.Session, url: str, **kwargs):
    resp = session.post(url, **kwargs)
    try:
        data = resp.json()
    except ValueError:
        snippet = resp.text[:80]
        raise RuntimeError(f"非JSON响应: {snippet}")
    return resp, data


with requests.Session() as s:
    try:
        login_resp, login_data = post_json(s, LOGIN_URL, data=LOGIN_PAYLOAD, headers=LOGIN_HEADERS)
        login_msg = login_data.get("msg", "") if isinstance(login_data, dict) else ""
        if not (login_resp.ok and login_data.get("ret") == 1):
            send_push(s, "69云 - 登录失败", login_msg or f"状态码: {login_resp.status_code}", level="passive", notify_level=1)
            raise SystemExit(f"[ERROR] login failed, Exception: {login_msg or login_resp.status_code}")
    except Exception as exc:
        send_push(s, "69云 - 登录失败", str(exc), level="passive", notify_level=1)
        raise SystemExit(f"[ERROR] login failed, Exception: {exc}")

    try:
        checkin_resp, data = post_json(s, CHECKIN_URL, headers=CHECKIN_HEADERS)
        checkin = data.get("ret")

        m = re.search(r"获得了\s*([\d.]+\s*[A-Za-z]+)", data.get("msg", ""))
        gained = m.group(1).replace(" ", "") if m else "NaN"
        traffic_info = data.get("trafficInfo") or {}
        left = traffic_info.get("unUsedTraffic", "NaN")

        if checkin == 1:
            send_push(s, "69云 - 签到成功", f"获得流量: {gained}  剩余流量: {left}", level="passive", notify_level=2)
            print(f"[INFO] success: Check-in successful. Data received: {gained}, remaining data: {left}.")
            sys.exit(0)
        elif checkin == 0:
            raise SystemExit("[WARNING] checkin fail: You have already checked in.")
        else:
            reason = data.get("msg", "未知原因")
            send_push(s, "69云 - 签到失败", reason, level="passive", notify_level=1)
            raise SystemExit(f"[ERROR] checkin fail: Login successful, but check-in failed. Reason: {reason}")
    except Exception as exc:
        send_push(s, "69云 - 签到失败", str(exc), level="passive", notify_level=1)
        raise SystemExit(f"[ERROR] checkin fail: Login successful, but check-in failed. Exception: {exc}")
