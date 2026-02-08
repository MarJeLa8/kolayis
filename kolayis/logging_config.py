import logging
import os
from logging.handlers import RotatingFileHandler

from kolayis.config import settings


def setup_logging() -> None:
    """
    Uygulama genelinde logging yapilandirmasini kurar.

    - Console handler: terminale INFO ve ustu mesajlari yazar.
    - File handler: logs/kolayis.log dosyasina yazar (rotating, max 5MB, 3 yedek).

    Cagrilma zamani: uygulama baslarken (main.py icinde) bir kez cagrilmali.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Root logger yapilandirmasi
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Ayni handler'larin tekrar eklenmesini onle (reload durumlarinda)
    if root_logger.handlers:
        return

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # --- Console Handler ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # --- File Handler (Rotating) ---
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "kolayis.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Kurulum tamamlandi bilgisi
    logging.getLogger(__name__).info(
        "Logging yapilandirmasi tamamlandi (seviye: %s)", settings.LOG_LEVEL.upper()
    )
