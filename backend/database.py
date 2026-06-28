"""Veritabanı bağlantı katmanı (PostgreSQL).

Tek sorumluluğu: SQLAlchemy engine + session kurmak ve FastAPI'ye bir
`get_db` bağımlılığı (dependency) sağlamak. Kullanıcı modelleri/tabloları
ayrı bir dosyada (örn. models.py) tanımlanmalı ve buradaki `Base`'ten türemeli.

Bağlantı adresi iki şekilde verilebilir (.env dosyasından okunur):
  1. Tek satır DATABASE_URL, örn:
       DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/exasparagas
  2. Ya da parça parça POSTGRES_* değişkenleri (DATABASE_URL yoksa bunlardan
     kurulur): POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST,
     POSTGRES_PORT, POSTGRES_DB
"""

import os

from dotenv import load_dotenv, find_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# .env'i bu dosya tek başına çalıştırıldığında da yükle (find_dotenv proje
# kökündeki .env'i yukarı doğru arayarak bulur). main.py de ayrıca yükler.
load_dotenv(find_dotenv())


def _build_database_url() -> str:
    """DATABASE_URL varsa onu kullan; yoksa POSTGRES_* parçalarından kur."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url

    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    host = os.environ.get("POSTGRES_HOST")
    port = os.environ.get("POSTGRES_PORT")
    db = os.environ.get("POSTGRES_DB")
    # psycopg = psycopg v3 sürücüsü (requirements.txt'teki psycopg[binary])
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


DATABASE_URL = _build_database_url()

# pool_pre_ping: havuzdaki ölü (timeout'a uğramış) bağlantıları kullanmadan
# önce yoklar; "server closed the connection unexpectedly" hatalarını önler.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Her istek kendi session'ını alır (aşağıdaki get_db ile).
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Tüm ORM modelleri (User vb.) bu Base'ten türemeli ki create_all onları görsün.
Base = declarative_base()


def get_db():
    """FastAPI dependency: istek başına bir DB session açar ve sonunda kapatır.

    Kullanım:
        @app.post("/login")
        def login(..., db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Base'e kayıtlı tüm tabloları oluşturur (yoksa).

    Modelleri (örn. models.py) import ETTİKTEN sonra çağır ki tablolar Base'e
    kayıtlı olsun. Uygulama açılışında bir kez çalıştırman yeterli:
        from . import models  # noqa: F401  (modellerin Base'e kaydolması için)
        init_db()
    """
    Base.metadata.create_all(bind=engine)
