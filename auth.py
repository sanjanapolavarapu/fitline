"""Local accounts for FitLine — hashed passwords + optional saved resume per user."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent
USERS_FILE = ROOT / ".fitline_users.json"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    ).hex()
    return f"{salt}${digest}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return secrets.compare_digest(_hash_password(password, salt), stored)


def _load_users() -> dict[str, dict]:
    if not USERS_FILE.exists():
        return {}
    try:
        data = json.loads(USERS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_users(users: dict[str, dict]) -> None:
    USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def admin_email() -> str:
    return normalize_email(os.environ.get("FITLINE_ADMIN_EMAIL", ""))


def is_admin(email: str) -> bool:
    admin = admin_email()
    return bool(admin and normalize_email(email) == admin)


def count_users() -> int:
    return len(_load_users())


def create_account(email: str, password: str, name: str = "") -> tuple[bool, str]:
    email = normalize_email(email)
    if not email or not EMAIL_RE.match(email):
        return False, "Enter a valid email address."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    users = _load_users()
    if email in users:
        return False, "An account with that email already exists. Try logging in."
    users[email] = {
        "name": name.strip() or email.split("@")[0],
        "password_hash": _hash_password(password),
        "created_at": _now_iso(),
        "last_login": _now_iso(),
        "login_count": 1,
    }
    _save_users(users)
    return True, "Account created — you're signed in."


def authenticate(email: str, password: str) -> tuple[bool, str, dict | None]:
    email = normalize_email(email)
    users = _load_users()
    user = users.get(email)
    if not user or not _verify_password(password, user.get("password_hash", "")):
        return False, "Invalid email or password.", None
    user["last_login"] = _now_iso()
    user["login_count"] = int(user.get("login_count") or 0) + 1
    users[email] = user
    _save_users(users)
    return True, "Welcome back!", {"email": email, "name": user.get("name") or email.split("@")[0]}


def save_user_work(email: str, work: dict[str, Any]) -> None:
    """Save resume + chat for this account so they can pick up later."""
    email = normalize_email(email)
    users = _load_users()
    if email not in users:
        return
    users[email]["saved_work"] = {
        **work,
        "updated_at": _now_iso(),
    }
    _save_users(users)


def load_user_work(email: str) -> dict[str, Any] | None:
    email = normalize_email(email)
    user = _load_users().get(email)
    if not user:
        return None
    saved = user.get("saved_work")
    return saved if isinstance(saved, dict) else None


def clear_user_work(email: str) -> None:
    email = normalize_email(email)
    users = _load_users()
    if email not in users:
        return
    users[email].pop("saved_work", None)
    _save_users(users)
