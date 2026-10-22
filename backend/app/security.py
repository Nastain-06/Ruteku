import uuid
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from . import cache
from .config import settings
from .db import get_db
from .models import User

bearer = HTTPBearer(auto_error=False)


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()  # NFR-06


DUMMY_HASH = hash_password("ruteku-dummy-password-anti-timing-attack")


def verify_password(p: str, h: str) -> bool:
    raw = p.encode("utf-8")
    if len(raw) > 72:
        return False
    try:
        return bcrypt.checkpw(raw, h.encode("utf-8"))
    except ValueError:
        return False


def create_token(user_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_hours)
    return jwt.encode({"sub": user_id, "jti": uuid.uuid4().hex, "exp": exp}, settings.jwt_secret, algorithm="HS256")


def current_claims(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if not cred:
        raise HTTPException(401, "Token tidak ada")
    try:
        c = jwt.decode(cred.credentials, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Token tidak valid atau kedaluwarsa")
    if cache.r.exists(f"blacklist:{c['jti']}"):
        raise HTTPException(401, "Sesi sudah berakhir")
    return c


def current_user(c: dict = Depends(current_claims), db: Session = Depends(get_db)) -> User:
    u = db.get(User, c["sub"])
    if not u or u.status != "active":
        raise HTTPException(401, "Akun tidak aktif")
    return u
