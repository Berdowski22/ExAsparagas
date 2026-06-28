"""Veritabanı modelleri (tablolar).

Her sınıf bir PostgreSQL tablosuna karşılık gelir. database.py'deki Base'ten
türerler; init_db() çağrıldığında SQLAlchemy bu sınıflara bakıp tabloları
otomatik oluşturur — elle CREATE TABLE yazmaya gerek yok.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    # Giriş bilgileri
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    # Şifre ASLA düz metin tutulmaz; bcrypt ile hash'lenmiş hali saklanır.
    hashed_password = Column(String(255), nullable=False)

    # Rol: "admin" | "journalist" | "casual"
    role = Column(String(20), nullable=False, default="casual")

    # Gazeteci doğrulaması: rol "journalist" olsa bile admin onaylayana kadar
    # is_verified False kalır. Doğrulama akışını sonra netleştireceğiz.
    is_verified = Column(Boolean, nullable=False, default=False)

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<User id={self.id} username={self.username!r} role={self.role!r}>"
