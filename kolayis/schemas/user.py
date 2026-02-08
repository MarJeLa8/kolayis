import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserCreate(BaseModel):
    """Kayit olurken gonderilen veri"""
    email: EmailStr
    password: str = Field(min_length=8, description="En az 8 karakter")
    full_name: str = Field(min_length=2, max_length=255)


class UserResponse(BaseModel):
    """Kullanici bilgisi dondurmek icin"""
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime

    # from_attributes=True: SQLAlchemy modelinden otomatik donusum saglar
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """Giris basarili olunca donen JWT token"""
    access_token: str
    token_type: str = "bearer"
