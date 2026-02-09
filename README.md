# KolayIS - Acik Kaynak CRM

Kucuk ve orta olcekli isletmeler icin full-stack CRM uygulamasi. Musteri, fatura, urun, stok, teklif, satis pipeline ve gelir-gider yonetimini tek bir yerden yapin.

**Tamamen ucretsiz ve acik kaynak kodlu.**

**Tech Stack:** Python 3.13, FastAPI, PostgreSQL, SQLAlchemy 2.0, Jinja2, Tailwind CSS

![Python](https://img.shields.io/badge/Python-3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Ozellikler

### Temel CRM
- **Musteri Yonetimi** - CRUD, notlar, arama, filtreleme, durum takibi
- **Urun/Hizmet Yonetimi** - Fiyat, KDV orani, stok takibi, stok hareketleri
- **Faturalama** - Kalem bazli fatura, KDV hesaplama, kismi odeme takibi
- **Teklif/Proforma** - Teklif olusturma, faturaya cevirme
- **Gelir-Gider Takibi** - Kategoriler, ozet, filtreler

### Satis Pipeline
- **Kanban Board** - Surukle-birak ile firsat yonetimi (HTML5 Drag API)
- **Deal Asamalari** - Lead, Teklif, Muzakere, Kazanildi, Kaybedildi
- **Firma/Kisi Bazli** - Musterilere bagli firsat takibi
- **Deger Takibi** - Tahmini gelir ve kapanma tarihi

### AI Asistan
- **Akilli Analizler** - Gelir, gider, musteri ve pipeline analizi
- **Kullanim Kilavuzu** - Nasil yapilir sorularina otomatik yanitlar
- **Offline Motor** - API anahtari olmadan da akilli yanit uretimi
- **Claude API Destegi** - Opsiyonel Anthropic API entegrasyonu

### WhatsApp Entegrasyonu
- **Meta Cloud API** - WhatsApp Business mesajlasma
- **Musteri Baglantisi** - Musterilere dogrudan mesaj gonderme
- **Mesaj Gecmisi** - Gonderilen mesajlarin kaydi

### Bildirim Merkezi
- **Canli Bildirimler** - Zil ikonu ile anlik bildirim
- **Polling** - Otomatik yeni bildirim kontrolu
- **Kategoriler** - Fatura, odeme, vade, musteri bildirimleri

### Musteri Portali
- **Ayri Giris Sistemi** - Erisim kodu + PIN ile musteri girisi
- **Fatura Goruntuleme** - Musteriler kendi faturalarini gorebilir
- **Dashboard** - Borc, odeme, vade ozeti

### PWA (Progressive Web App)
- **Yerel Uygulama** - Ana ekrana ekleyerek kullanma
- **Service Worker** - Offline destek
- **Manifest** - Tam ekran uygulama deneyimi

### Ozel Alanlar
- **Dinamik Alan Tanimlama** - Entity bazli ozel alanlar (text, number, date, select)
- **Musteri/Urun/Fatura** - Her varlik icin ayri alan tanimlari
- **Form Entegrasyonu** - Detay sayfalarinda otomatik gosterim

### Otomasyon
- **Tekrarlayan Faturalar** - Haftalik, aylik, ceyreklik, yillik otomatik uretim
- **Vadesi Gecen Uyarilar** - Sidebar badge, liste vurgulama, banner
- **Webhook Bildirimleri** - HMAC-SHA256 imzali, olay bazli bildirimler

### Raporlama
- **Dashboard** - Ozet istatistikler, grafikler (Chart.js)
- **Detayli Raporlar** - Top 5 musteri/urun, tarih filtresi
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
- **Global Arama** - Ctrl+K ile hizli arama (musteri, urun, fatura)
- **Dark Mode** - Tema toggle + sistem tercihi
- **Mobil Uyumlu** - Responsive tasarim
- **Dosya Ekleri** - Musteri ve faturalara dosya yukleme
- **Toplu Islemler** - Musteri/urun silme, fatura durum guncelleme
- **Email Gonderme** - SMTP ile fatura/teklif gonderimi
- **Landing Page** - Pazarlama sayfasi
- **Onboarding Wizard** - Ilk kullanim rehberi

---

## Ekran Goruntuleri

| Dashboard | Fatura Detay |
|-----------|-------------|
| Ozet istatistikler, grafikler | Kalem bazli, PDF cikti |

| Satis Pipeline | AI Asistan |
|----------------|------------|
| Kanban surukle-birak | Akilli analiz ve kilavuz |

---

## Kurulum

### Gereksinimler
- Python 3.13+
- PostgreSQL 16+
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
# Docker ile PostgreSQL (opsiyonel)
docker-compose up -d

# Veya mevcut PostgreSQL'e baglan - .env'de DATABASE_URL'i ayarla

# Migration'lari calistir
alembic upgrade head
```

### 5. Ortam degiskenlerini ayarla
```bash
cp .env.example .env
# .env dosyasini duzenle
```

### 6. Uygulamayi calistir
```bash
uvicorn kolayis.main:app --reload --port 8000
```

Uygulama: http://localhost:8000
API Dokumantasyonu: http://localhost:8000/docs

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
| `ANTHROPIC_API_KEY` | Claude AI API anahtari (opsiyonel) | - |
| `AI_MODEL` | AI model adi | `claude-sonnet-4-5-20250929` |
| `WHATSAPP_API_TOKEN` | Meta WhatsApp API token | - |
| `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp telefon numarasi ID | - |

---

## Proje Yapisi

```
kolayis/
├── models/          # SQLAlchemy modelleri
├── schemas/         # Pydantic semalari
├── services/        # Is mantigi servisleri
├── routers/         # API ve web route'lari
├── templates/       # Jinja2 HTML sablonlari (55+ sayfa)
├── static/          # Statik dosyalar (manifest, icons)
├── main.py          # FastAPI uygulama giris noktasi
├── config.py        # Uygulama ayarlari
├── database.py      # Veritabani baglantisi
└── dependencies.py  # Bagimlilk enjeksiyonlari
tests/               # pytest test suite
alembic/             # Veritabani migration'lari
```

---

## Testler

```bash
pytest
```

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
| `POST /api/v1/ai/ask` | AI Asistan'a soru sor |
| `POST /api/v1/whatsapp/send` | WhatsApp mesaj gonder |
| `GET /api/v1/notifications` | Bildirimler |

---

## Kullanilan Teknolojiler

| Teknoloji | Kullanim |
|-----------|----------|
| **FastAPI** | Web framework, REST API |
| **SQLAlchemy 2.0** | ORM, veritabani islemleri |
| **PostgreSQL** | Veritabani |
| **Jinja2** | HTML template engine |
| **Tailwind CSS** | UI styling (CDN) |
| **Chart.js** | Grafik ve raporlar |
| **xhtml2pdf** | PDF olusturma |
| **openpyxl** | Excel import/export |
| **PyJWT** | Token tabanli auth |
| **PyOTP** | 2FA (TOTP) |
| **Alembic** | Veritabani migration |
| **Docker** | Containerization |

---

## Katki

Pull request'ler memnuniyetle karsilanir! Buyuk degisiklikler icin once bir issue acin.

1. Fork edin
2. Feature branch olusturun (`git checkout -b feature/yeni-ozellik`)
3. Degisikliklerinizi commit edin (`git commit -m 'Yeni ozellik eklendi'`)
4. Push edin (`git push origin feature/yeni-ozellik`)
5. Pull Request acin

---

## Lisans

MIT - Detaylar icin [LICENSE](LICENSE) dosyasina bakin.
