import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, init_db, AsyncSessionLocal
from seed import seed_if_empty
from websocket_manager import manager
from dashboard import build_dashboard_state
from routes.regions import router as regions_router
from routes.counts import router as counts_router
from routes.admin import router as admin_router
from config import get_settings

settings = get_settings()


async def offline_heartbeat():
    """Broadcast dashboard state every 5s so offline cameras show within ~17s."""
    while True:
        await asyncio.sleep(5)
        try:
            async with AsyncSessionLocal() as db:
                state = await build_dashboard_state(db)
                await manager.broadcast(state.model_dump_json())
        except Exception:
            pass


_PLACEHOLDER_SECRETS = {
    "change-this-to-a-random-64-char-string",
    "replace-with-a-random-64-char-string",
}
_PLACEHOLDER_PASSWORDS = {"bits2024", "change-this-password"}


def _refuse_insecure_production_config() -> None:
    """On a real (Postgres) deployment, refuse to boot with placeholder secrets.

    These defaults are visible in the public repo, so running with them would let
    anyone forge admin tokens, log in, or post counts.
    """
    if settings.DATABASE_URL.startswith("sqlite"):
        return  # local dev
    problems = []
    if settings.SECRET_KEY in _PLACEHOLDER_SECRETS:
        problems.append("SECRET_KEY is a placeholder")
    if settings.ADMIN_PASSWORD in _PLACEHOLDER_PASSWORDS:
        problems.append("ADMIN_PASSWORD is a placeholder")
    if not settings.DEVICE_API_KEY:
        problems.append("DEVICE_API_KEY is empty (counts would be accepted from anyone)")
    if problems:
        raise RuntimeError("Insecure production config: " + "; ".join(problems))


@asynccontextmanager
async def lifespan(app: FastAPI):
    _refuse_insecure_production_config()
    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_if_empty(session)
    task = asyncio.create_task(offline_heartbeat())
    yield
    task.cancel()


app = FastAPI(title="Campus Library Occupancy Dashboard", lifespan=lifespan)

_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
_allow_all = _origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # credentials can't be combined with a wildcard origin per the CORS spec
    allow_credentials=not _allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(regions_router, prefix="/regions", tags=["regions"])
app.include_router(counts_router, prefix="/count", tags=["counts"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])


@app.api_route("/health", methods=["GET", "HEAD"], tags=["health"])
async def health():
    """Uptime-monitor ping (UptimeRobot sends HEAD). No DB hit, no data exposed."""
    return {"status": "ok"}


@app.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    await manager.connect(websocket)
    try:
        # Send current state immediately on connect
        state = await build_dashboard_state(db)
        await websocket.send_text(state.model_dump_json())
        while True:
            await websocket.receive_text()  # keepalive — client pings to stay alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)
