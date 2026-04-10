from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import auth, billing, faqs, personas, products, scripts, sessions, shops, webhooks

app = FastAPI(
    title="AI Co-host API",
    version="0.1.0",
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url=None,
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
app.include_router(webhooks.router, prefix=api_prefix)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await websocket.send_json({"type": "error", "message": "not implemented"})
    except WebSocketDisconnect:
        pass
