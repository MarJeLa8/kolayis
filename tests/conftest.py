"""
KolayIS CRM - Test Yapilandirmasi (conftest.py)

SQLite in-memory veritabani kullanarak PostgreSQL gerektirmeden
tum API endpoint'lerini test etmeye olanak saglar.

Her test fonksiyonu icin temiz bir veritabani olusturulur (function scope).
"""

import uuid

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from kolayis.database import Base, get_db
from kolayis.main import app
from kolayis.services.auth import hash_password, create_access_token

# Tum modelleri import et - Base.metadata.create_all icin gerekli
from kolayis.models import User, Customer, Note, Product, Invoice, InvoiceItem, Payment, Activity


# ---------------------------------------------------------------------------
# SQLite In-Memory Test Veritabani
# ---------------------------------------------------------------------------

# SQLite in-memory engine: her test icin hizli, izole veritabani
SQLITE_TEST_URL = "sqlite:///file::memory:?cache=shared"

test_engine = create_engine(
    SQLITE_TEST_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

# SQLite'da foreign key desteigni aktif et
# SQLite varsayilan olarak foreign key constraint'leri uygulamaz
@event.listens_for(test_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_session():
    """
    Her test icin temiz bir veritabani oturumu olusturur.

    - Tablolari olusturur (create_all)
    - Test bittikten sonra tablolari siler (drop_all)
    - Boylece her test izole calisir
    """
    # Tablolari olustur
    Base.metadata.create_all(bind=test_engine)

    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Tablolari temizle - bir sonraki test temiz baslasin
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """
    FastAPI TestClient olusturur.

    get_db dependency'sini override ederek test veritabanini kullanir.
    Boylece uygulama PostgreSQL yerine SQLite in-memory ile calisir.
    """
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    # Override'lari temizle
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_user(db_session):
    """
    Test kullanicisi olusturur ve veritabanina kaydeder.

    Dondurur: User nesnesi (id, email, full_name, hashed_password)
    Sifre: "Test1234!"
    """
    user = User(
        id=uuid.uuid4(),
        email="test@kolayis.com",
        hashed_password=hash_password("Test1234!"),
        full_name="Test Kullanici",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def auth_headers(test_user):
    """
    Yetkilendirilmis istek icin Authorization header'i dondurur.

    test_user fixture'una bagimlidir.
    Dondurur: {"Authorization": "Bearer <jwt_token>"}
    """
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def test_customer(db_session, test_user):
    """
    Test musterisi olusturur ve veritabanina kaydeder.

    test_user'in sahip oldugu bir musteri dondurur.
    """
    customer = Customer(
        id=uuid.uuid4(),
        owner_id=test_user.id,
        company_name="Test Sirket A.S.",
        contact_name="Ahmet Yilmaz",
        email="ahmet@testsirket.com",
        phone="0212 555 1234",
        address="Istanbul, Turkiye",
        tax_number="1234567890",
        status="active",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


@pytest.fixture(scope="function")
def test_product(db_session, test_user):
    """
    Test urunu olusturur ve veritabanina kaydeder.

    test_user'in sahip oldugu bir urun dondurur.
    """
    from decimal import Decimal

    product = Product(
        id=uuid.uuid4(),
        owner_id=test_user.id,
        name="Test Urun",
        description="Test icin ornek urun",
        unit_price=Decimal("150.00"),
        unit="adet",
        tax_rate=20,
        stock=100,
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product
