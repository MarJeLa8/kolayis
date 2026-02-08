"""
Toplu islem servisi.
Birden fazla kayit uzerinde topluca silme, durum degistirme ve PDF export islemleri yapar.
"""
import io
import uuid
import zipfile
import logging

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from kolayis.models.customer import Customer
from kolayis.models.product import Product
from kolayis.models.invoice import Invoice
from kolayis.models.payment import Payment
from kolayis.services.activity import log_activity

logger = logging.getLogger(__name__)


def bulk_delete_customers(
    db: Session, owner_id: uuid.UUID, customer_ids: list[uuid.UUID]
) -> dict:
    """
    Birden fazla musteriyi toplu olarak sil.
    Her musteri icin sahiplik kontrolu yapar.

    Dondurur:
        {"total": int, "success": int, "errors": int,
         "success_items": list[str], "error_items": list[str]}
    """
    success_items = []
    error_items = []

    for cid in customer_ids:
        try:
            customer = db.query(Customer).filter(
                Customer.id == cid, Customer.owner_id == owner_id
            ).first()

            if not customer:
                error_items.append(f"Musteri bulunamadi (ID: {str(cid)[:8]}...)")
                continue

            company_name = customer.company_name
            db.delete(customer)
            db.flush()

            # Aktivite logu
            log_activity(
                db, owner_id, "delete", "customer", cid,
                f"Musteri '{company_name}' toplu silme ile silindi",
            )
            success_items.append(f"'{company_name}' silindi")

        except Exception as e:
            logger.error(f"Toplu musteri silme hatasi (ID: {cid}): {e}")
            error_items.append(f"Musteri silinemedi (ID: {str(cid)[:8]}...): {str(e)}")
            db.rollback()

    # Tum basarili islemleri commit et
    try:
        db.commit()
    except Exception as e:
        logger.error(f"Toplu musteri silme commit hatasi: {e}")
        db.rollback()
        # Commit basarisiz olduysa tum basarili kayitlari hataya tasi
        error_items.extend([item + " (commit hatasi)" for item in success_items])
        success_items = []

    return {
        "total": len(customer_ids),
        "success": len(success_items),
        "errors": len(error_items),
        "success_items": success_items,
        "error_items": error_items,
    }


def bulk_update_invoice_status(
    db: Session, owner_id: uuid.UUID, invoice_ids: list[uuid.UUID], new_status: str
) -> dict:
    """
    Birden fazla faturanin durumunu toplu olarak degistir.
    Gecerli durumlar: draft, sent, paid, cancelled

    Dondurur:
        {"total": int, "success": int, "errors": int,
         "success_items": list[str], "error_items": list[str]}
    """
    valid_statuses = ("draft", "sent", "paid", "cancelled")
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gecersiz durum: {new_status}. Gecerli degerler: {', '.join(valid_statuses)}"
        )

    status_labels = {
        "draft": "Taslak", "sent": "Gonderildi",
        "paid": "Odendi", "cancelled": "Iptal",
    }

    success_items = []
    error_items = []

    for inv_id in invoice_ids:
        try:
            invoice = db.query(Invoice).filter(
                Invoice.id == inv_id, Invoice.owner_id == owner_id
            ).first()

            if not invoice:
                error_items.append(f"Fatura bulunamadi (ID: {str(inv_id)[:8]}...)")
                continue

            old_status = invoice.status
            old_label = status_labels.get(old_status, old_status)
            new_label = status_labels.get(new_status, new_status)

            invoice.status = new_status
            db.flush()

            # Aktivite logu
            log_activity(
                db, owner_id, "status_change", "invoice", inv_id,
                f"Fatura '{invoice.invoice_number}' durumu '{old_label}' -> '{new_label}' (toplu islem)",
            )
            success_items.append(
                f"'{invoice.invoice_number}': {old_label} -> {new_label}"
            )

        except Exception as e:
            logger.error(f"Toplu fatura durum degisiklik hatasi (ID: {inv_id}): {e}")
            error_items.append(
                f"Fatura durum degistirilemedi (ID: {str(inv_id)[:8]}...): {str(e)}"
            )
            db.rollback()

    try:
        db.commit()
    except Exception as e:
        logger.error(f"Toplu fatura durum commit hatasi: {e}")
        db.rollback()
        error_items.extend([item + " (commit hatasi)" for item in success_items])
        success_items = []

    return {
        "total": len(invoice_ids),
        "success": len(success_items),
        "errors": len(error_items),
        "success_items": success_items,
        "error_items": error_items,
    }


def bulk_delete_products(
    db: Session, owner_id: uuid.UUID, product_ids: list[uuid.UUID]
) -> dict:
    """
    Birden fazla urunu toplu olarak sil.
    Her urun icin sahiplik kontrolu yapar.

    Dondurur:
        {"total": int, "success": int, "errors": int,
         "success_items": list[str], "error_items": list[str]}
    """
    success_items = []
    error_items = []

    for pid in product_ids:
        try:
            product = db.query(Product).filter(
                Product.id == pid, Product.owner_id == owner_id
            ).first()

            if not product:
                error_items.append(f"Urun bulunamadi (ID: {str(pid)[:8]}...)")
                continue

            product_name = product.name
            db.delete(product)
            db.flush()

            # Aktivite logu
            log_activity(
                db, owner_id, "delete", "product", pid,
                f"Urun '{product_name}' toplu silme ile silindi",
            )
            success_items.append(f"'{product_name}' silindi")

        except Exception as e:
            logger.error(f"Toplu urun silme hatasi (ID: {pid}): {e}")
            error_items.append(f"Urun silinemedi (ID: {str(pid)[:8]}...): {str(e)}")
            db.rollback()

    try:
        db.commit()
    except Exception as e:
        logger.error(f"Toplu urun silme commit hatasi: {e}")
        db.rollback()
        error_items.extend([item + " (commit hatasi)" for item in success_items])
        success_items = []

    return {
        "total": len(product_ids),
        "success": len(success_items),
        "errors": len(error_items),
        "success_items": success_items,
        "error_items": error_items,
    }


def bulk_export_invoices_pdf(
    db: Session, owner_id: uuid.UUID, invoice_ids: list[uuid.UUID]
) -> bytes:
    """
    Birden fazla faturanin PDF'ini tek bir ZIP dosyasinda birlestir.
    xhtml2pdf kullanarak her fatura icin ayri PDF olusturur ve ZIP'e ekler.

    Dondurur:
        ZIP dosyasinin bytes icerigi

    Hata:
        HTTPException(404) - Hicbir fatura bulunamazsa
        HTTPException(500) - PDF olusturma hatasi
    """
    from xhtml2pdf import pisa
    from jinja2 import Environment, FileSystemLoader
    import os

    # Template ortamini kur (PDF template icin)
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
    env = Environment(loader=FileSystemLoader(template_dir))

    invoices = []
    for inv_id in invoice_ids:
        invoice = db.query(Invoice).filter(
            Invoice.id == inv_id, Invoice.owner_id == owner_id
        ).first()
        if invoice:
            invoices.append(invoice)

    if not invoices:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Secilen faturalar bulunamadi"
        )

    # ZIP dosyasi olustur
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for invoice in invoices:
            try:
                # PDF template'ini render et
                template = env.get_template("invoices/pdf.html")
                html_content = template.render(invoice=invoice)

                # HTML'den PDF olustur
                pdf_buffer = io.BytesIO()
                pisa_status = pisa.CreatePDF(
                    io.StringIO(html_content),
                    dest=pdf_buffer,
                    encoding='utf-8'
                )

                if pisa_status.err:
                    logger.error(
                        f"PDF olusturma hatasi (Fatura: {invoice.invoice_number}): "
                        f"{pisa_status.err}"
                    )
                    continue

                # PDF'i ZIP'e ekle
                pdf_filename = f"{invoice.invoice_number}.pdf"
                zf.writestr(pdf_filename, pdf_buffer.getvalue())

            except Exception as e:
                logger.error(
                    f"Fatura PDF olusturma hatasi ({invoice.invoice_number}): {e}"
                )
                continue

    zip_buffer.seek(0)
    zip_bytes = zip_buffer.getvalue()

    if len(zip_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF dosyalari olusturulamadi"
        )

    # Aktivite logu
    log_activity(
        db, owner_id, "export", "invoice", None,
        f"{len(invoices)} fatura toplu PDF olarak export edildi",
    )
    db.commit()

    return zip_bytes
