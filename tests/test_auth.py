"""
KolayIS CRM - Kimlik Dogrulama (Auth) Testleri

Test edilen endpoint'ler:
    POST /api/v1/auth/register  - Yeni kullanici kaydi
    POST /api/v1/auth/login     - Giris yapma (JWT token alma)
    GET  /api/v1/auth/me        - Mevcut kullanici bilgisi
"""


class TestRegister:
    """Kullanici kayit islemleri testleri."""

    def test_register(self, client):
        """Yeni kullanici basariyla kayit olabilmeli."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "yeni@kolayis.com",
                "password": "Guclu1234!",
                "full_name": "Yeni Kullanici",
            },
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["email"] == "yeni@kolayis.com"
        assert data["full_name"] == "Yeni Kullanici"
        assert data["is_active"] is True
        # Sifre hash'i response'da olmamali
        assert "hashed_password" not in data
        assert "password" not in data
        # UUID formatinda id donmeli
        assert "id" in data

    def test_register_duplicate_email(self, client, test_user):
        """Ayni email ile ikinci kez kayit olamamamali."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@kolayis.com",  # test_user'in email'i
                "password": "Guclu1234!",
                "full_name": "Duplikat Kullanici",
            },
        )
        assert response.status_code == 400
        assert "zaten kayitli" in response.json()["detail"]

    def test_register_short_password(self, client):
        """8 karakterden kisa sifre ile kayit olamamamali."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "kisa@kolayis.com",
                "password": "Ab1!",  # 4 karakter - cok kisa
                "full_name": "Kisa Sifre",
            },
        )
        assert response.status_code == 422  # Validation error

    def test_register_invalid_email(self, client):
        """Gecersiz email formatinda kayit olamamamali."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "gecersiz-email",
                "password": "Guclu1234!",
                "full_name": "Gecersiz Email",
            },
        )
        assert response.status_code == 422  # Validation error


class TestLogin:
    """Giris islemleri testleri."""

    def test_login(self, client, test_user):
        """Dogru email ve sifre ile giris yapabilmeli."""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@kolayis.com",
                "password": "Test1234!",
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        # Token bos olmamali
        assert len(data["access_token"]) > 0

    def test_login_wrong_password(self, client, test_user):
        """Yanlis sifre ile giris yapamamali."""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@kolayis.com",
                "password": "YanlisSifre123!",
            },
        )
        assert response.status_code == 401
        assert "hatali" in response.json()["detail"].lower()

    def test_login_nonexistent_user(self, client):
        """Kayitli olmayan email ile giris yapamamali."""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "yok@kolayis.com",
                "password": "HerhangiBirSifre1!",
            },
        )
        assert response.status_code == 401

    def test_login_returns_valid_token(self, client, test_user):
        """Login'den donen token ile /me endpoint'ine erisebilmeli."""
        # Once login yap
        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@kolayis.com",
                "password": "Test1234!",
            },
        )
        token = login_response.json()["access_token"]

        # Token ile /me endpoint'ine erisinebilmeli
        me_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_response.status_code == 200
        assert me_response.json()["email"] == "test@kolayis.com"


class TestMe:
    """/me endpoint'i testleri."""

    def test_me_with_token(self, client, test_user, auth_headers):
        """Gecerli token ile kullanici bilgilerini alabilmeli."""
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@kolayis.com"
        assert data["full_name"] == "Test Kullanici"
        assert data["is_active"] is True

    def test_me_without_token(self, client):
        """Token olmadan /me endpoint'ine erisememeli."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_me_with_invalid_token(self, client):
        """Gecersiz token ile /me endpoint'ine erisememeli."""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer gecersiz-token-12345"},
        )
        assert response.status_code == 401
