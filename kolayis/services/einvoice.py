"""
E-Fatura (UBL-TR) XML olusturma servisi.

UBL-TR 2.1 formatinda e-fatura XML'i olusturur.
Turkiye'deki GIB (Gelir Idaresi Baskanligi) standartlarina
uygun basitlestirilmis UBL-TR sablonu kullanir.

Namespace'ler:
- cbc: urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2
- cac: urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2
- inv: urn:oasis:names:specification:ubl:schema:xsd:Invoice-2

Kullanim:
    xml_str = generate_ubl_xml(invoice, customer, items, user)
"""

import re
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP
from xml.dom import minidom

# UBL-TR namespace tanimlari
NAMESPACES = {
    "xmlns": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "xmlns:cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "xmlns:cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "xmlns:ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
}

# Para birimi kodu
CURRENCY_CODE = "TRY"


def validate_tax_number(tax_number: str) -> bool:
    """
    Vergi numarasi dogrulama.

    Turkiye'de:
    - Tuzel kisiler (sirketler): 10 haneli vergi numarasi
    - Gercek kisiler (sahis): 11 haneli TC kimlik numarasi

    Args:
        tax_number: Dogrulanacak vergi numarasi

    Returns:
        True eger gecerli formattaysa (10 veya 11 haneli sayi)
    """
    if not tax_number:
        return False

    # Bosluk ve tire temizle
    cleaned = tax_number.strip().replace("-", "").replace(" ", "")

    # Sadece rakamlardan olusmali
    if not cleaned.isdigit():
        return False

    # 10 haneli (tuzel kisi) veya 11 haneli (gercek kisi) olmali
    return len(cleaned) in (10, 11)


def format_amount(amount) -> str:
    """
    Tutari UBL-TR formatina cevir.

    UBL-TR standardi nokta ayirici ve 2 ondalik basamak ister.
    Ornek: 1500.50 -> "1500.50", 3000 -> "3000.00"

    Args:
        amount: Cevirilecek tutar (Decimal, float veya int)

    Returns:
        2 ondalik basamakli, nokta ayiricili string
    """
    if isinstance(amount, Decimal):
        result = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        result = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return str(result)


def generate_ubl_xml(invoice, customer, items, user) -> str:
    """
    UBL-TR 2.1 formatinda e-fatura XML'i olusturur.

    GIB e-fatura standartlarina uygun basitlestirilmis XML uretir.
    Icerik: fatura no, tarih, musteri bilgileri, kalemler, KDV, toplamlar.

    Args:
        invoice: Invoice model nesnesi (invoice_number, invoice_date, due_date, subtotal, tax_total, total, notes)
        customer: Customer model nesnesi (company_name, tax_number, address, phone, email)
        items: InvoiceItem listesi (description, quantity, unit_price, tax_rate, line_total, tax_amount)
        user: User model nesnesi (full_name, email) - fatura duzenleyen

    Returns:
        Formatli UBL-TR XML string

    Ornek:
        xml_str = generate_ubl_xml(invoice, customer, invoice.items, current_user)
        # xml_str icerigi:
        # <?xml version="1.0" encoding="UTF-8"?>
        # <Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" ...>
        #   <cbc:ID>FTR-0001</cbc:ID>
        #   ...
        # </Invoice>
    """

    # Kok eleman: Invoice
    root = ET.Element("Invoice")
    for attr, value in NAMESPACES.items():
        root.set(attr, value)

    # --- UBL Versiyon Bilgisi ---
    _add_text_element(root, "cbc:UBLVersionID", "2.1")
    _add_text_element(root, "cbc:CustomizationID", "TR1.2")
    _add_text_element(root, "cbc:ProfileID", "TICARIFATURA")

    # --- Fatura Temel Bilgileri ---
    # Fatura numarasi
    _add_text_element(root, "cbc:ID", invoice.invoice_number)

    # Fatura tarihi ve zamani
    _add_text_element(root, "cbc:IssueDate", str(invoice.invoice_date))
    # Saat bilgisi (saat:dakika:saniye formati)
    if hasattr(invoice, "created_at") and invoice.created_at:
        _add_text_element(root, "cbc:IssueTime", invoice.created_at.strftime("%H:%M:%S"))
    else:
        _add_text_element(root, "cbc:IssueTime", "00:00:00")

    # Fatura tipi kodu: SATIS = standart satis faturasi
    _add_text_element(root, "cbc:InvoiceTypeCode", "SATIS")

    # Fatura notu
    if invoice.notes:
        _add_text_element(root, "cbc:Note", invoice.notes)

    # Para birimi
    _add_text_element(root, "cbc:DocumentCurrencyCode", CURRENCY_CODE)

    # --- Vade Tarihi ---
    if invoice.due_date:
        payment_means = ET.SubElement(root, "cac:PaymentMeans")
        _add_text_element(payment_means, "cbc:PaymentMeansCode", "1")
        _add_text_element(payment_means, "cbc:PaymentDueDate", str(invoice.due_date))

    # --- Fatura Duzenleyen (Satici / AccountingSupplierParty) ---
    supplier_party = ET.SubElement(root, "cac:AccountingSupplierParty")
    supplier_inner = ET.SubElement(supplier_party, "cac:Party")

    # Satici kimlik (kullanici email'i gecici olarak kullanilir)
    supplier_id = ET.SubElement(supplier_inner, "cac:PartyIdentification")
    supplier_id_val = ET.SubElement(supplier_id, "cbc:ID")
    supplier_id_val.set("schemeID", "VKN")
    supplier_id_val.text = "0000000000"  # Gercek senaryoda kullanicinin VKN'si

    # Satici adi
    supplier_name_elem = ET.SubElement(supplier_inner, "cac:PartyName")
    _add_text_element(supplier_name_elem, "cbc:Name", user.full_name)

    # Satici iletisim
    supplier_contact = ET.SubElement(supplier_inner, "cac:Contact")
    _add_text_element(supplier_contact, "cbc:ElectronicMail", user.email)

    # --- Fatura Alicisi (Musteri / AccountingCustomerParty) ---
    customer_party = ET.SubElement(root, "cac:AccountingCustomerParty")
    customer_inner = ET.SubElement(customer_party, "cac:Party")

    # Musteri vergi numarasi
    if customer.tax_number:
        customer_id = ET.SubElement(customer_inner, "cac:PartyIdentification")
        customer_id_val = ET.SubElement(customer_id, "cbc:ID")
        # 11 haneli = TCKN, 10 haneli = VKN
        if len(customer.tax_number.strip()) == 11:
            customer_id_val.set("schemeID", "TCKN")
        else:
            customer_id_val.set("schemeID", "VKN")
        customer_id_val.text = customer.tax_number.strip()

    # Musteri adi
    customer_name_elem = ET.SubElement(customer_inner, "cac:PartyName")
    _add_text_element(customer_name_elem, "cbc:Name", customer.company_name)

    # Musteri adres
    if customer.address:
        postal_address = ET.SubElement(customer_inner, "cac:PostalAddress")
        address_line = ET.SubElement(postal_address, "cac:AddressLine")
        _add_text_element(address_line, "cbc:Line", customer.address)
        country = ET.SubElement(postal_address, "cac:Country")
        _add_text_element(country, "cbc:Name", "Turkiye")

    # Musteri iletisim
    customer_contact = ET.SubElement(customer_inner, "cac:Contact")
    if customer.phone:
        _add_text_element(customer_contact, "cbc:Telephone", customer.phone)
    if customer.email:
        _add_text_element(customer_contact, "cbc:ElectronicMail", customer.email)

    # --- Vergi Toplamlar (TaxTotal) ---
    # KDV oranina gore gruplama
    tax_groups = _group_taxes(items)

    tax_total_elem = ET.SubElement(root, "cac:TaxTotal")
    tax_amount_elem = _add_currency_element(
        tax_total_elem, "cbc:TaxAmount", format_amount(invoice.tax_total)
    )

    # Her KDV orani icin alt toplam (TaxSubtotal)
    for rate, amounts in tax_groups.items():
        tax_subtotal = ET.SubElement(tax_total_elem, "cac:TaxSubtotal")
        _add_currency_element(
            tax_subtotal, "cbc:TaxableAmount", format_amount(amounts["taxable"])
        )
        _add_currency_element(
            tax_subtotal, "cbc:TaxAmount", format_amount(amounts["tax"])
        )
        # KDV orani
        _add_text_element(tax_subtotal, "cbc:Percent", str(rate))
        # Vergi kategorisi
        tax_category = ET.SubElement(tax_subtotal, "cac:TaxCategory")
        tax_scheme = ET.SubElement(tax_category, "cac:TaxScheme")
        _add_text_element(tax_scheme, "cbc:Name", "KDV")
        _add_text_element(tax_scheme, "cbc:TaxTypeCode", "0015")

    # --- Fatura Toplam (LegalMonetaryTotal) ---
    monetary_total = ET.SubElement(root, "cac:LegalMonetaryTotal")
    _add_currency_element(
        monetary_total, "cbc:LineExtensionAmount", format_amount(invoice.subtotal)
    )
    _add_currency_element(
        monetary_total, "cbc:TaxExclusiveAmount", format_amount(invoice.subtotal)
    )
    _add_currency_element(
        monetary_total, "cbc:TaxInclusiveAmount", format_amount(invoice.total)
    )
    _add_currency_element(
        monetary_total, "cbc:PayableAmount", format_amount(invoice.total)
    )

    # --- Fatura Kalemleri (InvoiceLine) ---
    for idx, item in enumerate(items, start=1):
        line = ET.SubElement(root, "cac:InvoiceLine")

        # Kalem sirasi
        _add_text_element(line, "cbc:ID", str(idx))

        # Miktar (birim: adet = C62 UBL kodu)
        qty_elem = _add_text_element(line, "cbc:InvoicedQuantity", format_amount(item.quantity))
        qty_elem.set("unitCode", "C62")

        # Kalem toplami (KDV haric)
        _add_currency_element(line, "cbc:LineExtensionAmount", format_amount(item.line_total))

        # Kalem vergi toplami
        item_tax_total = ET.SubElement(line, "cac:TaxTotal")
        _add_currency_element(
            item_tax_total, "cbc:TaxAmount", format_amount(item.tax_amount)
        )
        item_tax_subtotal = ET.SubElement(item_tax_total, "cac:TaxSubtotal")
        _add_currency_element(
            item_tax_subtotal, "cbc:TaxableAmount", format_amount(item.line_total)
        )
        _add_currency_element(
            item_tax_subtotal, "cbc:TaxAmount", format_amount(item.tax_amount)
        )
        _add_text_element(item_tax_subtotal, "cbc:Percent", str(item.tax_rate))
        item_tax_cat = ET.SubElement(item_tax_subtotal, "cac:TaxCategory")
        item_tax_scheme = ET.SubElement(item_tax_cat, "cac:TaxScheme")
        _add_text_element(item_tax_scheme, "cbc:Name", "KDV")
        _add_text_element(item_tax_scheme, "cbc:TaxTypeCode", "0015")

        # Kalem bilgileri (urun adi)
        item_elem = ET.SubElement(line, "cac:Item")
        _add_text_element(item_elem, "cbc:Name", item.description)

        # Birim fiyat
        price_elem = ET.SubElement(line, "cac:Price")
        _add_currency_element(price_elem, "cbc:PriceAmount", format_amount(item.unit_price))

    # XML string'e cevir ve formatla
    return _prettify_xml(root)


# ============================================================
# Yardimci (private) fonksiyonlar
# ============================================================


def _add_text_element(parent: ET.Element, tag: str, text: str) -> ET.Element:
    """
    Parent elemana yeni bir text alt eleman ekler.

    Args:
        parent: Ana XML elemani
        tag: Yeni elemanin tagi (orn: "cbc:ID")
        text: Elemanin metin icerigi

    Returns:
        Olusturulan alt eleman
    """
    elem = ET.SubElement(parent, tag)
    elem.text = text
    return elem


def _add_currency_element(parent: ET.Element, tag: str, amount: str) -> ET.Element:
    """
    Para birimi ozellikli bir eleman ekler.

    UBL-TR standartinda tutar alanlari currencyID ozelligine sahip olmali.
    Ornek: <cbc:TaxAmount currencyID="TRY">150.00</cbc:TaxAmount>

    Args:
        parent: Ana XML elemani
        tag: Yeni elemanin tagi
        amount: Tutar string'i (format_amount ile olusturulmus)

    Returns:
        Olusturulan alt eleman
    """
    elem = ET.SubElement(parent, tag)
    elem.set("currencyID", CURRENCY_CODE)
    elem.text = amount
    return elem


def _group_taxes(items) -> dict:
    """
    Fatura kalemlerini KDV oranina gore gruplar.

    Ayni KDV oranina sahip kalemlerin matrah (taxable) ve
    vergi (tax) toplamlarini hesaplar. UBL-TR TaxTotal/TaxSubtotal
    bolumu icin gereklidir.

    Args:
        items: InvoiceItem listesi

    Returns:
        {kdv_orani: {"taxable": matrah_toplami, "tax": vergi_toplami}}
        Ornek: {20: {"taxable": Decimal("1000.00"), "tax": Decimal("200.00")}}
    """
    groups = {}
    for item in items:
        rate = item.tax_rate
        if rate not in groups:
            groups[rate] = {"taxable": Decimal("0.00"), "tax": Decimal("0.00")}
        groups[rate]["taxable"] += item.line_total
        groups[rate]["tax"] += item.tax_amount
    return groups


def _prettify_xml(root: ET.Element) -> str:
    """
    XML agacini guzel formatlanmis string'e cevirir.

    minidom ile girintili (indent) XML olusturur.
    Bos satirlari temizler.

    Args:
        root: Kok XML elemani

    Returns:
        Formatli XML string (UTF-8, xml declaration dahil)
    """
    rough_string = ET.tostring(root, encoding="unicode", xml_declaration=False)
    # minidom ile formatla
    dom = minidom.parseString(rough_string)
    pretty = dom.toprettyxml(indent="  ", encoding=None)

    # minidom'un olusturdugu fazla bos satirlari temizle
    lines = [line for line in pretty.split("\n") if line.strip()]

    # Ilk satir xml declaration - UTF-8 olarak degistir
    if lines and lines[0].startswith("<?xml"):
        lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'

    return "\n".join(lines)
