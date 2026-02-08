"""
Email gonderme servisi.
SMTP kullanarak fatura PDF'ini ve dogrulama kodlarini gonderir.
"""

import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from kolayis.config import settings


def generate_verification_code() -> str:
    """6 haneli rastgele dogrulama kodu olustur."""
    return f"{random.randint(100000, 999999)}"


def send_verification_email(to_email: str, full_name: str, code: str) -> bool:
    """
    Kayit dogrulama kodunu email ile gonder.
    Basarili ise True, hata olursa False dondurur.
    """
    if not is_email_configured():
        return False

    msg = MIMEText(
        f"Sayin {full_name},\n\n"
        f"KolayIS hesabinizi dogrulamak icin asagidaki kodu kullanin:\n\n"
        f"    {code}\n\n"
        f"Bu kod 10 dakika gecerlidir.\n\n"
        f"Saygilarimizla,\n{settings.APP_NAME}",
        "plain",
        "utf-8",
    )
    msg["From"] = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = f"Email Dogrulama Kodu - {settings.APP_NAME}"

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception:
        return False


def is_email_configured() -> bool:
    """SMTP ayarlari tanimli mi kontrol et."""
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


def send_invoice_email(
    to_email: str,
    customer_name: str,
    invoice_number: str,
    pdf_bytes: bytes,
) -> bool:
    """
    Fatura PDF'ini email olarak gonder.
    Basarili ise True, hata olursa False dondurur.
    """
    if not is_email_configured():
        return False

    msg = MIMEMultipart()
    msg["From"] = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = f"Fatura: {invoice_number} - {settings.APP_NAME}"

    # Email govdesi
    body = f"""Sayin {customer_name},

{invoice_number} numarali faturaniz ekte yer almaktadir.

Sorulariniz icin bizimle iletisime gecebilirsiniz.

Saygilarimizla,
{settings.APP_NAME}
"""
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # PDF eki
    pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    pdf_attachment.add_header(
        "Content-Disposition", "attachment", filename=f"{invoice_number}.pdf"
    )
    msg.attach(pdf_attachment)

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception:
        return False
