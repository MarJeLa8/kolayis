import uuid

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from kolayis.models.note import Note
from kolayis.schemas.note import NoteCreate, NoteUpdate
from kolayis.services.customer import get_customer


def get_notes(
    db: Session, customer_id: uuid.UUID, owner_id: uuid.UUID
) -> list[Note]:
    """Bir musterinin tum notlarini getir. Once musteri sahipligini kontrol eder."""
    # Musteri bu kullaniciya ait mi?
    get_customer(db, customer_id, owner_id)

    return (
        db.query(Note)
        .filter(Note.customer_id == customer_id)
        .order_by(Note.created_at.desc())
        .all()
    )


def get_note(
    db: Session, customer_id: uuid.UUID, note_id: uuid.UUID, owner_id: uuid.UUID
) -> Note:
    """Tek bir notu getir. Musteri sahipligini kontrol eder."""
    get_customer(db, customer_id, owner_id)

    note = db.query(Note).filter(
        Note.id == note_id,
        Note.customer_id == customer_id,
    ).first()

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not bulunamadi",
        )
    return note


def create_note(
    db: Session, customer_id: uuid.UUID, owner_id: uuid.UUID, data: NoteCreate
) -> Note:
    """Musteriye yeni not ekle."""
    get_customer(db, customer_id, owner_id)

    note = Note(
        customer_id=customer_id,
        author_id=owner_id,
        **data.model_dump(),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def update_note(
    db: Session,
    customer_id: uuid.UUID,
    note_id: uuid.UUID,
    owner_id: uuid.UUID,
    data: NoteUpdate,
) -> Note:
    """Notu guncelle."""
    note = get_note(db, customer_id, note_id, owner_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(note, field, value)

    db.commit()
    db.refresh(note)
    return note


def delete_note(
    db: Session, customer_id: uuid.UUID, note_id: uuid.UUID, owner_id: uuid.UUID
) -> None:
    """Notu sil."""
    note = get_note(db, customer_id, note_id, owner_id)
    db.delete(note)
    db.commit()
