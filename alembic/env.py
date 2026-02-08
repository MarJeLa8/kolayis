import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Proje kokunu Python path'e ekle (import'larin calismasi icin)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Modellerimizi ve ayarlarimizi import et
from kolayis.database import Base
from kolayis.config import settings
import kolayis.models  # noqa: F401 - Tum modellerin yuklenmesi icin

# Alembic config nesnesi
config = context.config

# .env dosyasindan veritabani URL'sini al (alembic.ini'deki yerine)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Logging ayarlari
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Autogenerate icin: Base.metadata tum tablo bilgilerini icerir
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
