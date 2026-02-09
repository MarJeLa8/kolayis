import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from kolayis.logging_config import setup_logging
from kolayis.rate_limit import limiter
from kolayis.routers import auth, customers, notes, web, products_api, invoices_api, portal, notifications_api, deals_api, ai_api

# Loglama sistemini baslat (uygulama ayaga kalkmadan once)
setup_logging()

logger = logging.getLogger(__name__)

# FastAPI uygulamasini olustur
app = FastAPI(
    title="KolayIS",
    description="Kucuk isletmeler icin basit CRM sistemi",
    version="0.1.0",
)

logger.info("KolayIS uygulamasi baslatiliyor...")

# Static dosyalar (PWA manifest, icons, service worker)
app.mount("/static", StaticFiles(directory="kolayis/static"), name="static")

# slowapi'yi FastAPI state'e bagla
app.state.limiter = limiter

# ---------------------------------------------------------------------------
# CORS Ayarlari
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


# ---------------------------------------------------------------------------
# Guvenlik Header'lari Middleware
# ---------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Her yanita guvenlik header'lari ekler."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# ---------------------------------------------------------------------------
# Rate Limit Exceeded Handler
# ---------------------------------------------------------------------------
@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Rate limit asildiginda kullaniciya uygun hata mesaji dondur."""
    logger.warning("Rate limit asildi: %s %s", request.method, request.url)
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Cok fazla istek gonderdiniz. Lutfen biraz bekleyip tekrar deneyin.",
            "retry_after": exc.detail,
        },
    )


# Hata sayfalari icin template engine
_error_templates = Jinja2Templates(directory="kolayis/templates")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Ozel HTTP hata sayfalari (404, 500 vb.)."""
    logger.warning("HTTP %d hatasi: %s %s", exc.status_code, request.method, request.url)
    if exc.status_code == 404:
        return _error_templates.TemplateResponse(
            "errors/404.html",
            {"request": request},
            status_code=404,
        )
    if exc.status_code == 500:
        return _error_templates.TemplateResponse(
            "errors/500.html",
            {"request": request},
            status_code=500,
        )
    # Diger HTTP hatalari icin varsayilan davranis
    return HTMLResponse(content=str(exc.detail), status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Yakalanmamis hatalari 500 sayfasina yonlendir."""
    logger.error("Yakalanmamis hata: %s %s", request.method, request.url, exc_info=exc)
    return _error_templates.TemplateResponse(
        "errors/500.html",
        {"request": request},
        status_code=500,
    )


# API Router'lari
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Kimlik Dogrulama"])
app.include_router(customers.router, prefix="/api/v1/customers", tags=["Musteriler"])
app.include_router(notes.router, prefix="/api/v1/customers", tags=["Gorusme Notlari"])

# Yeni API Router'lari
app.include_router(products_api.router, prefix="/api/v1/products", tags=["Urunler API"])
app.include_router(invoices_api.router, prefix="/api/v1/invoices", tags=["Faturalar API"])

# Bildirim API
app.include_router(notifications_api.router, prefix="/api/v1/notifications", tags=["Bildirimler"])

# Satis Pipeline API
app.include_router(deals_api.router, prefix="/api/v1/pipeline", tags=["Satis Pipeline"])

# AI Asistan API
app.include_router(ai_api.router, prefix="/api/v1/ai", tags=["AI Asistan"])

# Musteri Portali router'i
app.include_router(portal.router, tags=["Musteri Portali"])

# Web arayuz router'i
app.include_router(web.router, tags=["Web Arayuz"])


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse("kolayis/static/favicon.ico")


@app.get("/")
def root(request: Request):
    """Ana sayfa - giris yapmissa dashboard, yapmamissa landing page."""
    token = request.cookies.get("access_token")
    if token:
        return RedirectResponse(url="/dashboard")
    return _error_templates.TemplateResponse("landing.html", {"request": request})
