import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()
    yield tmp_path / "storage"
    get_settings.cache_clear()


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


@pytest.fixture
def sample_mp4(tmp_path) -> bytes:
    """A tiny synthetic MP4 (a moving square) that OpenCV can decode."""
    path = tmp_path / "sample.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (160, 120))
    for i in range(30):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        cv2.rectangle(frame, (i * 4, 40), (i * 4 + 20, 60), (255, 255, 255), -1)
        writer.write(frame)
    writer.release()
    return path.read_bytes()
