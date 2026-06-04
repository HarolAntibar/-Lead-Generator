"""Rate limiter setup — slowapi singleton used across all routers.

Import `limiter` in any router and decorate endpoints with @limiter.limit().
The SlowAPIMiddleware must be registered in main.py for the limiter to work.

Key identifier: limits by the authenticated user's session key when present,
falling back to the client IP. This prevents one user from burning another's
quota while still blocking IP-level abuse.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
