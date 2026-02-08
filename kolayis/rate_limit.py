"""Rate limiting yapilandirmasi (slowapi)."""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Client IP bazli rate limiter
# Global limit: dakikada 120 istek
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"],
)
