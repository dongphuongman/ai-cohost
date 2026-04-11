import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine
from app.routers import analytics, auth, billing, faqs, personas, products, scripts, sessions, shops, tts, webhooks
from app.ws.handler import websocket_endpoint as ws_handler, _redis as ws_redis

logger = logging.getLogger(__name__)

def _filter_sensitive_data(event, hint):
    """Strip passwords, tokens, API keys from error reports."""
    if "request" in event and "headers" in event["request"]:
        headers = event["request"]["headers"]
        event["request"]["headers"] = {
            k: v for k, v in headers.items()
            if k.lower() not in ("authorization", "x-api-key", "cookie")
        }
    if "user" in event:
        event["user"].pop("email", None)
        event["user"].pop("ip_address", None)
    return event


if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=0.1,
        environment=settings.app_env,
        before_send=_filter_sensitive_data,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Co-host API")
    yield
    # Graceful shutdown: close connection pools
    logger.info("Shutting down — closing connections")
    await ws_redis.aclose()
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title="AI Co-host API",
    version="0.1.0",
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "chrome-extension://*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = "/api/v1"
app.include_router(auth.router, prefix=api_prefix)
app.include_router(shops.router, prefix=api_prefix)
app.include_router(products.router, prefix=api_prefix)
app.include_router(faqs.router, prefix=api_prefix)
app.include_router(personas.router, prefix=api_prefix)
app.include_router(sessions.router, prefix=api_prefix)
app.include_router(scripts.router, prefix=api_prefix)
app.include_router(billing.router, prefix=api_prefix)
app.include_router(tts.router, prefix=api_prefix)
app.include_router(analytics.router, prefix=api_prefix)
app.include_router(webhooks.router, prefix=api_prefix)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


app.websocket("/ws")(ws_handler)
