"""Kimlik doğrulama uç noktaları (signup / login / me) ve admin onayı.

main.py bu router'ı app.include_router(auth.router) ile dahil eder.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import LoginRequest, SignupRequest, TokenResponse, UserOut
from security import (
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    # Kullanıcı adı / e-posta benzersiz mi?
    exists = (
        db.query(User)
        .filter((User.username == body.username) | (User.email == body.email))
        .first()
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu kullanıcı adı veya e-posta zaten kayıtlı.")

    # Gazeteci olarak kayıt olunsa bile is_verified=False kalır (admin onaylar).
    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    ident = body.identifier.strip().lower()
    user = (
        db.query(User)
        .filter((User.username == body.identifier.strip()) | (User.email == ident))
        .first()
    )
    # Kullanıcı yok ya da şifre yanlış — aynı genel mesaj (kullanıcı sızdırma yok)
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Kullanıcı adı/e-posta veya şifre hatalı.")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Hesap pasif durumda.")

    token = create_access_token(user)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    """Token'a karşılık gelen oturum sahibini döndürür."""
    return UserOut.model_validate(current)


@router.post("/admin/verify/{user_id}", response_model=UserOut)
def verify_journalist(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    """Admin, bir gazeteci hesabını doğrular (is_verified=True)."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kullanıcı bulunamadı.")
    if user.role != "journalist":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bu kullanıcı gazeteci değil.")
    user.is_verified = True
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
