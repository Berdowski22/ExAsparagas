"""Güvenlik yardımcıları: şifre hash'leme, JWT üret/doğrula, mevcut kullanıcı.

- Şifreler bcrypt ile hash'lenir (düz metin asla saklanmaz/loglanmaz).
- Giriş sonrası kullanıcıya imzalı bir JWT verilir; sonraki isteklerde
  Authorization: Bearer <token> başlığıyla gönderilir.
"""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import find_dotenv, load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
from models import User

load_dotenv(find_dotenv())

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-insecure-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 saat

# Authorization: Bearer <token> başlığını okur
_bearer = HTTPBearer(auto_error=False)


# --- Şifre hash'leme (bcrypt) ---
def hash_password(plain: str) -> str:
    # bcrypt en fazla 72 byte işler; uzun şifreleri güvenle kısalt
    pw = plain.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- JWT ---
def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),          # token'ın sahibi (kullanıcı id)
        "username": user.username,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token süresi doldu, tekrar giriş yapın.")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Geçersiz token.")


# --- FastAPI dependency'leri ---
def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Token'ı doğrula ve karşılık gelen kullanıcıyı döndür."""
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Giriş gerekli.")
    payload = _decode_token(creds.credentials)
    user = db.query(User).filter(User.id == int(payload.get("sub", 0))).first()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Kullanıcı bulunamadı veya pasif.")
    return user


def require_role(*allowed_roles: str):
    """Belirli rolleri zorunlu kılan bir dependency üretir.

    Örn: Depends(require_role("admin")) sadece adminlere izin verir.
    """
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu işlem için yetkiniz yok.")
        return user
    return checker
