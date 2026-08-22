import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import edges, nodes, register
from app.config import get_settings
from app.mqtt_ingestion import build_ingestion_service
from app.retention import run_retention_cleanup
from app.scheduler import scheduler

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    mqtt_service = build_ingestion_service()
    app.state.mqtt_service = mqtt_service
    mqtt_task = asyncio.create_task(mqtt_service.run())

    scheduler.add_job(run_retention_cleanup, "interval", minutes=10, id="retention-cleanup")
    scheduler.start()

    logger.info("central-system startup complete")
    try:
        yield
    finally:
        mqtt_service.stop()
        mqtt_task.cancel()
        scheduler.shutdown(wait=False)


app = FastAPI(title="central-system", lifespan=lifespan)

# Local hackathon demo only — dashboard/ is a browser app on a different origin/port. Tighten
# this before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(nodes.router)
app.include_router(edges.router)
app.include_router(register.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
