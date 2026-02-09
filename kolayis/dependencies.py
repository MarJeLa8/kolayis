from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from kolayis.database import get_db
from kolayis.services.auth import verify_token
from kolayis.models.user import User

# OAuth2PasswordBearer: Swagger UI'da "Authorize" butonu gosterir
# tokenUrl: login endpoint'inin adresi
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """
    JWT token'dan mevcut kullaniciyi dondur.
    Oncelik: Authorization header, sonra cookie.
    """
    # Bearer token yoksa cookie'den dene
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token bulunamadi",
        )

    user_id = verify_token(token)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanici bulunamadi veya aktif degil",
        )
    return user
