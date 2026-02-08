from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from kolayis.config import settings

# Engine: veritabanina baglantiyi yoneten nesne
# echo=False: SQL sorgulari artik logging sistemi uzerinden yonetiliyor
engine = create_engine(settings.DATABASE_URL, echo=False)

# SessionLocal: her istek icin yeni bir veritabani oturumu olusturur
# autocommit=False: degisiklikleri elle commit etmen gerekir
# autoflush=False: sorgu oncesi otomatik flush yapmaz
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Base: tum modellerin miras alacagi temel sinif
class Base(DeclarativeBase):
    pass


def get_db():
    """
    FastAPI dependency olarak kullanilir.
    Her istek icin yeni bir veritabani oturumu acar,
    istek bitince kapatir.

    Kullanim:
        @router.get("/")
        def endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
