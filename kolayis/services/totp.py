"""
TOTP (Time-based One-Time Password) servisi.
Iki faktorlu dogrulama (2FA) icin kullanilir.

Nasil calisir:
1. Kullanici 2FA'yi aktif etmek istediginde generate_totp_secret() ile bir secret uretilir
2. Bu secret + kullanici email'i ile bir URI olusturulur (get_totp_uri)
3. URI, QR koda donusturulur (generate_qr_code) - kullanici bunu Google Authenticator vb. ile tarar
4. Her giriste kullanicinin uygulamadan aldigi 6 haneli kod verify_totp() ile dogrulanir
"""

import io

import pyotp
import qrcode


def generate_totp_secret() -> str:
    """
    Yeni bir TOTP secret uret.
    Bu secret veritabaninda kullaniciya ait olarak saklanir.
    Base32 formatinda 32 karakter uzunlugunda rastgele bir string dondurur.
    """
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str) -> str:
    """
    TOTP URI olustur (otpauth:// formatinda).
    Bu URI, QR kod icine gomulur ve authenticator uygulamasi tarafindan okunur.

    Args:
        secret: Kullanicinin TOTP secret'i
        email: Kullanicinin email adresi (authenticator'da hesap adi olarak gorunur)

    Returns:
        otpauth://totp/KolayIS:email?secret=...&issuer=KolayIS formatinda URI
    """
    totp = pyotp.totp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name="KolayIS")


def generate_qr_code(uri: str) -> bytes:
    """
    Verilen URI'yi QR kod PNG goruntusune donustur.
    Kullanici bu QR kodu telefonundaki authenticator uygulamasiyla tarar.

    Args:
        uri: otpauth:// formatinda TOTP URI'si

    Returns:
        PNG formatinda QR kod goruntusu (bytes)
    """
    # QR kod olustur - hata duzeltme seviyesi yuksek tutulur (telefon kamerasi icin)
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(uri)
    qr.make(fit=True)

    # PNG olarak bellege yaz
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


def verify_totp(secret: str, code: str) -> bool:
    """
    Kullanicinin girdigi 6 haneli kodu dogrula.

    valid_window=1 parametresi sayesinde bir onceki ve bir sonraki
    30 saniyelik penceredeki kodlar da kabul edilir.
    Bu, kullanicinin saatinin biraz kayik olmasi durumunda bile
    giris yapabilmesini saglar.

    Args:
        secret: Kullanicinin veritabanindaki TOTP secret'i
        code: Kullanicinin girdigi 6 haneli kod (string)

    Returns:
        True eger kod gecerli, False degilse
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
