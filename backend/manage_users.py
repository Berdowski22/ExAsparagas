"""Küçük yönetim aracı: admin oluştur, gazeteci doğrula, kullanıcıları listele.

Adminler kendi kendine kayıt OLAMAZ (güvenlik) — ilk admini buradan oluştur.

Kullanım (backend klasöründen):
  python manage_users.py create-admin <username> <email> <password>
  python manage_users.py verify <username_or_email>     # gazeteciyi onayla
  python manage_users.py set-role <username_or_email> <role>
  python manage_users.py list
"""

import sys

from database import SessionLocal, init_db
from models import User
from security import hash_password


def _find(db, ident):
    return (
        db.query(User)
        .filter((User.username == ident) | (User.email == ident.lower()))
        .first()
    )


def create_admin(username, email, password):
    db = SessionLocal()
    try:
        if _find(db, username) or _find(db, email):
            print("[X] This username or email already exists.")
            return
        admin = User(
            username=username,
            email=email.lower(),
            hashed_password=hash_password(password),
            role="admin",
            is_verified=True,
        )
        db.add(admin)
        db.commit()
        print(f"[OK] Admin created: {username} ({email})")
    finally:
        db.close()


def verify(ident):
    db = SessionLocal()
    try:
        user = _find(db, ident)
        if not user:
            print("[X] User not found.")
            return
        user.is_verified = True
        db.commit()
        print(f"[OK] Verified: {user.username} (role: {user.role})")
    finally:
        db.close()


def set_role(ident, role):
    if role not in ("admin", "journalist", "casual"):
        print("[X] Role must be 'admin', 'journalist' or 'casual'.")
        return
    db = SessionLocal()
    try:
        user = _find(db, ident)
        if not user:
            print("[X] User not found.")
            return
        user.role = role
        if role in ("admin", "casual"):
            user.is_verified = role == "admin"
        db.commit()
        print(f"[OK] {user.username} role set to '{role}'.")
    finally:
        db.close()


def list_users():
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.id).all()
        if not users:
            print("(kayıtlı kullanıcı yok)")
            return
        print(f"{'id':>3}  {'username':16} {'role':11} {'verified':8} email")
        for u in users:
            print(f"{u.id:>3}  {u.username:16} {u.role:11} {str(u.is_verified):8} {u.email}")
    finally:
        db.close()


def main():
    init_db()
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    cmd = args[0]
    if cmd == "create-admin" and len(args) == 4:
        create_admin(args[1], args[2], args[3])
    elif cmd == "verify" and len(args) == 2:
        verify(args[1])
    elif cmd == "set-role" and len(args) == 3:
        set_role(args[1], args[2])
    elif cmd == "list" and len(args) == 1:
        list_users()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
