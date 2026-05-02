from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from cryptography.fernet import Fernet
from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def _jwt_secret() -> str:
    return os.getenv("JWT_SECRET") or os.getenv("APP_SECRET_KEY") or "writerlm-dev-secret-change-me"


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    expire_minutes = expires_minutes or int(os.getenv("JWT_EXPIRES_MINUTES", "1440"))
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _jwt_secret(), algorithms=["HS256"])


def _fernet_key() -> bytes:
    configured = os.getenv("APP_ENCRYPTION_KEY", "").strip()
    if configured:
        return configured.encode("utf-8")
    digest = hashlib.sha256(_jwt_secret().encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(value: str) -> str:
    return Fernet(_fernet_key()).encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    return Fernet(_fernet_key()).decrypt(value.encode("utf-8")).decode("utf-8")


def mask_secret(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    if len(cleaned) <= 8:
        return "••••"
    return f"{cleaned[:4]}••••{cleaned[-4:]}"
