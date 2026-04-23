"""CLI session file and HTTP login/register against OpenAgentic API."""

from __future__ import annotations

import json
from getpass import getpass
from pathlib import Path

import httpx

from openagentic.cli.platform_adapter import CLI_PLATFORM


def cli_session_path() -> Path:
    return Path.home() / ".openagentic" / "cli_session.json"


def load_cli_session() -> dict | None:
    p = cli_session_path()
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_cli_session(payload: dict) -> None:
    p = cli_session_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    CLI_PLATFORM.secure_file_permissions(p)


def clear_cli_session_file() -> None:
    p = cli_session_path()
    try:
        p.unlink(missing_ok=True)
    except OSError:
        pass


def platform_authenticate_sync(api_base: str) -> tuple[str, str]:
    """Login or register against OpenAgentic HTTP API; return (access_token, user_email)."""
    base = api_base.rstrip("/")
    saved = load_cli_session()
    if saved and saved.get("api_base") == base:
        access = saved.get("access_token")
        refresh = saved.get("refresh_token")
        if isinstance(access, str) and access:
            try:
                with httpx.Client(timeout=30.0) as client:
                    me = client.get(
                        f"{base}/api/auth/me",
                        headers={"Authorization": f"Bearer {access}"},
                    )
                    if me.status_code == 200:
                        email = me.json().get("email", "")
                        print(f"[骞冲彴] 宸蹭娇鐢ㄤ繚瀛樼殑浼氳瘽鐧诲綍: {email}")
                        return access, email
                    if refresh and isinstance(refresh, str):
                        ref = client.post(f"{base}/api/auth/refresh", params={"token": refresh})
                        if ref.status_code == 200:
                            data = ref.json()
                            access = data["token"]
                            new_refresh = data.get("refresh_token") or refresh
                            save_cli_session(
                                {
                                    "api_base": base,
                                    "access_token": access,
                                    "refresh_token": new_refresh,
                                }
                            )
                            me2 = client.get(
                                f"{base}/api/auth/me",
                                headers={"Authorization": f"Bearer {access}"},
                            )
                            if me2.status_code == 200:
                                email = me2.json().get("email", "")
                                print(f"[骞冲彴] 宸插埛鏂颁护鐗屽苟鐧诲綍: {email}")
                                return access, email
            except httpx.RequestError as e:
                print(f"[WARN] 璇诲彇骞冲彴浼氳瘽澶辫触锛堝皢閲嶆柊鐧诲綍锛? {e}")

    print(f"\n[骞冲彴璁よ瘉] OpenAgentic 鏈嶅姟: {base}")
    print("璇峰厛鐧诲綍宸叉湁璐﹀彿锛屾垨娉ㄥ唽鏂拌处鍙凤紙闇€鏈嶅姟宸插惎鍔ㄤ笖鏁版嵁搴撳彲鐢級銆?)

    with httpx.Client(timeout=60.0) as client:
        while True:
            print("\n閫夋嫨: 1 鐧诲綍  |  2 娉ㄥ唽  |  q 閫€鍑?)
            choice = input("> ").strip().lower()
            if choice in {"q", "quit", "exit"}:
                print("宸查€€鍑恒€?)
                raise SystemExit(0)
            if choice not in {"1", "2"}:
                print("璇疯緭鍏?1銆? 鎴?q")
                continue
            email = input("閭: ").strip()
            if not email:
                print("閭涓嶈兘涓虹┖")
                continue
            password = getpass("瀵嗙爜: ")
            if len(password) < 6:
                print("瀵嗙爜鑷冲皯 6 浣?)
                continue
            if choice == "2":
                display_name = input("鏄剧ず鍚嶏紙鍙洖杞﹁烦杩囷級: ").strip() or None
                body: dict = {"email": email, "password": password}
                if display_name:
                    body["display_name"] = display_name
                try:
                    r = client.post(f"{base}/api/auth/register", json=body)
                except httpx.RequestError as e:
                    print(f"[ERROR] 鏃犳硶杩炴帴 {base}: {e}")
                    continue
                if r.status_code == 400 and "already" in (r.text or "").lower():
                    print("璇ラ偖绠卞凡娉ㄥ唽锛岃鏀圭敤 1 鐧诲綍銆?)
                    continue
            else:
                try:
                    r = client.post(
                        f"{base}/api/auth/login", json={"email": email, "password": password}
                    )
                except httpx.RequestError as e:
                    print(f"[ERROR] 鏃犳硶杩炴帴 {base}: {e}")
                    continue
            if r.status_code not in (200, 201):
                detail = ""
                try:
                    detail = r.json().get("detail", str(r.text))[:300]
                except Exception:
                    detail = (r.text or "")[:300]
                print(f"[ERROR] {r.status_code} {detail}")
                continue
            data = r.json()
            access = data["token"]
            refresh = data.get("refresh_token")
            me = client.get(
                f"{base}/api/auth/me",
                headers={"Authorization": f"Bearer {access}"},
            )
            if me.status_code != 200:
                print(f"[ERROR] 鐧诲綍鎴愬姛浣嗘棤娉曡鍙栫敤鎴蜂俊鎭? {me.status_code}")
                continue
            user_email = me.json().get("email", email)
            save_cli_session(
                {
                    "api_base": base,
                    "access_token": access,
                    "refresh_token": refresh,
                }
            )
            print(f"[骞冲彴] 鐧诲綍鎴愬姛: {user_email}")
            return access, user_email
