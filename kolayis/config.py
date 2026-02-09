from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Uygulama ayarlari.
    Degerler .env dosyasindan okunur. .env dosyasi yoksa default degerler kullanilir.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Veritabani baglanti adresi
    DATABASE_URL: str = "postgresql://kolayis:kolayis123@localhost:5432/kolayis_db"

    # JWT (token) ayarlari
    SECRET_KEY: str = "CHANGE-THIS-IN-PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Uygulama
    APP_NAME: str = "KolayIS"
    DEBUG: bool = True

    # Loglama seviyesi (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    LOG_LEVEL: str = "INFO"

    # SMTP (email gonderme) ayarlari
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""

    # Cloudflare Turnstile
    TURNSTILE_SITE_KEY: str = ""
    TURNSTILE_SECRET_KEY: str = ""

    # AI Asistan (Claude API)
    ANTHROPIC_API_KEY: str = ""
    AI_MODEL: str = "claude-sonnet-4-5-20250929"

    # WhatsApp Business API (Meta Cloud API)
    WHATSAPP_API_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = "kolayis-webhook-verify"


# Tek bir settings nesnesi olustur, her yerde bunu kullan
settings = Settings()
