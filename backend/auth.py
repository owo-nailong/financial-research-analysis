"""
Authentication and role-based access control (admin / user).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import AUTH_CONFIG

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

# In-memory user store seeded from config (also synced to DB when available)
_USERS: dict[str, dict] = {}


def _hash_password(password: str, salt: str = "fras-salt") -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def init_default_users() -> None:
    """Seed default admin and user accounts."""
    global _USERS
    _USERS = {
        AUTH_CONFIG["admin_username"]: {
            "username": AUTH_CONFIG["admin_username"],
            "password_hash": _hash_password(AUTH_CONFIG["admin_password"]),
            "role": "admin",
            "display_name": "管理员",
        },
        AUTH_CONFIG["user_username"]: {
            "username": AUTH_CONFIG["user_username"],
            "password_hash": _hash_password(AUTH_CONFIG["user_password"]),
            "role": "user",
            "display_name": "普通用户",
        },
    }
    logger.info("[Auth] Default users loaded: admin=%s user=%s",
                AUTH_CONFIG["admin_username"], AUTH_CONFIG["user_username"])


def verify_password(username: str, password: str) -> Optional[dict]:
    user = _USERS.get(username)
    if not user:
        return None
    if not hmac.compare_digest(user["password_hash"], _hash_password(password)):
        return None
    return {"username": user["username"], "role": user["role"], "display_name": user["display_name"]}


def change_own_password(username: str, old_password: str, new_password: str) -> dict:
    user = _USERS.get(username)
    if not user:
        raise ValueError("用户不存在")
    if not hmac.compare_digest(user["password_hash"], _hash_password(old_password)):
        raise ValueError("原密码错误")
    if not new_password or len(new_password) < 6:
        raise ValueError("新密码至少 6 位")
    user["password_hash"] = _hash_password(new_password)
    return {"username": username, "role": user["role"]}


def admin_set_password(username: str, new_password: str) -> dict:
    user = _USERS.get(username)
    if not user:
        raise ValueError("用户不存在")
    if not new_password or len(new_password) < 6:
        raise ValueError("新密码至少 6 位")
    user["password_hash"] = _hash_password(new_password)
    return {"username": username, "role": user["role"]}


def create_token(username: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=AUTH_CONFIG["token_expire_hours"])
    payload = {
        "sub": username,
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, AUTH_CONFIG["jwt_secret"], algorithm=AUTH_CONFIG["jwt_algorithm"])


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            AUTH_CONFIG["jwt_secret"],
            algorithms=[AUTH_CONFIG["jwt_algorithm"]],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    username = payload.get("sub")
    role = payload.get("role", "user")
    if username not in _USERS:
        raise HTTPException(status_code=401, detail="User not found")
    return {"username": username, "role": role, "display_name": _USERS[username]["display_name"]}


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    if credentials is None or not credentials.credentials:
        return None
    try:
        return get_current_user(credentials)
    except HTTPException:
        return None


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def require_user(user: dict = Depends(get_current_user)) -> dict:
    """Any authenticated user (admin or user)."""
    return user


def list_users_safe() -> list[dict]:
    return [
        {"username": u["username"], "role": u["role"], "display_name": u["display_name"]}
        for u in _USERS.values()
    ]


def create_user(username: str, password: str, role: str = "user", display_name: str = "") -> dict:
    if role not in ("admin", "user"):
        raise ValueError("role must be admin or user")
    if username in _USERS:
        raise ValueError("username already exists")
    if not password or len(password) < 6:
        raise ValueError("密码至少 6 位")
    label = (display_name or "").strip() or (
        "管理员" if role == "admin" else "普通用户"
    )
    _USERS[username] = {
        "username": username,
        "password_hash": _hash_password(password),
        "role": role,
        "display_name": label,
    }
    return {"username": username, "role": role, "display_name": label}


# Initialize on import
init_default_users()
