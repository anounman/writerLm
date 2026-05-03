from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from web.backend.database import get_db
from web.backend.models import User
from web.backend.security import decode_access_token, decode_clerk_session_token, password_hash


bearer_scheme = HTTPBearer(auto_error=False)


def _safe_clerk_email(payload: dict) -> str:
    for key in ("email", "primary_email", "email_address", "preferred_email"):
        value = str(payload.get(key) or "").strip().lower()
        if "@" in value:
            return value
    subject = str(payload.get("sub") or "user").strip().lower()
    safe_subject = "".join(char if char.isalnum() else "-" for char in subject).strip("-") or "user"
    return f"{safe_subject[:80]}@clerk-user.local"


def _clerk_user(db: Session, payload: dict) -> User:
    email = _safe_clerk_email(payload)
    user = db.query(User).filter(User.email == email).first()
    if user is not None:
        return user

    subject = str(payload.get("sub") or email)
    user = User(
        email=email,
        password_hash=password_hash(f"clerk:{subject}"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except Exception:
        try:
            clerk_payload = decode_clerk_session_token(credentials.credentials)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.") from exc
        return _clerk_user(db, clerk_payload)

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists.")
    return user
