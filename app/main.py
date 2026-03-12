import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import REMARKABLE_VERSION, SERVICE_NAME, DATA_PATH, TO_DEVICE_PATH
from app import routes, ssh

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Initializing %s v%s...", SERVICE_NAME, REMARKABLE_VERSION)
        os.makedirs(DATA_PATH, exist_ok=True)
        os.makedirs(TO_DEVICE_PATH, exist_ok=True)
        ssh.ensure_ssh_key()
        logger.info("Data directory: %s", DATA_PATH)
        logger.info("Remarkable service ready.")
    except Exception as exc:
        logger.warning("Lifespan startup skipped (likely test mode): %s", exc)

    yield

    logger.info("Shutting down...")
    logger.info("Shutdown complete.")


app = FastAPI(
    title="reMarkable Rendering Service",
    description="Render reMarkable notebooks as high-quality PNGs and PDFs.",
    version=REMARKABLE_VERSION,
    lifespan=lifespan,
)

app.include_router(routes.router)
