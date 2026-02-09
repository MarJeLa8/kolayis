"""AI Asistan API router'i."""
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from kolayis.database import get_db
from kolayis.dependencies import get_current_user
from kolayis.models.user import User
from kolayis.services import ai_assistant

logger = logging.getLogger(__name__)
router = APIRouter()


class AskRequest(BaseModel):
    question: str


@router.post("/ask")
def ask_assistant(
    body: AskRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """AI asistana soru sor."""
    answer = ai_assistant.ask_ai(db, user.id, body.question)
    return {"answer": answer}


@router.get("/insights")
def get_insights(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Dashboard icin AI onerileri getir."""
    insights = ai_assistant.get_dashboard_insights(db, user.id)
    return {"insights": insights}
