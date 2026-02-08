"""
KolayIS CRM - Musteri (Customer) Testleri

Test edilen endpoint'ler:
    POST   /api/v1/customers          - Musteri olusturma
    GET    /api/v1/customers           - Musteri listeleme
    GET    /api/v1/customers/{id}      - Musteri detay
    PUT    /api/v1/customers/{id}      - Musteri guncelleme
    DELETE /api/v1/customers/{id}      - Musteri silme
"""

import uuid


class TestCreateCustomer:
    """Musteri olusturma testleri."""

    def test_create_customer(self, client, auth_headers):
        """Yeni musteri basariyla olusturulabilmeli."""
        response = client.post(
            "/api/v1/customers",
            json={
                "company_name": "Yeni Sirket Ltd.",
                "contact_name": "Mehmet Demir",
                "email": "mehmet@yenisirket.com",
                "phone": "0312 444 5678",
                "address": "Ankara, Turkiye",
                "tax_number": "9876543210",
                "status": "active",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["company_name"] == "Yeni Sirket Ltd."
        assert data["contact_name"] == "Mehmet Demir"
        assert data["email"] == "mehmet@yenisirket.com"
        assert data["phone"] == "0312 444 5678"
        assert data["tax_number"] == "9876543210"
        assert data["status"] == "active"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_customer_minimal(self, client, auth_headers):
        """Sadece zorunlu alan (company_name) ile musteri olusturulabilmeli."""
        response = client.post(
            "/api/v1/customers",
            json={
                "company_name": "Minimal Sirket",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["company_name"] == "Minimal Sirket"
        assert data["contact_name"] is None
        assert data["email"] is None

    def test_create_customer_without_auth(self, client):
        """Token olmadan musteri olusturulamamamali."""
        response = client.post(
            "/api/v1/customers",
            json={"company_name": "Yetkisiz Sirket"},
        )
        assert response.status_code == 401

    def test_create_customer_empty_name(self, client, auth_headers):
        """Bos sirket adi ile musteri olusturulamamamali."""
        response = client.post(
            "/api/v1/customers",
            json={"company_name": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422  # Validation error


class TestListCustomers:
    """Musteri listeleme testleri."""

    def test_list_customers(self, client, auth_headers, test_customer):
        """Musteri listesi bos olmamali (test_customer fixture'u var)."""
        response = client.get(
            "/api/v1/customers",
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_list_customers_empty(self, client, auth_headers):
        """Hic musteri yoksa bos liste donmeli."""
        response = client.get(
            "/api/v1/customers",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_customers_pagination(self, client, auth_headers):
        """Sayfalama parametreleri calismali."""
        # Once 3 musteri olustur
        for i in range(3):
            client.post(
                "/api/v1/customers",
                json={"company_name": f"Sirket {i}"},
                headers=auth_headers,
            )

        # Sayfa 1, boyut 2
        response = client.get(
            "/api/v1/customers?page=1&size=2",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["size"] == 2

    def test_list_customers_search(self, client, auth_headers, test_customer):
        """Arama parametresi calismali."""
        response = client.get(
            "/api/v1/customers?search=Test Sirket",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        # Arama sonucu icerisinde test_customer olmali
        company_names = [item["company_name"] for item in data["items"]]
        assert "Test Sirket A.S." in company_names

    def test_list_customers_without_auth(self, client):
        """Token olmadan musteri listeleyememeli."""
        response = client.get("/api/v1/customers")
        assert response.status_code == 401


class TestGetCustomer:
    """Musteri detay testleri."""

    def test_get_customer(self, client, auth_headers, test_customer):
        """Musteri detayi basariyla getirilmeli."""
        response = client.get(
            f"/api/v1/customers/{test_customer.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["id"] == str(test_customer.id)
        assert data["company_name"] == "Test Sirket A.S."
        assert data["contact_name"] == "Ahmet Yilmaz"
        assert data["email"] == "ahmet@testsirket.com"

    def test_customer_not_found(self, client, auth_headers):
        """Olmayan musteri icin 404 donmeli."""
        fake_id = uuid.uuid4()
        response = client.get(
            f"/api/v1/customers/{fake_id}",
            headers=auth_headers,
        )
        assert response.status_code == 404
        assert "bulunamadi" in response.json()["detail"].lower()

    def test_get_customer_without_auth(self, client, test_customer):
        """Token olmadan musteri detayina erisememeli."""
        response = client.get(f"/api/v1/customers/{test_customer.id}")
        assert response.status_code == 401


class TestUpdateCustomer:
    """Musteri guncelleme testleri."""

    def test_update_customer(self, client, auth_headers, test_customer):
        """Musteri bilgileri basariyla guncellenebilmeli."""
        response = client.put(
            f"/api/v1/customers/{test_customer.id}",
            json={
                "company_name": "Guncellenmis Sirket A.S.",
                "contact_name": "Mehmet Yilmaz",
                "phone": "0216 777 8899",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["company_name"] == "Guncellenmis Sirket A.S."
        assert data["contact_name"] == "Mehmet Yilmaz"
        assert data["phone"] == "0216 777 8899"
        # Gonderilmeyen alanlar degismemeli
        assert data["email"] == "ahmet@testsirket.com"
        assert data["tax_number"] == "1234567890"

    def test_update_customer_partial(self, client, auth_headers, test_customer):
        """Sadece bir alan guncellendiginde diger alanlar degismemeli."""
        response = client.put(
            f"/api/v1/customers/{test_customer.id}",
            json={"status": "inactive"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "inactive"
        assert data["company_name"] == "Test Sirket A.S."  # Degismemeli

    def test_update_nonexistent_customer(self, client, auth_headers):
        """Olmayan musteriyi guncellemeye calismak 404 donmeli."""
        fake_id = uuid.uuid4()
        response = client.put(
            f"/api/v1/customers/{fake_id}",
            json={"company_name": "Yok Sirket"},
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestDeleteCustomer:
    """Musteri silme testleri."""

    def test_delete_customer(self, client, auth_headers, test_customer):
        """Musteri basariyla silinebilmeli."""
        response = client.delete(
            f"/api/v1/customers/{test_customer.id}",
            headers=auth_headers,
        )
        assert response.status_code == 204

        # Silindikten sonra erismeye calisinca 404 donmeli
        get_response = client.get(
            f"/api/v1/customers/{test_customer.id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 404

    def test_delete_nonexistent_customer(self, client, auth_headers):
        """Olmayan musteriyi silmeye calismak 404 donmeli."""
        fake_id = uuid.uuid4()
        response = client.delete(
            f"/api/v1/customers/{fake_id}",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_delete_customer_without_auth(self, client, test_customer):
        """Token olmadan musteri silememeli."""
        response = client.delete(f"/api/v1/customers/{test_customer.id}")
        assert response.status_code == 401
