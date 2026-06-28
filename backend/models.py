"""Veritabanı modelleri (tablolar).

Her sınıf bir PostgreSQL tablosuna karşılık gelir. database.py'deki Base'ten
türerler; init_db() çağrıldığında SQLAlchemy bu sınıflara bakıp tabloları
otomatik oluşturur — elle CREATE TABLE yazmaya gerek yok.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

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


class Post(Base):
    """Bir kullanıcının blog'da paylaştığı AI analiz çıktısı."""

    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    news_text = Column(Text, nullable=False)          # analiz edilen haber metni
    verdict = Column(String(40))                       # "Likely Real" vb. (hızlı gösterim için)
    result_json = Column(Text, nullable=False)         # tam analiz sonucu (JSON, yeniden çizmek için)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    author = relationship("User")
    verifications = relationship(
        "PostVerification", back_populates="post", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Post id={self.id} author_id={self.author_id} verdict={self.verdict!r}>"


class PostVerification(Base):
    """Bir gazetecinin bir gönderiyi doğru/yanlış olarak oylaması.

    (post_id, journalist_id) benzersizdir: her gazeteci bir gönderiye tek oy verir
    (oyunu değiştirebilir).
    """

    __tablename__ = "post_verifications"
    __table_args__ = (UniqueConstraint("post_id", "journalist_id", name="uq_post_journalist"),)

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    journalist_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    is_correct = Column(Boolean, nullable=False)       # True = doğru, False = yanlış
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    post = relationship("Post", back_populates="verifications")
    journalist = relationship("User")
