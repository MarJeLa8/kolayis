import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from kolayis.database import get_db
from kolayis.dependencies import get_current_user
from kolayis.models.user import User
from kolayis.schemas.note import NoteCreate, NoteUpdate, NoteResponse
from kolayis.services import note as note_service

router = APIRouter()


@router.get("/{customer_id}/notes", response_model=list[NoteResponse])
def list_notes(
    customer_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Bir musterinin tum gorusme notlarini listele."""
    return note_service.get_notes(
        db=db,
        customer_id=customer_id,
        owner_id=current_user.id,
    )


@router.post(
    "/{customer_id}/notes",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_note(
    customer_id: uuid.UUID,
    data: NoteCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Musteriye yeni gorusme notu ekle."""
    return note_service.create_note(
        db=db,
        customer_id=customer_id,
        owner_id=current_user.id,
        data=data,
    )


@router.get("/{customer_id}/notes/{note_id}", response_model=NoteResponse)
def get_note(
    customer_id: uuid.UUID,
    note_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Tek bir gorusme notunu getir."""
    return note_service.get_note(
        db=db,
        customer_id=customer_id,
        note_id=note_id,
        owner_id=current_user.id,
    )


@router.put("/{customer_id}/notes/{note_id}", response_model=NoteResponse)
def update_note(
    customer_id: uuid.UUID,
    note_id: uuid.UUID,
    data: NoteUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Gorusme notunu guncelle."""
    return note_service.update_note(
        db=db,
        customer_id=customer_id,
        note_id=note_id,
        owner_id=current_user.id,
        data=data,
    )


@router.delete(
    "/{customer_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_note(
    customer_id: uuid.UUID,
    note_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Gorusme notunu sil."""
    note_service.delete_note(
        db=db,
        customer_id=customer_id,
        note_id=note_id,
        owner_id=current_user.id,
    )
