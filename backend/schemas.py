"""API istek/yanıt şemaları (Pydantic).

ORM (models.py) veritabanı tarafıdır; bu dosya ise dışarıya açılan JSON
biçimleridir. Şifre hash'i gibi alanlar yanıt şemalarına ASLA konmaz.
"""

import re

from pydantic import BaseModel, field_validator

# Kullanıcı kendisi sadece bu rollerle kayıt olabilir; "admin" verilemez.
SIGNUP_ROLES = {"casual", "journalist"}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignupRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str = "casual"

    @field_validator("username")
    @classmethod
    def _username_ok(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Kullanıcı adı en az 3 karakter olmalı.")
        return v

    @field_validator("email")
    @classmethod
    def _email_ok(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Geçerli bir e-posta girin.")
        return v

    @field_validator("password")
    @classmethod
    def _password_ok(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Şifre en az 6 karakter olmalı.")
        return v

    @field_validator("role")
    @classmethod
    def _role_ok(cls, v: str) -> str:
        v = (v or "casual").strip().lower()
        if v not in SIGNUP_ROLES:
            raise ValueError("Rol 'casual' veya 'journalist' olmalı.")
        return v


class LoginRequest(BaseModel):
    # Kullanıcı adı VEYA e-posta ile giriş yapılabilir
    identifier: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_verified: bool

    class Config:
        from_attributes = True  # ORM nesnesinden doğrudan üretilebilsin


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
