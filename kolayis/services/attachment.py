import uuid
import os
import logging
from pathlib import Path

from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile, status

from kolayis.models.attachment import Attachment

logger = logging.getLogger(__name__)

# Yuklenen dosyalarin saklanacagi klasor (proje kokunde)
UPLOAD_DIR = Path("uploads")

# Maksimum dosya boyutu: 10 MB (byte cinsinden)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Izin verilen dosya uzantilari
ALLOWED_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png",
    ".doc", ".docx", ".xls", ".xlsx",
    ".csv", ".txt",
}

# Uzanti -> MIME tipi eslemesi
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
    ".txt": "text/plain",
}


def _ensure_upload_dir(owner_id: uuid.UUID) -> Path:
    """
    Kullaniciya ozel yukleme klasorunu olustur.
    Yapi: uploads/<owner_id>/
    """
    user_dir = UPLOAD_DIR / str(owner_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _validate_file(file: UploadFile, file_size: int) -> str:
    """
    Dosya uzantisini ve boyutunu kontrol eder.
    Gecerli uzantiyi dondurur, gecersizse HTTPException firlatir.
    """
    # Dosya adindaki uzantiyi al
    original_name = file.filename or "unknown"
    ext = Path(original_name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gecersiz dosya tipi: '{ext}'. "
                   f"Izin verilen tipler: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    if file_size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        file_mb = file_size / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dosya boyutu cok buyuk: {file_mb:.1f} MB. "
                   f"Maksimum: {max_mb:.0f} MB",
        )

    return ext


def get_attachments(
    db: Session,
    owner_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
) -> list[Attachment]:
    """
    Bir varliga ait tum dosya eklerini getir.
    Sadece kullanicinin kendi yukledigi dosyalar dondurulur.
    """
    return (
        db.query(Attachment)
        .filter(
            Attachment.owner_id == owner_id,
            Attachment.entity_type == entity_type,
            Attachment.entity_id == entity_id,
        )
        .order_by(Attachment.created_at.desc())
        .all()
    )


async def save_attachment(
    db: Session,
    owner_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    file: UploadFile,
    description: str | None = None,
) -> Attachment:
    """
    Dosya ekini diske kaydet ve veritabanina kayit olustur.

    Guvenlik onlemleri:
    - Dosya adi UUID ile degistirilir (path traversal onlemi)
    - Uzanti kontrolu yapilir
    - Boyut kontrolu yapilir
    """
    # Dosya icerigini oku
    content = await file.read()
    file_size = len(content)

    # Validasyon
    ext = _validate_file(file, file_size)

    # Guvenli dosya adi olustur: UUID + orijinal uzanti
    safe_filename = f"{uuid.uuid4()}{ext}"
    original_filename = file.filename or "unknown"

    # MIME tipini belirle
    mime_type = MIME_TYPES.get(ext, "application/octet-stream")

    # Kullanici klasorunu olustur ve dosyayi kaydet
    user_dir = _ensure_upload_dir(owner_id)
    file_path = user_dir / safe_filename

    try:
        with open(file_path, "wb") as f:
            f.write(content)
    except OSError as e:
        logger.error(f"Dosya yazma hatasi: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dosya kaydedilemedi. Lutfen tekrar deneyin.",
        )

    # Veritabani kaydini olustur
    attachment = Attachment(
        owner_id=owner_id,
        entity_type=entity_type,
        entity_id=entity_id,
        filename=safe_filename,
        original_filename=original_filename,
        file_size=file_size,
        mime_type=mime_type,
        description=description,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    logger.info(
        f"Dosya yuklendi: {original_filename} -> {safe_filename} "
        f"({file_size} byte, {entity_type}/{entity_id})"
    )

    return attachment


def delete_attachment(
    db: Session,
    attachment_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> bool:
    """
    Dosya ekini hem veritabanindan hem diskten sil.
    Sadece dosyayi yukleyen kullanici silebilir.
    Basarili ise True, bulunamazsa False dondurur.
    """
    attachment = db.query(Attachment).filter(
        Attachment.id == attachment_id,
        Attachment.owner_id == owner_id,
    ).first()

    if not attachment:
        return False

    # Diskteki dosyayi sil
    file_path = UPLOAD_DIR / str(owner_id) / attachment.filename
    try:
        if file_path.exists():
            os.remove(file_path)
            logger.info(f"Dosya silindi: {file_path}")
        else:
            logger.warning(f"Silinecek dosya bulunamadi: {file_path}")
    except OSError as e:
        logger.error(f"Dosya silme hatasi: {e}")
        # Disk hatasi olsa bile veritabani kaydini sil

    # Veritabani kaydini sil
    db.delete(attachment)
    db.commit()

    return True


def get_attachment_file(
    db: Session,
    attachment_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> tuple[Path, str, str] | None:
    """
    Dosya indirme icin dosya yolunu, orijinal adini ve MIME tipini dondurur.
    Dosya bulunamazsa veya kullaniciya ait degilse None dondurur.

    Returns:
        (filepath, original_filename, mime_type) veya None
    """
    attachment = db.query(Attachment).filter(
        Attachment.id == attachment_id,
        Attachment.owner_id == owner_id,
    ).first()

    if not attachment:
        return None

    file_path = UPLOAD_DIR / str(owner_id) / attachment.filename

    if not file_path.exists():
        logger.warning(f"Veritabaninda kayit var ama dosya bulunamadi: {file_path}")
        return None

    return (file_path, attachment.original_filename, attachment.mime_type)
