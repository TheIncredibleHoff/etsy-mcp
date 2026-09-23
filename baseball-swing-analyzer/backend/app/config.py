from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-5"
    storage_dir: Path = Path("storage")
    max_upload_mb: int = 200
    cors_origins: str = "http://localhost:5173"
    pose_model_path: Path = Path("storage/models/pose_landmarker_full.task")
    pose_model_url: str = (
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        "pose_landmarker_full/float16/latest/pose_landmarker_full.task"
    )
    max_analysis_frames: int = 900

    @property
    def storage_path(self) -> Path:
        path = self.storage_dir if self.storage_dir.is_absolute() else BACKEND_DIR / self.storage_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def pose_model_file(self) -> Path:
        path = self.pose_model_path
        return path if path.is_absolute() else BACKEND_DIR / path

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
