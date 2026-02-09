"""Ozel alan (Custom Field) servisi."""
import uuid

from sqlalchemy.orm import Session

from kolayis.models.custom_field import CustomFieldDefinition, CustomFieldValue


# ---------------------------------------------------------------------------
# Alan Tanimlari (Definitions)
# ---------------------------------------------------------------------------

def get_definitions(
    db: Session, owner_id: uuid.UUID, entity_type: str | None = None
) -> list[CustomFieldDefinition]:
    """Kullanicinin tanimladigi ozel alanlari getir."""
    q = db.query(CustomFieldDefinition).filter(
        CustomFieldDefinition.owner_id == owner_id,
        CustomFieldDefinition.is_active == True,
    )
    if entity_type:
        q = q.filter(CustomFieldDefinition.entity_type == entity_type)
    return q.order_by(CustomFieldDefinition.position, CustomFieldDefinition.created_at).all()


def get_definition(db: Session, owner_id: uuid.UUID, field_id: uuid.UUID) -> CustomFieldDefinition | None:
    return db.query(CustomFieldDefinition).filter(
        CustomFieldDefinition.id == field_id,
        CustomFieldDefinition.owner_id == owner_id,
    ).first()


def create_definition(
    db: Session, owner_id: uuid.UUID,
    entity_type: str, field_name: str, field_type: str,
    options: list[str] | None = None,
    is_required: bool = False,
) -> CustomFieldDefinition:
    """Yeni ozel alan tanimla."""
    # Sira numarasi: mevcut en buyuk + 1
    max_pos = db.query(CustomFieldDefinition.position).filter(
        CustomFieldDefinition.owner_id == owner_id,
        CustomFieldDefinition.entity_type == entity_type,
    ).order_by(CustomFieldDefinition.position.desc()).first()
    pos = (max_pos[0] + 1) if max_pos else 0

    field = CustomFieldDefinition(
        owner_id=owner_id,
        entity_type=entity_type,
        field_name=field_name,
        field_type=field_type,
        options=options,
        is_required=is_required,
        position=pos,
    )
    db.add(field)
    db.commit()
    db.refresh(field)
    return field


def update_definition(
    db: Session, owner_id: uuid.UUID, field_id: uuid.UUID, **kwargs
) -> CustomFieldDefinition | None:
    field = get_definition(db, owner_id, field_id)
    if not field:
        return None
    for k, v in kwargs.items():
        if hasattr(field, k):
            setattr(field, k, v)
    db.commit()
    db.refresh(field)
    return field


def delete_definition(db: Session, owner_id: uuid.UUID, field_id: uuid.UUID) -> bool:
    field = get_definition(db, owner_id, field_id)
    if not field:
        return False
    # Iliskili degerleri de sil
    db.query(CustomFieldValue).filter(CustomFieldValue.field_id == field_id).delete()
    db.delete(field)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Alan Degerleri (Values)
# ---------------------------------------------------------------------------

def get_values_for_entity(
    db: Session, owner_id: uuid.UUID, entity_type: str, entity_id: uuid.UUID
) -> dict[uuid.UUID, str]:
    """Bir varligin tum ozel alan degerlerini dict olarak dondur {field_id: value}."""
    definitions = get_definitions(db, owner_id, entity_type)
    field_ids = [d.id for d in definitions]
    if not field_ids:
        return {}

    values = db.query(CustomFieldValue).filter(
        CustomFieldValue.field_id.in_(field_ids),
        CustomFieldValue.entity_id == entity_id,
    ).all()

    return {v.field_id: v.value for v in values}


def get_fields_with_values(
    db: Session, owner_id: uuid.UUID, entity_type: str, entity_id: uuid.UUID
) -> list[dict]:
    """Alan tanimlarini degerleriyle birlikte dondur."""
    definitions = get_definitions(db, owner_id, entity_type)
    values = get_values_for_entity(db, owner_id, entity_type, entity_id)

    result = []
    for d in definitions:
        result.append({
            "id": d.id,
            "field_name": d.field_name,
            "field_type": d.field_type,
            "options": d.options,
            "is_required": d.is_required,
            "value": values.get(d.id, ""),
        })
    return result


def save_values(
    db: Session, entity_id: uuid.UUID, field_values: dict[str, str]
) -> None:
    """Bir varlik icin ozel alan degerlerini kaydet/guncelle.
    field_values: {field_id_str: value}
    """
    for field_id_str, value in field_values.items():
        try:
            fid = uuid.UUID(field_id_str)
        except ValueError:
            continue

        existing = db.query(CustomFieldValue).filter(
            CustomFieldValue.field_id == fid,
            CustomFieldValue.entity_id == entity_id,
        ).first()

        if existing:
            existing.value = value
        else:
            db.add(CustomFieldValue(
                field_id=fid,
                entity_id=entity_id,
                value=value,
            ))

    db.commit()
