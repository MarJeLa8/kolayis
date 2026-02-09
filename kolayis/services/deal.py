"""Satis firsati (Deal) ve Pipeline servisi."""
import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from kolayis.models.deal import Deal, DealStage

logger = logging.getLogger(__name__)

# Varsayilan pipeline asamalari
DEFAULT_STAGES = [
    {"name": "Lead", "color": "#3b82f6", "position": 0, "is_closed": False, "is_won": False},
    {"name": "Iletisim", "color": "#8b5cf6", "position": 1, "is_closed": False, "is_won": False},
    {"name": "Teklif", "color": "#f59e0b", "position": 2, "is_closed": False, "is_won": False},
    {"name": "Muzakere", "color": "#f97316", "position": 3, "is_closed": False, "is_won": False},
    {"name": "Kazanildi", "color": "#22c55e", "position": 4, "is_closed": True, "is_won": True},
    {"name": "Kaybedildi", "color": "#ef4444", "position": 5, "is_closed": True, "is_won": False},
]


def ensure_default_stages(db: Session, owner_id: uuid.UUID) -> list[DealStage]:
    """Kullanicinin pipeline asamalari yoksa varsayilanlari olustur."""
    stages = get_stages(db, owner_id)
    if stages:
        return stages

    for s in DEFAULT_STAGES:
        stage = DealStage(
            owner_id=owner_id,
            name=s["name"],
            color=s["color"],
            position=s["position"],
            is_closed=s["is_closed"],
            is_won=s["is_won"],
        )
        db.add(stage)
    db.commit()
    return get_stages(db, owner_id)


def get_stages(db: Session, owner_id: uuid.UUID) -> list[DealStage]:
    """Kullanicinin pipeline asamalarini sirali getir."""
    return (
        db.query(DealStage)
        .filter(DealStage.owner_id == owner_id)
        .order_by(DealStage.position)
        .all()
    )


def create_stage(
    db: Session, owner_id: uuid.UUID, name: str, color: str = "#6366f1",
    is_closed: bool = False, is_won: bool = False,
) -> DealStage:
    """Yeni pipeline asamasi olustur."""
    max_pos = (
        db.query(DealStage.position)
        .filter(DealStage.owner_id == owner_id)
        .order_by(DealStage.position.desc())
        .first()
    )
    position = (max_pos[0] + 1) if max_pos else 0

    stage = DealStage(
        owner_id=owner_id, name=name, color=color,
        position=position, is_closed=is_closed, is_won=is_won,
    )
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return stage


def update_stage(
    db: Session, stage_id: uuid.UUID, owner_id: uuid.UUID, **kwargs
) -> DealStage:
    """Pipeline asamasini guncelle."""
    stage = db.query(DealStage).filter(
        DealStage.id == stage_id, DealStage.owner_id == owner_id
    ).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Asama bulunamadi")
    for key, value in kwargs.items():
        if value is not None and hasattr(stage, key):
            setattr(stage, key, value)
    db.commit()
    db.refresh(stage)
    return stage


def delete_stage(db: Session, stage_id: uuid.UUID, owner_id: uuid.UUID) -> bool:
    """Pipeline asamasini sil. Icerisinde deal varsa silme."""
    stage = db.query(DealStage).filter(
        DealStage.id == stage_id, DealStage.owner_id == owner_id
    ).first()
    if not stage:
        return False
    deal_count = db.query(Deal).filter(Deal.stage_id == stage_id).count()
    if deal_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Bu asamada {deal_count} firsat var. Once firsatlari tasiyin."
        )
    db.delete(stage)
    db.commit()
    return True


def reorder_stages(db: Session, owner_id: uuid.UUID, stage_ids: list[str]) -> None:
    """Asama siralamasini guncelle."""
    for i, sid in enumerate(stage_ids):
        db.query(DealStage).filter(
            DealStage.id == uuid.UUID(sid), DealStage.owner_id == owner_id
        ).update({"position": i})
    db.commit()


# --- Deal (Firsat) CRUD ---

def get_deals(
    db: Session, owner_id: uuid.UUID,
    stage_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    search: str | None = None,
) -> list[Deal]:
    """Firsatlari getir."""
    query = db.query(Deal).filter(Deal.owner_id == owner_id)
    if stage_id:
        query = query.filter(Deal.stage_id == stage_id)
    if customer_id:
        query = query.filter(Deal.customer_id == customer_id)
    if search:
        query = query.filter(Deal.title.ilike(f"%{search}%"))
    return query.order_by(Deal.position, Deal.created_at.desc()).all()


def get_deal(db: Session, deal_id: uuid.UUID, owner_id: uuid.UUID) -> Deal:
    """Tek bir firsati getir."""
    deal = db.query(Deal).filter(
        Deal.id == deal_id, Deal.owner_id == owner_id
    ).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Firsat bulunamadi")
    return deal


def create_deal(
    db: Session, owner_id: uuid.UUID,
    title: str, stage_id: uuid.UUID,
    customer_id: uuid.UUID | None = None,
    quotation_id: uuid.UUID | None = None,
    value: Decimal = Decimal("0.00"),
    probability: int = 50,
    expected_close_date=None,
    notes: str | None = None,
    priority: str = "medium",
) -> Deal:
    """Yeni satis firsati olustur."""
    deal = Deal(
        owner_id=owner_id,
        title=title,
        stage_id=stage_id,
        customer_id=customer_id,
        quotation_id=quotation_id,
        value=value,
        probability=probability,
        expected_close_date=expected_close_date,
        notes=notes,
        priority=priority,
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


def update_deal(
    db: Session, deal_id: uuid.UUID, owner_id: uuid.UUID, **kwargs
) -> Deal:
    """Firsati guncelle."""
    deal = get_deal(db, deal_id, owner_id)
    for key, value in kwargs.items():
        if hasattr(deal, key):
            setattr(deal, key, value)
    db.commit()
    db.refresh(deal)
    return deal


def move_deal(
    db: Session, deal_id: uuid.UUID, owner_id: uuid.UUID,
    new_stage_id: uuid.UUID, new_position: int = 0,
) -> Deal:
    """Firsati baska bir asamaya tasi (surukle-birak)."""
    deal = get_deal(db, deal_id, owner_id)

    # Yeni asama var mi kontrol et
    new_stage = db.query(DealStage).filter(
        DealStage.id == new_stage_id, DealStage.owner_id == owner_id
    ).first()
    if not new_stage:
        raise HTTPException(status_code=404, detail="Hedef asama bulunamadi")

    deal.stage_id = new_stage_id
    deal.position = new_position

    # Kapanmis asamaya tasindiysa closed_at ayarla
    if new_stage.is_closed and not deal.closed_at:
        deal.closed_at = datetime.now(timezone.utc)
    elif not new_stage.is_closed:
        deal.closed_at = None

    db.commit()
    db.refresh(deal)
    return deal


def delete_deal(db: Session, deal_id: uuid.UUID, owner_id: uuid.UUID) -> bool:
    """Firsati sil."""
    deal = get_deal(db, deal_id, owner_id)
    db.delete(deal)
    db.commit()
    return True


# --- Istatistikler ---

def get_pipeline_stats(db: Session, owner_id: uuid.UUID) -> dict:
    """Pipeline istatistiklerini hesapla."""
    deals = db.query(Deal).filter(Deal.owner_id == owner_id).all()

    total_value = sum(d.value for d in deals)
    open_deals = [d for d in deals if not d.stage or not d.stage.is_closed]
    won_deals = [d for d in deals if d.stage and d.stage.is_closed and d.stage.is_won]
    lost_deals = [d for d in deals if d.stage and d.stage.is_closed and not d.stage.is_won]

    open_value = sum(d.value for d in open_deals)
    won_value = sum(d.value for d in won_deals)
    weighted_value = sum(d.value * d.probability / 100 for d in open_deals)

    win_rate = 0
    if won_deals or lost_deals:
        win_rate = round(len(won_deals) / (len(won_deals) + len(lost_deals)) * 100)

    return {
        "total_deals": len(deals),
        "open_deals": len(open_deals),
        "won_deals": len(won_deals),
        "lost_deals": len(lost_deals),
        "total_value": total_value,
        "open_value": open_value,
        "won_value": won_value,
        "weighted_value": weighted_value,
        "win_rate": win_rate,
    }
