from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import videos
from .config import get_settings

settings = get_settings()

app = FastAPI(title="Baseball Swing Analyzer API")
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
