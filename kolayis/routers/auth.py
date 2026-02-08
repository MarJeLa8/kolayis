from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from kolayis.database import get_db
from kolayis.dependencies import get_current_user
from kolayis.rate_limit import limiter
from kolayis.models.user import User
from kolayis.schemas.user import UserCreate, UserResponse, Token
from kolayis.services.auth import hash_password, verify_password, create_access_token

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(
    request: Request,
    data: UserCreate,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Yeni kullanici kaydi.
    Email benzersiz olmali, sifre en az 8 karakter.
    """
    # Email daha once kullanilmis mi kontrol et
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu email adresi zaten kayitli",
        )

    # Yeni kullanici olustur
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Giris yap ve JWT token al.
    Swagger UI'da username = email, password = sifre olarak girilir.
    """
    # Kullaniciyi email ile bul
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email veya sifre hatali",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesap devre disi birakilmis",
        )

    # Token olustur ve dondur
    access_token = create_access_token(user.id)
    return Token(access_token=access_token)


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Mevcut kullanicinin bilgilerini dondur.
    Bu endpoint token ile korunuyor - giris yapmadan erisemezsin.
    """
    return current_user
