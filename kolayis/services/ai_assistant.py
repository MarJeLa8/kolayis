"""
AI Asistan servisi.
Claude API kullanarak isletme verilerini analiz eder,
tahminler yapar ve oneriler sunar.
"""
import uuid
import json
import logging
from decimal import Decimal
from datetime import datetime, date, timedelta

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func, extract

from kolayis.config import settings
from kolayis.models.invoice import Invoice
from kolayis.models.customer import Customer
from kolayis.models.payment import Payment
from kolayis.models.expense import Expense
from kolayis.models.deal import Deal, DealStage

logger = logging.getLogger(__name__)


def _get_business_context(db: Session, owner_id: uuid.UUID) -> str:
    """Kullanicinin isletme verilerini AI icin ozetle."""
    today = date.today()
    month_start = today.replace(day=1)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)

    # Musteri istatistikleri
    total_customers = db.query(Customer).filter(Customer.owner_id == owner_id).count()
    active_customers = db.query(Customer).filter(
        Customer.owner_id == owner_id, Customer.status == "active"
    ).count()
    new_customers_this_month = db.query(Customer).filter(
        Customer.owner_id == owner_id,
        Customer.created_at >= month_start,
    ).count()

    # Fatura istatistikleri
    invoices = db.query(Invoice).filter(Invoice.owner_id == owner_id).all()
    total_revenue = sum(i.total for i in invoices if i.status == "paid")
    pending_invoices = [i for i in invoices if i.status in ("draft", "sent")]
    pending_amount = sum(i.remaining_amount for i in pending_invoices)
    overdue_invoices = [
        i for i in pending_invoices
        if i.due_date and i.due_date < today
    ]
    overdue_amount = sum(i.remaining_amount for i in overdue_invoices)

    # Bu ay gelir
    this_month_invoices = [
        i for i in invoices
        if i.status == "paid" and i.invoice_date >= month_start
    ]
    this_month_revenue = sum(i.total for i in this_month_invoices)

    # Gecen ay gelir
    last_month_invoices = [
        i for i in invoices
        if i.status == "paid" and last_month_start <= i.invoice_date < month_start
    ]
    last_month_revenue = sum(i.total for i in last_month_invoices)

    # Giderler
    this_month_expenses = (
        db.query(sql_func.coalesce(sql_func.sum(Expense.amount), 0))
        .filter(
            Expense.owner_id == owner_id,
            Expense.expense_type == "expense",
            Expense.expense_date >= month_start,
        )
        .scalar()
    )

    # Son 5 fatura
    recent_invoices = sorted(invoices, key=lambda x: x.created_at, reverse=True)[:5]
    recent_invoice_lines = []
    for inv in recent_invoices:
        recent_invoice_lines.append(
            f"  - {inv.invoice_number}: {inv.total:.2f} TL ({inv.status}) - {inv.customer.company_name if inv.customer else '?'}"
        )

    # Pipeline
    deals = db.query(Deal).filter(Deal.owner_id == owner_id).all()
    open_deals = [d for d in deals if d.stage and not d.stage.is_closed]
    open_deal_value = sum(d.value for d in open_deals)

    # Top 5 musteri (gelire gore)
    customer_revenue = {}
    for inv in invoices:
        if inv.status == "paid" and inv.customer:
            name = inv.customer.company_name
            customer_revenue[name] = customer_revenue.get(name, Decimal("0")) + inv.total
    top_customers = sorted(customer_revenue.items(), key=lambda x: x[1], reverse=True)[:5]
    top_customer_lines = [f"  - {name}: {rev:.2f} TL" for name, rev in top_customers]

    context = f"""ISLETME VERILERI (Bugunun tarihi: {today.isoformat()}):

MUSTERILER:
- Toplam musteri: {total_customers}
- Aktif musteri: {active_customers}
- Bu ay yeni musteri: {new_customers_this_month}

GELIR:
- Toplam gelir (tum zamanlar): {total_revenue:.2f} TL
- Bu ay gelir: {this_month_revenue:.2f} TL
- Gecen ay gelir: {last_month_revenue:.2f} TL
- Bu ay gider: {this_month_expenses:.2f} TL
- Bu ay net: {(this_month_revenue - Decimal(str(this_month_expenses))):.2f} TL

FATURALAR:
- Bekleyen fatura tutari: {pending_amount:.2f} TL ({len(pending_invoices)} adet)
- Vadesi gecmis: {overdue_amount:.2f} TL ({len(overdue_invoices)} adet)

SATIS PIPELINE:
- Acik firsatlar: {len(open_deals)} adet, toplam deger: {open_deal_value:.2f} TL

SON 5 FATURA:
{chr(10).join(recent_invoice_lines) if recent_invoice_lines else "  Henuz fatura yok"}

EN COK GELIR GETIREN MUSTERILER:
{chr(10).join(top_customer_lines) if top_customer_lines else "  Henuz veri yok"}
"""
    return context


def ask_ai(
    db: Session,
    owner_id: uuid.UUID,
    question: str,
) -> str:
    """
    AI asistana soru sor.
    Isletme verileri ile birlikte Claude'a gonderir.
    """
    if not settings.ANTHROPIC_API_KEY:
        return _generate_offline_insight(db, owner_id, question)

    context = _get_business_context(db, owner_id)

    system_prompt = """Sen KolayIS CRM uygulamasinin AI asistanisin.
Kullanicinin isletme verilerini analiz edip Turkce olarak yardimci oluyorsun.
Kisa, net ve aksiyona donuk cevaplar ver.
Sayisal verileri kullanarak somut oneriler sun.
Emoji kullanma. Profesyonel bir dil kullan."""

    try:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.AI_MODEL,
                "max_tokens": 1024,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": f"{context}\n\nKULLANICI SORUSU: {question}"},
                ],
            },
            timeout=30,
        )
        result = resp.json()
        if "content" in result and result["content"]:
            return result["content"][0].get("text", "Cevap alinamadi.")
        return result.get("error", {}).get("message", "AI yanit veremedi.")
    except Exception as e:
        logger.error(f"AI asistan hatasi: {e}")
        return _generate_offline_insight(db, owner_id, question)


def get_dashboard_insights(db: Session, owner_id: uuid.UUID) -> list[dict]:
    """
    Dashboard icin otomatik AI oneriler olustur.
    API key yoksa basit kural tabanli oneriler dondurur.
    """
    return _generate_offline_insight_cards(db, owner_id)


def _generate_offline_insight(db: Session, owner_id: uuid.UUID, question: str) -> str:
    """API key yokken akilli kural tabanli cevap uret."""
    q = question.lower().strip()
    today = date.today()
    month_start = today.replace(day=1)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)

    # ---- Kullanim / nasil yapilir sorusu ----
    help_response = _handle_help_question(q)
    if help_response:
        return help_response

    # ---- Gelir / ciro sorusu ----
    if any(k in q for k in ["gelir", "ciro", "kazanc", "satis", "hasilat", "bu ay"]):
        invoices = db.query(Invoice).filter(
            Invoice.owner_id == owner_id, Invoice.status == "paid"
        ).all()
        total_revenue = sum(i.total for i in invoices)
        this_month = sum(i.total for i in invoices if i.invoice_date >= month_start)
        last_month = sum(
            i.total for i in invoices
            if last_month_start <= i.invoice_date < month_start
        )
        expenses = (
            db.query(sql_func.coalesce(sql_func.sum(Expense.amount), 0))
            .filter(
                Expense.owner_id == owner_id,
                Expense.expense_type == "expense",
                Expense.expense_date >= month_start,
            ).scalar()
        )
        net = this_month - Decimal(str(expenses))

        response = f"Bu ayin gelir durumu:\n\n"
        response += f"- Bu ay gelir: {this_month:,.0f} TL\n"
        response += f"- Gecen ay gelir: {last_month:,.0f} TL\n"
        response += f"- Bu ay gider: {expenses:,.0f} TL\n"
        response += f"- Bu ay net kar: {net:,.0f} TL\n"
        response += f"- Toplam gelir (tum zamanlar): {total_revenue:,.0f} TL\n\n"

        if last_month > 0:
            change = ((this_month - last_month) / last_month) * 100
            if change > 0:
                response += f"Gecen aya gore %{change:.0f} artis var. Guzel gidiyorsunuz!"
            elif change < 0:
                response += f"Gecen aya gore %{abs(change):.0f} dusus var. Yeni musterilere ve bekleyen faturalara odaklanmanizi oneririm."
            else:
                response += "Gelir gecen ayla ayni seviyede."
        elif this_month > 0:
            response += "Gecen ay gelir olmadigi icin karsilastirma yapilamiyor, ancak bu ay guzel bir baslangiciniz var."
        else:
            response += "Bu ay henuz tahsilat yapilmamis. Bekleyen faturalari takip etmenizi oneririm."
        return response

    # ---- Vade / gecmis fatura sorusu ----
    if any(k in q for k in ["vade", "gecmis", "gecikm", "overdue", "odenmemis", "bekleyen"]):
        overdue = db.query(Invoice).filter(
            Invoice.owner_id == owner_id,
            Invoice.status.in_(["draft", "sent"]),
            Invoice.due_date < today,
        ).all()
        pending = db.query(Invoice).filter(
            Invoice.owner_id == owner_id,
            Invoice.status.in_(["draft", "sent"]),
            Invoice.due_date >= today,
        ).all()

        if not overdue and not pending:
            return "Tebrikler! Vadesi gecmis veya bekleyen faturaniz bulunmuyor. Tum odemeler guncel gorunuyor."

        response = ""
        if overdue:
            overdue_total = sum(i.remaining_amount for i in overdue)
            response += f"Vadesi gecmis {len(overdue)} fatura var, toplam {overdue_total:,.0f} TL:\n\n"
            for inv in sorted(overdue, key=lambda x: x.due_date)[:5]:
                days_late = (today - inv.due_date).days
                cust_name = inv.customer.company_name if inv.customer else "?"
                response += f"- {inv.invoice_number} ({cust_name}): {inv.remaining_amount:,.0f} TL - {days_late} gun gecikme\n"
            if len(overdue) > 5:
                response += f"  ... ve {len(overdue) - 5} fatura daha\n"
            response += "\nBu musterilere odeme hatirlatmasi gondermenizi oneririm."
        else:
            response += "Vadesi gecmis faturaniz yok.\n"

        if pending:
            pending_total = sum(i.remaining_amount for i in pending)
            response += f"\nBekleyen {len(pending)} fatura var, toplam {pending_total:,.0f} TL."
            upcoming_7 = [i for i in pending if i.due_date and i.due_date <= today + timedelta(days=7)]
            if upcoming_7:
                response += f"\nOnumuzdeki 7 gun icinde vadesi dolacak {len(upcoming_7)} fatura var - bunlari yakindan takip edin."

        return response

    # ---- En iyi musteri sorusu ----
    if any(k in q for k in ["musteri", "en iyi", "en cok", "top", "sadik", "degerli"]):
        invoices = db.query(Invoice).filter(
            Invoice.owner_id == owner_id, Invoice.status == "paid"
        ).all()
        customer_revenue = {}
        customer_count = {}
        for inv in invoices:
            if inv.customer:
                name = inv.customer.company_name
                customer_revenue[name] = customer_revenue.get(name, Decimal("0")) + inv.total
                customer_count[name] = customer_count.get(name, 0) + 1

        if not customer_revenue:
            return "Henuz odenmis fatura bulunmadigi icin musteri siralamasiyanpilamiyor."

        top = sorted(customer_revenue.items(), key=lambda x: x[1], reverse=True)[:5]
        total_rev = sum(customer_revenue.values())

        response = "En cok gelir getiren musterileriniz:\n\n"
        for i, (name, rev) in enumerate(top, 1):
            pct = (rev / total_rev * 100) if total_rev else 0
            count = customer_count.get(name, 0)
            response += f"{i}. {name}: {rev:,.0f} TL ({count} fatura, toplamin %{pct:.0f}'i)\n"

        total_customers = db.query(Customer).filter(Customer.owner_id == owner_id).count()
        response += f"\nToplam {total_customers} musteriniz var. "

        if len(top) >= 2:
            top2_rev = sum(r for _, r in top[:2])
            concentration = (top2_rev / total_rev * 100) if total_rev else 0
            if concentration > 60:
                response += f"Dikkat: Gelirinizin %{concentration:.0f}'i ilk 2 musteriden geliyor. Musteri cesitliligini artirmaniz riski azaltir."
            else:
                response += "Musteri dagilimi dengeli gorunuyor, bu olumlu bir durum."

        return response

    # ---- Nakit akisi / tahmin sorusu ----
    if any(k in q for k in ["nakit", "tahmin", "ongooru", "projeksiyon", "akis", "cash"]):
        pending = db.query(Invoice).filter(
            Invoice.owner_id == owner_id,
            Invoice.status.in_(["draft", "sent"]),
        ).all()
        paid_this_month = sum(
            i.total for i in db.query(Invoice).filter(
                Invoice.owner_id == owner_id,
                Invoice.status == "paid",
                Invoice.invoice_date >= month_start,
            ).all()
        )
        expenses_this_month = (
            db.query(sql_func.coalesce(sql_func.sum(Expense.amount), 0))
            .filter(
                Expense.owner_id == owner_id,
                Expense.expense_type == "expense",
                Expense.expense_date >= month_start,
            ).scalar()
        )

        upcoming_30 = [i for i in pending if i.due_date and i.due_date <= today + timedelta(days=30)]
        upcoming_amount = sum(i.remaining_amount for i in upcoming_30)
        overdue = [i for i in pending if i.due_date and i.due_date < today]
        overdue_amount = sum(i.remaining_amount for i in overdue)

        response = "Nakit akisi tahmini (onumuzdeki 30 gun):\n\n"
        response += f"- Bu ay mevcut tahsilat: {paid_this_month:,.0f} TL\n"
        response += f"- Bu ay giderler: {expenses_this_month:,.0f} TL\n"
        response += f"- 30 gun icinde beklenen tahsilat: {upcoming_amount:,.0f} TL ({len(upcoming_30)} fatura)\n"
        if overdue_amount > 0:
            response += f"- Vadesi gecmis alacak: {overdue_amount:,.0f} TL ({len(overdue)} fatura)\n"
        response += f"\nTahmini toplam giris: {upcoming_amount + overdue_amount:,.0f} TL\n\n"

        if overdue_amount > upcoming_amount:
            response += "Vadesi gecmis alacaklar yuksek. Oncelikle gecmis faturaların tahsilatina odaklanmanizi oneririm."
        elif upcoming_amount > 0:
            response += "Onumuzdeki donemde duzenli bir nakit girisi bekleniyor. Fatura vadelerini yakindan takip etmeye devam edin."
        else:
            response += "Onumuzdeki 30 gun icinde vadesi dolacak fatura bulunmuyor. Yeni satis firsatlari olusturmayi dusunebilirsiniz."
        return response

    # ---- Pipeline / firsat sorusu ----
    if any(k in q for k in ["pipeline", "firsat", "deal", "satis firsati", "potansiyel"]):
        deals = db.query(Deal).join(DealStage).filter(
            Deal.owner_id == owner_id, DealStage.is_closed == False
        ).all()

        if not deals:
            return "Su an acik satis firsatiniz bulunmuyor. Yeni firsatlar olusturmak icin Pipeline sayfasini ziyaret edin."

        total_value = sum(d.value for d in deals)
        weighted = sum(d.value * d.probability / 100 for d in deals)
        high = [d for d in deals if d.probability >= 70]
        medium = [d for d in deals if 30 <= d.probability < 70]
        low = [d for d in deals if d.probability < 30]

        response = f"Satis Pipeline Ozeti:\n\n"
        response += f"- Toplam acik firsat: {len(deals)} adet, {total_value:,.0f} TL\n"
        response += f"- Agirlikli deger (olasiliga gore): {weighted:,.0f} TL\n\n"
        if high:
            response += f"Yuksek olasilik (%70+): {len(high)} firsat, {sum(d.value for d in high):,.0f} TL\n"
        if medium:
            response += f"Orta olasilik (%30-70): {len(medium)} firsat, {sum(d.value for d in medium):,.0f} TL\n"
        if low:
            response += f"Dusuk olasilik (<%30): {len(low)} firsat, {sum(d.value for d in low):,.0f} TL\n"

        if high:
            response += f"\nYuksek olasiklikli firsatlara oncelik verin - bunlar kisa vadede donusebilir."
        return response

    # ---- Gider sorusu ----
    if any(k in q for k in ["gider", "masraf", "harcama", "maliyet"]):
        expenses_this = (
            db.query(sql_func.coalesce(sql_func.sum(Expense.amount), 0))
            .filter(Expense.owner_id == owner_id, Expense.expense_type == "expense", Expense.expense_date >= month_start)
            .scalar()
        )
        expenses_last = (
            db.query(sql_func.coalesce(sql_func.sum(Expense.amount), 0))
            .filter(Expense.owner_id == owner_id, Expense.expense_type == "expense",
                    Expense.expense_date >= last_month_start, Expense.expense_date < month_start)
            .scalar()
        )
        revenue_this = sum(
            i.total for i in db.query(Invoice).filter(
                Invoice.owner_id == owner_id, Invoice.status == "paid", Invoice.invoice_date >= month_start
            ).all()
        )

        response = f"Gider durumu:\n\n"
        response += f"- Bu ay gider: {expenses_this:,.0f} TL\n"
        response += f"- Gecen ay gider: {expenses_last:,.0f} TL\n"
        response += f"- Bu ay gelir: {revenue_this:,.0f} TL\n"
        net = revenue_this - Decimal(str(expenses_this))
        response += f"- Bu ay net: {net:,.0f} TL\n\n"

        if expenses_last > 0:
            change = ((Decimal(str(expenses_this)) - Decimal(str(expenses_last))) / Decimal(str(expenses_last))) * 100
            if change > 20:
                response += f"Giderler gecen aya gore %{change:.0f} artmis. Gider kalemlerini gozden gecirmenizi oneririm."
            elif change < -10:
                response += f"Giderler gecen aya gore %{abs(change):.0f} azalmis, tasarruf saglanmis."
            else:
                response += "Giderler gecen ayla benzer seviyede."
        return response

    # ---- Genel ozet / fallback ----
    # Soruyu anlamaya calis ve isletme verileriyle birlikte anlamli cevap ver
    invoices = db.query(Invoice).filter(Invoice.owner_id == owner_id).all()
    total_customers = db.query(Customer).filter(Customer.owner_id == owner_id).count()
    total_revenue = sum(i.total for i in invoices if i.status == "paid")
    pending = [i for i in invoices if i.status in ("draft", "sent")]
    pending_amount = sum(i.remaining_amount for i in pending)
    overdue = [i for i in pending if i.due_date and i.due_date < today]

    # Oncelik ve aciliyet sirasi belirle
    priorities = []
    if overdue:
        overdue_amount = sum(i.remaining_amount for i in overdue)
        priorities.append(f"Vadesi gecmis {len(overdue)} fatura ({overdue_amount:,.0f} TL) tahsil edilmeyi bekliyor")
    if pending:
        priorities.append(f"Bekleyen {len(pending)} fatura takip edilmeli ({pending_amount:,.0f} TL)")
    month_start = today.replace(day=1)
    this_month_rev = sum(i.total for i in invoices if i.status == "paid" and i.invoice_date >= month_start)
    if this_month_rev == 0 and total_revenue > 0:
        priorities.append("Bu ay henuz tahsilat yapilmamis - odeme takibine oncelik verin")

    response = f"Sorunuzu anlamaya calistim. Iste isletmenizin mevcut durumu ve onerilerim:\n\n"
    response += f"Genel Durum:\n"
    response += f"- {total_customers} aktif musteri\n"
    response += f"- Toplam gelir: {total_revenue:,.0f} TL\n"
    response += f"- Bekleyen alacak: {pending_amount:,.0f} TL\n\n"

    if priorities:
        response += "Oncelikli Aksiyonlar:\n"
        for i, p in enumerate(priorities, 1):
            response += f"{i}. {p}\n"
        response += "\n"

    response += "Bana su konularda soru sorabilirsiniz:\n\n"
    response += "Veri Analizi:\n"
    response += '- "Bu ay gelir durumum nasil?"\n'
    response += '- "Vadesi gecmis faturalarim var mi?"\n'
    response += '- "En iyi musterilerim kimler?"\n'
    response += '- "Nakit akisi tahminim nedir?"\n\n'
    response += "Kullanim Rehberi:\n"
    response += '- "Fatura nasil olusturulur?"\n'
    response += '- "Musteri nasil eklenir?"\n'
    response += '- "WhatsApp mesaji nasil gonderilir?"\n'
    response += '- "Neler yapabilirim?"'
    return response


def _handle_help_question(q: str) -> str | None:
    """Kullanim / nasil yapilir tipi sorulari yakalayip rehber cevap dondurur."""

    # Uygulama hakkinda / ne ise yarar
    if any(k in q for k in ["ne ise yar", "ne ise yarar", "uygulama ne", "bu ne",
                             "kolayis ne", "ne isine", "ne icin", "amaci ne",
                             "bu program", "bu sistem", "ne yapabilir"]):
        return (
            "KolayIS, kucuk ve orta olcekli isletmeler icin gelistirilmis bir CRM ve "
            "fatura yonetim sistemidir.\n\n"
            "Temel Ozellikler:\n\n"
            "Musteri Yonetimi - Musterilerinizi tek merkezden yonetin, notlar tutun, "
            "iletisim gecmisini takip edin.\n\n"
            "Faturalama - Profesyonel faturalar oluturun, PDF olarak indirin veya "
            "e-posta ile gonderin. Tekrarlayan faturalar otomatik olusturulur.\n\n"
            "Odeme Takibi - Tahsilatlari kaydedin, vadesi gecmis faturalari aninda gorun, "
            "otomatik hatirlatmalar gonderin.\n\n"
            "Teklif Yonetimi - Teklifler hazirlayip onaylananları tek tikla faturaya donusturun.\n\n"
            "Satis Pipeline - Satis firsatlarini Kanban gorunumunde takip edin.\n\n"
            "WhatsApp Entegrasyonu - Musterilere fatura ve odeme hatirlatmasi gonderin.\n\n"
            "AI Asistan - Isletme verilerinizi analiz edip akilli oneriler alin.\n\n"
            "Raporlar & Dashboard - Gelir, gider, musteri analizlerini grafiklerle gorun.\n\n"
            "Stok Takibi - Urun stok hareketlerini yonetin.\n\n"
            "Gider Yonetimi - Isletme giderlerini kaydedin, kar-zarar analizi yapin.\n\n"
            "Kisacasi isletmenizi tek bir yerden yonetmenizi saglayan kapsamli bir aractir."
        )

    # Fatura olusturma
    if any(k in q for k in ["fatura olustur", "fatura nas", "fatura ekle", "fatura kes",
                             "yeni fatura", "fatura yaz", "faturalama"]):
        return (
            "Yeni fatura olusturmak icin:\n\n"
            "1. Sol menuden 'Faturalar' sayfasina gidin\n"
            "2. Sag ustteki 'Yeni Fatura' butonuna tiklayin\n"
            "3. Musteriyi secin (yoksa once musteri ekleyin)\n"
            "4. Urun/hizmet satirlarini ekleyin\n"
            "5. Vade tarihi ve notlari doldurun\n"
            "6. 'Kaydet' ile taslak olarak kaydedin\n"
            "7. Hazir oldugunda 'Gonder' ile musteriye iletin\n\n"
            "Ipucu: Daha once olusturdugu nuz bir faturadan 'Kopyala' ile yeni fatura da olusturabilirsiniz."
        )

    # Musteri ekleme
    if any(k in q for k in ["musteri olustur", "musteri nas", "musteri ekle", "yeni musteri",
                             "muster kayit", "musteri kaydet"]):
        return (
            "Yeni musteri eklemek icin:\n\n"
            "1. Sol menuden 'Musteriler' sayfasina gidin\n"
            "2. Sag ustteki 'Yeni Musteri' butonuna tiklayin\n"
            "3. Sirket adi, email, telefon ve adres bilgilerini girin\n"
            "4. Vergi dairesi ve vergi no bilgilerini ekleyin (istege bagli)\n"
            "5. 'Kaydet' butonuna tiklayin\n\n"
            "Ipucu: CSV dosyasindan toplu musteri aktarimi da yapabilirsiniz."
        )

    # Urun ekleme
    if any(k in q for k in ["urun olustur", "urun nas", "urun ekle", "yeni urun",
                             "hizmet ekle", "urun kayit"]):
        return (
            "Yeni urun veya hizmet eklemek icin:\n\n"
            "1. Sol menuden 'Urunler' sayfasina gidin\n"
            "2. 'Yeni Urun' butonuna tiklayin\n"
            "3. Urun adini, kodunu ve aciklamasini girin\n"
            "4. Birim fiyat ve KDV oranini belirleyin\n"
            "5. Stok takibi yapacaksaniz miktar girin\n"
            "6. 'Kaydet' ile kaydedin\n\n"
            "Ipucu: Urunler fatura olustururken otomatik olarak listelenir."
        )

    # Teklif olusturma
    if any(k in q for k in ["teklif olustur", "teklif nas", "teklif ekle", "yeni teklif",
                             "teklif hazirla", "teklif yaz"]):
        return (
            "Teklif olusturmak icin:\n\n"
            "1. Sol menuden 'Teklifler' sayfasina gidin\n"
            "2. 'Yeni Teklif' butonuna tiklayin\n"
            "3. Musteriyi secin ve urun satirlarini ekleyin\n"
            "4. Gecerlilik tarihini ve notlari doldurun\n"
            "5. 'Kaydet' ile kaydedin\n\n"
            "Ipucu: Kabul edilen teklifi tek tikla faturaya donusturebilirsiniz."
        )

    # Odeme kaydi
    if any(k in q for k in ["odeme nas", "odeme kayit", "odeme ekle", "tahsilat",
                             "odeme al", "odeme gir"]):
        return (
            "Odeme kaydetmek icin:\n\n"
            "1. 'Faturalar' sayfasindan ilgili faturayi acin\n"
            "2. Fatura detayinda 'Odeme Ekle' butonuna tiklayin\n"
            "3. Odeme tutarini, tarihini ve yontemini girin\n"
            "4. 'Kaydet' ile tamamlayin\n\n"
            "Fatura tamamen odendiginde durumu otomatik olarak 'Odendi' olarak guncellenir."
        )

    # Gider kaydi
    if any(k in q for k in ["gider nas", "gider ekle", "gider kayit", "masraf ekle",
                             "masraf nas", "harcama ekle"]):
        return (
            "Gider kaydetmek icin:\n\n"
            "1. Sol menuden 'Giderler' sayfasina gidin\n"
            "2. 'Yeni Gider' butonuna tiklayin\n"
            "3. Kategori, tutar ve tarihi girin\n"
            "4. Aciklama ve fis/fatura bilgilerini ekleyin\n"
            "5. 'Kaydet' ile kaydedin\n\n"
            "Giderler raporlarda ve kar-zarar hesabinda otomatik olarak kullanilir."
        )

    # Rapor
    if any(k in q for k in ["rapor nas", "rapor olustur", "rapor al", "rapor gor",
                             "rapor nerede"]):
        return (
            "Raporlari gormek icin:\n\n"
            "1. Sol menuden 'Raporlar' sayfasina gidin\n"
            "2. Gelir, gider, musteri ve urun raporlarini gorebilirsiniz\n"
            "3. Tarih araligini secin\n"
            "4. PDF veya Excel olarak indirebilirsiniz\n\n"
            "Dashboard'da da temel istatistikleri ve grafikleri gorebilirsiniz."
        )

    # WhatsApp
    if any(k in q for k in ["whatsapp", "mesaj gonder", "mesaj nas"]):
        return (
            "WhatsApp mesaji gondermek icin:\n\n"
            "1. Sol menuden 'WhatsApp' sayfasina gidin\n"
            "2. 'Mesaj Gonder' butonuna tiklayin\n"
            "3. Musteriyi secin\n"
            "4. Mesaj tipini secin: Serbest mesaj, Fatura veya Odeme hatirlatmasi\n"
            "5. 'Gonder' butonuna tiklayin\n\n"
            "Not: WhatsApp entegrasyonu icin Meta Business API ayarlarinin yapilmis olmasi gerekir."
        )

    # Pipeline / firsat
    if any(k in q for k in ["firsat nas", "firsat ekle", "deal ekle", "pipeline nas",
                             "firsat olustur", "yeni firsat"]):
        return (
            "Yeni satis firsati olusturmak icin:\n\n"
            "1. Sol menuden 'Pipeline' sayfasina gidin\n"
            "2. 'Yeni Firsat' butonuna tiklayin\n"
            "3. Firsat adini, degerini ve musteri bilgisini girin\n"
            "4. Asama ve olasilik yuzdesini belirleyin\n"
            "5. Tahmini kapanma tarihini secin\n"
            "6. 'Kaydet' ile kaydedin\n\n"
            "Firsatlari Kanban gorunumunde surekle-birak ile asamalar arasinda tasiyabilirsiniz."
        )

    # Ozel alan
    if any(k in q for k in ["ozel alan", "custom field", "alan ekle", "alan olustur"]):
        return (
            "Ozel alan tanimlamak icin:\n\n"
            "1. Sol menude Ayarlar > 'Ozel Alanlar' sayfasina gidin\n"
            "2. 'Yeni Alan Ekle' butonuna tiklayin\n"
            "3. Hangi varlik icin oldugunu secin (Musteri, Fatura, Urun, Firsat)\n"
            "4. Alan adi, tipi (metin, sayi, tarih, secim listesi, vb.) belirleyin\n"
            "5. 'Kaydet' ile kaydedin\n\n"
            "Tanimlanan alanlar ilgili detay sayfalarinda gorunur ve duzenlenebilir."
        )

    # PDF / export
    if any(k in q for k in ["pdf", "yazdir", "indir", "export", "excel", "csv",
                             "disari aktar"]):
        return (
            "Verileri disa aktarmak icin:\n\n"
            "- Fatura PDF: Fatura detay sayfasinda 'PDF Indir' butonu\n"
            "- Musteri listesi: Musteriler sayfasinda 'Excel/CSV' butonu\n"
            "- Raporlar: Raporlar sayfasinda PDF veya Excel secenegi\n"
            "- Fatura XML: e-Fatura (UBL-TR) formati desteklenir\n\n"
            "Ipucu: Toplu islem icin liste sayfalarindaki secim kutularini kullanin."
        )

    # Genel nasil / yardim (veri analizi iceren sorulari haric tut)
    data_keywords = ["gelir", "ciro", "kazanc", "hasilat", "vade", "gecmis", "gecikm",
                     "musteri", "en iyi", "en cok", "nakit", "tahmin", "pipeline",
                     "firsat", "gider", "masraf", "bu ay", "satis"]
    is_data_question = any(k in q for k in data_keywords)
    if not is_data_question and any(k in q for k in ["nasil", "nedir", "nerede", "yapabil",
                                                      "yardim", "help", "ne yapab",
                                                      "ozellik", "fonksiyon"]):
        return (
            "KolayIS ile yapabilecekleriniz:\n\n"
            "- Musteri Yonetimi: Musteri ekleyin, notlar tutun, ozel alanlar tanimlayin\n"
            "- Faturalama: Fatura oluturun, PDF indirin, e-posta ile gonderin\n"
            "- Urun & Stok: Urun/hizmet tanimlarin, stok takibi yapin\n"
            "- Teklifler: Teklif hazirlayip onaylananlarari faturaya donusturun\n"
            "- Odeme Takibi: Tahsilatlari kaydedin, vadesi gecmisleri takip edin\n"
            "- Gider Yonetimi: Giderlerinizi kaydedin, kar-zarar gorun\n"
            "- Satis Pipeline: Firsatlari Kanban gorunumunde yonetin\n"
            "- WhatsApp: Musterilere mesaj ve hatirlatma gonderin\n"
            "- Raporlar: Gelir, gider, musteri analizleri gorun\n"
            "- Takvim: Vade tarihlerini takvimde takip edin\n\n"
            "Herhangi bir ozellik hakkinda detay icin 'X nasil yapilir?' diye sorun.\n"
            "Ornegin: 'Fatura nasil olusturulur?', 'Musteri nasil eklenir?'"
        )

    return None


def _generate_offline_insight_cards(db: Session, owner_id: uuid.UUID) -> list[dict]:
    """Kural tabanli dashboard onerileri."""
    today = date.today()
    insights = []

    # Vadesi gecmis faturalar
    overdue = (
        db.query(Invoice)
        .filter(
            Invoice.owner_id == owner_id,
            Invoice.status.in_(["draft", "sent"]),
            Invoice.due_date < today,
        )
        .all()
    )
    if overdue:
        total = sum(i.remaining_amount for i in overdue)
        insights.append({
            "type": "warning",
            "title": "Vadesi Gecmis Faturalar",
            "message": f"{len(overdue)} faturanin vadesi gecmis. Toplam {total:.0f} TL tahsil edilmeyi bekliyor.",
            "action": "Musterilerinize hatirlatma gonderin.",
            "link": "/invoices?status=overdue",
        })

    # Gelir trendi
    month_start = today.replace(day=1)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)

    this_month = sum(
        i.total for i in db.query(Invoice).filter(
            Invoice.owner_id == owner_id,
            Invoice.status == "paid",
            Invoice.invoice_date >= month_start,
        ).all()
    )
    last_month = sum(
        i.total for i in db.query(Invoice).filter(
            Invoice.owner_id == owner_id,
            Invoice.status == "paid",
            Invoice.invoice_date >= last_month_start,
            Invoice.invoice_date < month_start,
        ).all()
    )

    if last_month > 0:
        change = ((this_month - last_month) / last_month) * 100
        if change > 0:
            insights.append({
                "type": "success",
                "title": "Gelir Artisi",
                "message": f"Bu ay gelir gecen aya gore %{change:.0f} artti ({this_month:.0f} TL vs {last_month:.0f} TL).",
                "action": "Tebrikler! Buyume devam ediyor.",
                "link": "/reports",
            })
        elif change < -10:
            insights.append({
                "type": "warning",
                "title": "Gelir Dususu",
                "message": f"Bu ay gelir gecen aya gore %{abs(change):.0f} dustu ({this_month:.0f} TL vs {last_month:.0f} TL).",
                "action": "Yeni musteri adaylarina odaklanin.",
                "link": "/pipeline",
            })

    # Yaklasan vadeler (7 gun icinde)
    upcoming = (
        db.query(Invoice)
        .filter(
            Invoice.owner_id == owner_id,
            Invoice.status.in_(["draft", "sent"]),
            Invoice.due_date >= today,
            Invoice.due_date <= today + timedelta(days=7),
        )
        .all()
    )
    if upcoming:
        total = sum(i.remaining_amount for i in upcoming)
        insights.append({
            "type": "info",
            "title": "Yaklasan Vadeler",
            "message": f"7 gun icinde vadesi dolacak {len(upcoming)} fatura var. Toplam: {total:.0f} TL.",
            "action": "Musterilerinizi bilgilendirin.",
            "link": "/invoices",
        })

    # Pipeline firsatlari
    open_deals = (
        db.query(Deal)
        .join(DealStage)
        .filter(Deal.owner_id == owner_id, DealStage.is_closed == False)
        .all()
    )
    if open_deals:
        total_value = sum(d.value for d in open_deals)
        high_prob = [d for d in open_deals if d.probability >= 70]
        if high_prob:
            insights.append({
                "type": "success",
                "title": "Yuksek Olasılikli Firsatlar",
                "message": f"{len(high_prob)} firsat %70+ olasilikla. Toplam deger: {sum(d.value for d in high_prob):.0f} TL.",
                "action": "Bu firsatlari yakindan takip edin.",
                "link": "/pipeline",
            })

    if not insights:
        insights.append({
            "type": "info",
            "title": "Her Sey Yolunda",
            "message": "Su an dikkat edilmesi gereken bir durum yok.",
            "action": "Iyi calismaya devam edin!",
            "link": "/dashboard",
        })

    return insights
