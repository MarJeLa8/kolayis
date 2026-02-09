"""Satis Pipeline API router'i - Kanban surukle-birak islemleri icin."""
import uuid
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from kolayis.database import get_db
from kolayis.dependencies import get_current_user
from kolayis.models.user import User
from kolayis.services import deal as deal_service

logger = logging.getLogger(__name__)
router = APIRouter()


class MoveDealRequest(BaseModel):
    stage_id: str
    position: int = 0


class ReorderStagesRequest(BaseModel):
    stage_ids: list[str]


@router.get("/stages")
def list_stages(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Pipeline asamalarini getir."""
    stages = deal_service.ensure_default_stages(db, user.id)
    return {
        "stages": [
            {
                "id": str(s.id),
                "name": s.name,
                "color": s.color,
                "position": s.position,
                "is_closed": s.is_closed,
                "is_won": s.is_won,
                "deal_count": len(s.deals),
                "total_value": str(sum(d.value for d in s.deals)),
            }
            for s in stages
        ]
    }


@router.get("/deals")
def list_deals(
    stage_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Firsatlari getir (opsiyonel stage filtresi)."""
    sid = uuid.UUID(stage_id) if stage_id else None
    deals = deal_service.get_deals(db, user.id, stage_id=sid)
    return {
        "deals": [
            {
                "id": str(d.id),
                "title": d.title,
                "value": str(d.value),
                "currency": d.currency,
                "probability": d.probability,
                "priority": d.priority,
                "stage_id": str(d.stage_id),
                "customer_name": d.customer.company_name if d.customer else None,
                "customer_id": str(d.customer_id) if d.customer_id else None,
                "expected_close_date": d.expected_close_date.isoformat() if d.expected_close_date else None,
                "position": d.position,
            }
            for d in deals
        ]
    }


@router.post("/deals/{deal_id}/move")
def move_deal(
    deal_id: uuid.UUID,
    body: MoveDealRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Firsati baska bir asamaya tasi (surukle-birak)."""
    deal = deal_service.move_deal(
        db, deal_id, user.id,
        new_stage_id=uuid.UUID(body.stage_id),
        new_position=body.position,
    )
    return {"success": True, "deal_id": str(deal.id), "stage_id": str(deal.stage_id)}


@router.post("/stages/reorder")
def reorder_stages(
    body: ReorderStagesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Asama siralamasini guncelle."""
    deal_service.reorder_stages(db, user.id, body.stage_ids)
    return {"success": True}


@router.delete("/deals/{deal_id}")
def delete_deal(
    deal_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Firsati sil."""
    deal_service.delete_deal(db, deal_id, user.id)
    return {"success": True}


@router.get("/stats")
def pipeline_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Pipeline istatistiklerini getir."""
    return deal_service.get_pipeline_stats(db, user.id)
