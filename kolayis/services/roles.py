"""
Rol tabanli yetkilendirme (RBAC) servisi.

Roller ve yetkileri:
- admin: Her seye erisebilir (wildcard: "*")
- manager: Musteriler, urunler, faturalar, raporlar, teklifler, giderler
- user: Sinirli erisim - okuma ve bazi olusturma yetkileri

Yetki formati: "kaynak.islem" (ornegin "customers.create", "invoices.read")
Wildcard: "kaynak.*" o kaynaktaki tum islemlere erisim verir
"""

from typing import Callable

from fastapi import HTTPException, status


# Rol -> yetki listesi eslesmesi
# "*" -> tum kaynaklara erisim (admin icin)
# "customers.*" -> customers altindaki tum islemlere erisim
# "customers.read" -> sadece okuma yetkisi
ROLES: dict = {
    "admin": ["*"],
    "manager": [
        "customers.*",
        "products.*",
        "invoices.*",
        "reports.*",
        "quotations.*",
        "expenses.*",
    ],
    "user": [
        "customers.read",
        "customers.create",
        "products.read",
        "invoices.read",
        "invoices.create",
    ],
}

# Rol hiyerarsisi: index buyudukce yetki artar
# require_role() fonksiyonunda karsilastirma icin kullanilir
ROLE_HIERARCHY = ["user", "manager", "admin"]


def has_permission(user_role: str, permission: str) -> bool:
    """
    Kullanicinin belirli bir yetkiye sahip olup olmadigini kontrol et.

    Kontrol sirasi:
    1. Rol ROLES dict'inde tanimli mi? (degilse False)
    2. Admin mi? ("*" yetkisi -> her seye erisir)
    3. Tam eslesme var mi? (ornegin "customers.read" == "customers.read")
    4. Wildcard eslesme var mi? (ornegin "customers.*" ile "customers.read" eslenir)

    Args:
        user_role: Kullanicinin rolu ("admin", "manager", "user")
        permission: Kontrol edilecek yetki ("customers.read" gibi)

    Returns:
        True eger kullanici bu yetkiye sahipse
    """
    # Rol tanimli degilse erisim yok
    permissions = ROLES.get(user_role, [])

    # Admin wildcard kontrolu - her seye erisir
    if "*" in permissions:
        return True

    # Tam eslesme kontrolu
    if permission in permissions:
        return True

    # Wildcard eslesme: "customers.*" izni "customers.read" i kapsar
    # permission'in kaynak kismini al (noktadan onceki kisim)
    resource = permission.split(".")[0] if "." in permission else permission
    wildcard = f"{resource}.*"
    if wildcard in permissions:
        return True

    return False


def require_role(min_role: str) -> Callable:
    """
    Minimum rol seviyesi gerektiren bir kontrol fonksiyonu dondur.

    Rol hiyerarsisi: user < manager < admin
    Ornegin require_role("manager") cagrildiginda:
    - admin -> IZIN (admin, manager'dan yuksek)
    - manager -> IZIN (esit)
    - user -> REDDEDILDI (user, manager'dan dusuk)

    Kullanim:
        checker = require_role("manager")
        checker(current_user)  # user.role < "manager" ise HTTPException firlatir

    Args:
        min_role: Gereken minimum rol ("user", "manager", "admin")

    Returns:
        Kullanici nesnesini alip yetki kontrolu yapan fonksiyon.
        Yetki yoksa HTTPException(403) firlatir.
    """
    def check_role(user) -> bool:
        """
        Kullanicinin rolunu kontrol et.
        user nesnesi .role attribute'una sahip olmali.
        """
        user_role = getattr(user, "role", "user")

        # Her iki rolun hiyerarsideki sirasini bul
        user_level = (
            ROLE_HIERARCHY.index(user_role)
            if user_role in ROLE_HIERARCHY
            else 0  # Bilinmeyen rol -> en dusuk seviye
        )
        min_level = (
            ROLE_HIERARCHY.index(min_role)
            if min_role in ROLE_HIERARCHY
            else 0
        )

        # Kullanicinin seviyesi, gereken seviyeden dusukse erisim yok
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu islem icin yetkiniz yok. Gereken minimum rol: "
                       f"{min_role}, sizin rolunuz: {user_role}",
            )
        return True

    return check_role
