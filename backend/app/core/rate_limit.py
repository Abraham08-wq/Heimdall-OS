from typing import Optional
import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import settings

async def configure_rate_limiter(app: FastAPI):
    """Initialize FastAPI Redis-backed rate limiter and attach middleware to normalize 429 responses.

    Uses `fastapi-limiter` under the hood. Adds a middleware to set a `Retry-After` header
    based on the limiter's reset value when returning 429.
    """
    try:
        from aioredis import from_url as aioredis_from_url
        from fastapi_limiter import FastAPILimiter
    except Exception:
        # Missing optional deps; skip initialization (dev only)
        return

    redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
    try:
        redis = await aioredis_from_url(redis_url, encoding='utf-8', decode_responses=True)
        await FastAPILimiter.init(redis)
    except Exception:
        # don't crash startup; log if available
        try:
            import logging
            logging.getLogger('rate_limit').warning('Could not initialize redis rate limiter')
        except Exception:
            pass

    @app.middleware('http')
    async def rate_limit_retry_after(request: Request, call_next):
        resp = await call_next(request)
        # normalize 429 responses from limiter to include Retry-After
        if resp.status_code == 429:
            # try to read X-RateLimit-Reset header if present
            reset = resp.headers.get('X-RateLimit-Reset')
            try:
                if reset:
                    # expected to be unix timestamp
                    import time
                    reset_ts = int(float(reset))
                    retry_after = max(0, reset_ts - int(time.time()))
                else:
                    retry_after = 60
            except Exception:
                retry_after = 60

            resp.headers['Retry-After'] = str(retry_after)
        return resp


def get_rate_limit_dependency(times: int = 5, seconds: int = 60):
    """Helper to return fastapi-limiter dependency. Returns None if fastapi-limiter is missing.
    Use like: Depends(get_rate_limit_dependency(5,60))
    """
    try:
        from fastapi_limiter.depends import RateLimiter

        def dep():
            return RateLimiter(times=times, seconds=seconds)

        return dep
    except Exception:
        # no-op dependency
        from fastapi import Depends

        async def noop():
            return None

        return lambda: Depends(noop)
