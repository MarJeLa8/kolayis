# Tum modelleri buradan import ediyoruz
# Boylece Alembic autogenerate tum tablolari gorebilir
from kolayis.models.user import User
from kolayis.models.customer import Customer
from kolayis.models.note import Note
from kolayis.models.product import Product
from kolayis.models.invoice import Invoice, InvoiceItem
from kolayis.models.payment import Payment
from kolayis.models.activity import Activity
from kolayis.models.quotation import Quotation, QuotationItem
from kolayis.models.expense import Expense, ExpenseCategory
from kolayis.models.recurring import RecurringInvoice, RecurringInvoiceItem
from kolayis.models.attachment import Attachment
from kolayis.models.stock_movement import StockMovement
from kolayis.models.webhook import Webhook, WebhookLog
from kolayis.models.portal import PortalAccess

__all__ = [
    "User", "Customer", "Note", "Product", "Invoice", "InvoiceItem",
    "Payment", "Activity", "Quotation", "QuotationItem",
    "Expense", "ExpenseCategory", "RecurringInvoice", "RecurringInvoiceItem",
    "Attachment", "StockMovement", "Webhook", "WebhookLog", "PortalAccess",
]
