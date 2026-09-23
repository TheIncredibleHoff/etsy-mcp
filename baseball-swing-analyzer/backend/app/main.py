import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import videos
from .config import get_settings
from .services.pipeline import recover_interrupted_jobs

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    recover_interrupted_jobs()
    yield


app = FastAPI(title="Baseball Swing Analyzer API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(videos.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
