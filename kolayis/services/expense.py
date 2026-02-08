import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from kolayis.models.expense import Expense, ExpenseCategory
from kolayis.schemas.expense import ExpenseCreate, ExpenseUpdate, ExpenseCategoryCreate
from kolayis.services.activity import log_activity


# --- Kategori CRUD ---

def get_expense_categories(
    db: Session, owner_id: uuid.UUID
) -> list[ExpenseCategory]:
    """
    Kullanicinin tum gelir-gider kategorilerini getir.
    Isme gore siralar.
    """
    return (
        db.query(ExpenseCategory)
        .filter(ExpenseCategory.owner_id == owner_id)
        .order_by(ExpenseCategory.name.asc())
        .all()
    )


def create_expense_category(
    db: Session, owner_id: uuid.UUID, data: ExpenseCategoryCreate
) -> ExpenseCategory:
    """Yeni gelir-gider kategorisi olustur."""
    category = ExpenseCategory(
        owner_id=owner_id,
        name=data.name,
        color=data.color,
    )
    db.add(category)
    db.flush()
    log_activity(
        db, owner_id, "create", "expense_category", category.id,
        f"Gelir-gider kategorisi '{data.name}' olusturuldu",
    )
    db.commit()
    db.refresh(category)
    return category


def delete_expense_category(
    db: Session, category_id: uuid.UUID, owner_id: uuid.UUID
) -> bool:
    """
    Gelir-gider kategorisini sil.
    Kategoriye bagli kayitlarin category_id'si NULL olur (ondelete SET NULL).
    Dondurur: True (basarili) veya False (bulunamadi).
    """
    category = db.query(ExpenseCategory).filter(
        ExpenseCategory.id == category_id,
        ExpenseCategory.owner_id == owner_id,
    ).first()

    if not category:
        return False

    category_name = category.name
    db.delete(category)
    log_activity(
        db, owner_id, "delete", "expense_category", category_id,
        f"Gelir-gider kategorisi '{category_name}' silindi",
    )
    db.commit()
    return True


# --- Gelir-Gider CRUD ---

def get_expenses(
    db: Session,
    owner_id: uuid.UUID,
    page: int = 1,
    size: int = 20,
    expense_type: str | None = None,
    category_id: uuid.UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    sort_by: str = "expense_date",
    sort_order: str = "desc",
) -> tuple[list[Expense], int]:
    """
    Kullanicinin gelir-gider kayitlarini listele.
    Sayfalama, tip filtresi, kategori filtresi, tarih araligi ve siralama destekler.
    Dondurur: (kayit_listesi, toplam_sayi)
    """
    query = db.query(Expense).filter(Expense.owner_id == owner_id)

    # Tip filtresi (income / expense)
    if expense_type:
        query = query.filter(Expense.expense_type == expense_type)

    # Kategori filtresi
    if category_id:
        query = query.filter(Expense.category_id == category_id)

    # Tarih araligi filtresi
    if start_date:
        query = query.filter(Expense.expense_date >= start_date)
    if end_date:
        query = query.filter(Expense.expense_date <= end_date)

    # Toplam kayit sayisi
    total = query.count()

    # Siralama
    allowed_sort_fields = {
        "expense_date": Expense.expense_date,
        "amount": Expense.amount,
        "created_at": Expense.created_at,
        "description": Expense.description,
    }
    sort_column = allowed_sort_fields.get(sort_by, Expense.expense_date)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    # Sayfalama
    offset = (page - 1) * size
    expenses = query.offset(offset).limit(size).all()

    return expenses, total


def get_expense(
    db: Session, expense_id: uuid.UUID, owner_id: uuid.UUID
) -> Expense:
    """Tek bir gelir-gider kaydini getir. Sahiplik kontrolu yapar."""
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.owner_id == owner_id,
    ).first()

    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gelir-gider kaydi bulunamadi",
        )
    return expense


def create_expense(
    db: Session, owner_id: uuid.UUID, data: ExpenseCreate
) -> Expense:
    """Yeni gelir veya gider kaydi olustur."""
    expense = Expense(
        owner_id=owner_id,
        **data.model_dump(),
    )
    db.add(expense)
    db.flush()

    tip_label = "Gelir" if data.expense_type == "income" else "Gider"
    log_activity(
        db, owner_id, "create", "expense", expense.id,
        f"{tip_label} kaydi '{data.description}' ({data.amount} TL) olusturuldu",
    )
    db.commit()
    db.refresh(expense)
    return expense


def update_expense(
    db: Session, expense_id: uuid.UUID, owner_id: uuid.UUID, data: ExpenseUpdate
) -> Expense:
    """
    Gelir-gider kaydini guncelle.
    exclude_unset=True: sadece gonderilen alanlari gunceller.
    """
    expense = get_expense(db, expense_id, owner_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(expense, field, value)

    log_activity(
        db, owner_id, "update", "expense", expense_id,
        f"Gelir-gider kaydi '{expense.description}' guncellendi",
    )
    db.commit()
    db.refresh(expense)
    return expense


def delete_expense(
    db: Session, expense_id: uuid.UUID, owner_id: uuid.UUID
) -> None:
    """Gelir-gider kaydini sil."""
    expense = get_expense(db, expense_id, owner_id)
    description = expense.description
    tip_label = "Gelir" if expense.expense_type == "income" else "Gider"

    db.delete(expense)
    log_activity(
        db, owner_id, "delete", "expense", expense_id,
        f"{tip_label} kaydi '{description}' silindi",
    )
    db.commit()


def get_expense_summary(
    db: Session,
    owner_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """
    Gelir-gider ozet bilgisini hesapla.
    Dondurur: {
        "total_income": float,
        "total_expense": float,
        "net": float,
        "by_category": [{"category_name": str, "category_color": str, "total": float, "type": str}, ...]
    }
    """
    base_query = db.query(Expense).filter(Expense.owner_id == owner_id)

    # Tarih araligi filtresi
    if start_date:
        base_query = base_query.filter(Expense.expense_date >= start_date)
    if end_date:
        base_query = base_query.filter(Expense.expense_date <= end_date)

    # Toplam gelir
    total_income = (
        base_query
        .filter(Expense.expense_type == "income")
        .with_entities(func.coalesce(func.sum(Expense.amount), 0))
        .scalar()
    )

    # Toplam gider
    total_expense = (
        base_query
        .filter(Expense.expense_type == "expense")
        .with_entities(func.coalesce(func.sum(Expense.amount), 0))
        .scalar()
    )

    # Net kar/zarar
    net = Decimal(str(total_income)) - Decimal(str(total_expense))

    # Kategori bazli ozet (LEFT JOIN ile kategori bilgisi de alinir)
    category_summary = (
        db.query(
            ExpenseCategory.name.label("category_name"),
            ExpenseCategory.color.label("category_color"),
            Expense.expense_type,
            func.sum(Expense.amount).label("total"),
        )
        .outerjoin(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .filter(Expense.owner_id == owner_id)
    )
    if start_date:
        category_summary = category_summary.filter(Expense.expense_date >= start_date)
    if end_date:
        category_summary = category_summary.filter(Expense.expense_date <= end_date)

    category_summary = (
        category_summary
        .group_by(ExpenseCategory.name, ExpenseCategory.color, Expense.expense_type)
        .all()
    )

    by_category = [
        {
            "category_name": row.category_name or "Kategorisiz",
            "category_color": row.category_color or "#9ca3af",
            "type": row.expense_type,
            "total": float(row.total),
        }
        for row in category_summary
    ]

    return {
        "total_income": float(total_income),
        "total_expense": float(total_expense),
        "net": float(net),
        "by_category": by_category,
    }
