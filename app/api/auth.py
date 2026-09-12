"""轻量演示级鉴权（内存存储）。

项目定位为模拟数据、不接真实账号系统，因此这里提供一个进程内的演示级
用户体系：注册 / 登录接口，密码以 PBKDF2 哈希存储，登录签发一个不透明
token。数据保存在内存，进程重启后不保留，仅用于前端登录/注册演示与将
登录名关联到会话及模拟画像。

安全说明：这不是生产级鉴权，不做邮箱验证、找回密码、会话持久化等。
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from typing import Optional

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/auth", tags=["auth"])

# 进程内用户表：username -> {salt, hash}；以及 token -> username。
_USERS: dict[str, dict[str, bytes]] = {}
_TOKENS: dict[str, str] = {}


def _hash_password(password: str, salt: bytes) -> bytes:
    """用 PBKDF2-HMAC-SHA256 派生密码哈希。"""
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)


class Credentials(BaseModel):
    """注册 / 登录请求体。"""

    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=4, max_length=128)


class AuthResult(BaseModel):
    """鉴权成功响应。"""

    token: str
    username: str


def _err(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": message})


@router.post("/register")
async def register(body: Credentials):
    """注册新用户。用户名已存在时返回 409。"""
    username = body.username.strip()
    if username in _USERS:
        return _err(409, "Username already exists")
    salt = os.urandom(16)
    _USERS[username] = {"salt": salt, "hash": _hash_password(body.password, salt)}
    token = secrets.token_urlsafe(24)
    _TOKENS[token] = username
    return AuthResult(token=token, username=username)


@router.post("/login")
async def login(body: Credentials):
    """登录已有用户。用户名或密码错误时返回 401。"""
    username = body.username.strip()
    record = _USERS.get(username)
    if record is None:
        return _err(401, "Invalid username or password")
    candidate = _hash_password(body.password, record["salt"])
    if not hmac.compare_digest(candidate, record["hash"]):
        return _err(401, "Invalid username or password")
    token = secrets.token_urlsafe(24)
    _TOKENS[token] = username
    return AuthResult(token=token, username=username)


def resolve_user(authorization: Optional[str]) -> Optional[str]:
    """从 Authorization: Bearer <token> 头解析出用户名，无效返回 None。"""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return _TOKENS.get(parts[1])


@router.get("/me")
async def me(authorization: Optional[str] = Header(default=None)):
    """返回当前 token 对应的用户名，未登录返回 401。"""
    username = resolve_user(authorization)
    if username is None:
        return _err(401, "Not authenticated")
    return {"username": username}
