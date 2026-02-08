# KolayIS

Kucuk isletmeler icin full-stack CRM uygulamasi. Musteri, fatura, urun, stok, teklif ve gelir-gider yonetimini tek bir yerden yapin.

**Tech Stack:** Python, FastAPI, PostgreSQL, SQLAlchemy, Jinja2, Tailwind CSS

![Python](https://img.shields.io/badge/Python-3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Ozellikler

### Temel
- **Musteri Yonetimi** - CRUD, notlar, arama, filtreleme, durum takibi
- **Urun/Hizmet Yonetimi** - Fiyat, KDV orani, stok takibi
- **Faturalama** - Kalem bazli fatura, KDV hesaplama, kismi odeme takibi
- **Teklif/Proforma** - Teklif olusturma, faturaya cevirme
- **Gelir-Gider Takibi** - Kategoriler, ozet, filtreler

### Otomasyon
- **Tekrarlayan Faturalar** - Haftalik, aylik, ceyreklik, yillik otomatik uretim
- **Vadesi Gecen Uyarilar** - Sidebar badge, liste vurgulama, banner
- **Webhook Bildirimleri** - HMAC-SHA256 imzali, olay bazli bildirimler

### Raporlama
- **Dashboard** - Ozet istatistikler, grafikler
- **Detayli Raporlar** - Top 5 musteri/urun, tarih filtresi, Chart.js grafikleri
- **Aktivite Logu** - Tum CRUD islemlerinin kaydi
- **Takvim Gorunumu** - Fatura, vade ve odeme tarihleri

### Import / Export
- **CSV & Excel Import** - Musteri, urun, fatura iceri aktarma
- **CSV & Excel Export** - Musteri, urun, fatura disa aktarma
- **PDF Ciktisi** - Profesyonel fatura PDF'i (xhtml2pdf)
- **E-Fatura** - UBL-TR XML formati

### Guvenlik
- **JWT Authentication** - Cookie tabanli oturum yonetimi
- **2FA (TOTP)** - QR kod ile iki faktorlu dogrulama
- **Cloudflare Turnstile** - Bot korumasi (login/register)
- **Rol Yonetimi** - Admin, manager, user rolleri
- **Rate Limiting** - API ve sayfa erisim sinirlamasi
- **Guvenlik Header'lari** - XSS, clickjacking, MIME korumalari

### Diger
- **Musteri Portali** - Musterilerin kendi faturalarini gormesi
- **Global Arama** - Ctrl+K ile hizli arama (AJAX)
- **Dark Mode** - Tema toggle + sistem tercihi
- **Mobil Uyumlu** - Responsive tasarim
- **Dosya Ekleri** - Musteri ve faturalara dosya yukleme
- **Toplu Islemler** - Musteri/urun silme, fatura durum guncelleme
- **Email Gonderme** - SMTP ile fatura/teklif gonderimi

---

## Kurulum

### Gereksinimler
- Python 3.13+
- PostgreSQL 16+ (veya Docker)
- Git

### 1. Projeyi klonla
```bash
git clone https://github.com/MarJeLa8/kolayis.git
cd kolayis
```

### 2. Sanal ortam olustur
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Bagimliliklari yukle
```bash
pip install -r requirements.txt
```

### 4. Veritabanini baslat
```bash
# Docker ile PostgreSQL
docker-compose up -d

# Migration'lari calistir
alembic upgrade head
```

### 5. Ortam degiskenlerini ayarla
```bash
# .env.example dosyasini kopyala
cp .env.example .env

# .env dosyasini duzenle (SECRET_KEY, SMTP ayarlari vs.)
```

### 6. Uygulamayi calistir
```bash
uvicorn kolayis.main:app --reload --port 8000
```

Uygulama: http://localhost:8000
API Dokumantasyonu: http://localhost:8000/docs

---

## Docker ile Production Deploy

```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## Ortam Degiskenleri

| Degisken | Aciklama | Varsayilan |
|----------|----------|------------|
| `DATABASE_URL` | PostgreSQL baglanti adresi | `postgresql://kolayis:kolayis123@localhost:5432/kolayis_db` |
| `SECRET_KEY` | JWT sifreleme anahtari | `CHANGE-THIS-IN-PRODUCTION` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token suresi (dk) | `30` |
| `SMTP_HOST` | Email sunucusu | - |
| `SMTP_PORT` | SMTP portu | `587` |
| `SMTP_USER` | SMTP kullanici adi | - |
| `SMTP_PASSWORD` | SMTP sifresi | - |
| `TURNSTILE_SITE_KEY` | Cloudflare Turnstile site key | - |
| `TURNSTILE_SECRET_KEY` | Cloudflare Turnstile secret key | - |

---

## Proje Yapisi

```
kolayis/
├── models/          # SQLAlchemy modelleri (13 model)
├── schemas/         # Pydantic semalari (12 sema)
├── services/        # Is mantigi servisleri (18 servis)
├── routers/         # API ve web route'lari (7 router)
├── templates/       # Jinja2 HTML sablonlari (51 sayfa)
├── main.py          # FastAPI uygulama giris noktasi
├── config.py        # Uygulama ayarlari
├── database.py      # Veritabani baglantisi
└── dependencies.py  # Bagimlilk enjeksiyonlari
tests/               # pytest test suite (48 test)
alembic/             # Veritabani migration'lari
```

---

## Testler

```bash
pytest
```

48 test: auth, customers, products, invoices

---

## API

REST API `/api/v1/` altinda sunulur. Swagger UI: http://localhost:8000/docs

| Endpoint | Aciklama |
|----------|----------|
| `POST /api/v1/auth/register` | Kayit ol |
| `POST /api/v1/auth/login` | Giris yap |
| `GET /api/v1/customers` | Musteri listesi |
| `GET /api/v1/products` | Urun listesi |
| `GET /api/v1/invoices` | Fatura listesi |

---

## Kullanilan Teknolojiler

| Teknoloji | Kullanim |
|-----------|----------|
| **FastAPI** | Web framework, REST API |
| **SQLAlchemy** | ORM, veritabani islemleri |
| **PostgreSQL** | Veritabani |
| **Jinja2** | HTML template engine |
| **Tailwind CSS** | UI styling |
| **Chart.js** | Grafik ve raporlar |
| **xhtml2pdf** | PDF olusturma |
| **openpyxl** | Excel import/export |
| **PyJWT** | Token tabanli auth |
| **PyOTP** | 2FA (TOTP) |
| **Alembic** | Veritabani migration |
| **Docker** | Containerization |

---

## Lisans

MIT
