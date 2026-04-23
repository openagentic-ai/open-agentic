"""CLI session file and HTTP login/register against OpenAgentic API."""

from __future__ import annotations

import json
import os
from getpass import getpass
from pathlib import Path

import httpx


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
    if os.name != "nt":
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass


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
                        print(f"[平台] 已使用保存的会话登录: {email}")
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
                                print(f"[平台] 已刷新令牌并登录: {email}")
                                return access, email
            except httpx.RequestError as e:
                print(f"[WARN] 读取平台会话失败（将重新登录）: {e}")

    print(f"\n[平台认证] OpenAgentic 服务: {base}")
    print("请先登录已有账号，或注册新账号（需服务已启动且数据库可用）。")

    with httpx.Client(timeout=60.0) as client:
        while True:
            print("\n选择: 1 登录  |  2 注册  |  q 退出")
            choice = input("> ").strip().lower()
            if choice in {"q", "quit", "exit"}:
                print("已退出。")
                raise SystemExit(0)
            if choice not in {"1", "2"}:
                print("请输入 1、2 或 q")
                continue
            email = input("邮箱: ").strip()
            if not email:
                print("邮箱不能为空")
                continue
            password = getpass("密码: ")
            if len(password) < 6:
                print("密码至少 6 位")
                continue
            if choice == "2":
                display_name = input("显示名（可回车跳过）: ").strip() or None
                body: dict = {"email": email, "password": password}
                if display_name:
                    body["display_name"] = display_name
                try:
                    r = client.post(f"{base}/api/auth/register", json=body)
                except httpx.RequestError as e:
                    print(f"[ERROR] 无法连接 {base}: {e}")
                    continue
                if r.status_code == 400 and "already" in (r.text or "").lower():
                    print("该邮箱已注册，请改用 1 登录。")
                    continue
            else:
                try:
                    r = client.post(
                        f"{base}/api/auth/login", json={"email": email, "password": password}
                    )
                except httpx.RequestError as e:
                    print(f"[ERROR] 无法连接 {base}: {e}")
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
                print(f"[ERROR] 登录成功但无法读取用户信息: {me.status_code}")
                continue
            user_email = me.json().get("email", email)
            save_cli_session(
                {
                    "api_base": base,
                    "access_token": access,
                    "refresh_token": refresh,
                }
            )
            print(f"[平台] 登录成功: {user_email}")
            return access, user_email
