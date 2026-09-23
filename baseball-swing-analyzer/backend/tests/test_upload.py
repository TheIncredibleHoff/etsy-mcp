def test_upload_mp4_roundtrip(client, sample_mp4):
    res = client.post("/api/videos", files={"file": ("swing.mp4", sample_mp4, "video/mp4")})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["original_filename"] == "swing.mp4"
    assert body["status"] == "uploaded"
    assert body["info"]["frame_count"] == 30
    assert body["info"]["width"] == 160

    video_id = body["id"]
    assert client.get(f"/api/videos/{video_id}").json()["id"] == video_id
    assert [v["id"] for v in client.get("/api/videos").json()] == [video_id]

    file_res = client.get(f"/api/videos/{video_id}/file")
    assert file_res.status_code == 200
    assert file_res.content == sample_mp4

    assert client.delete(f"/api/videos/{video_id}").status_code == 204
    assert client.get(f"/api/videos/{video_id}").status_code == 404


def test_mov_extension_accepted(client, sample_mp4):
    res = client.post("/api/videos", files={"file": ("swing.MOV", sample_mp4, "video/quicktime")})
    assert res.status_code == 201, res.text
    assert res.json()["content_type"] == "video/quicktime"


def test_rejects_wrong_extension(client, sample_mp4):
    res = client.post("/api/videos", files={"file": ("swing.avi", sample_mp4, "video/x-msvideo")})
    assert res.status_code == 415


def test_rejects_non_video_bytes(client):
    res = client.post("/api/videos", files={"file": ("swing.mp4", b"not a video at all", "video/mp4")})
    assert res.status_code == 415


def test_rejects_undecodable_container(client, isolated_storage):
    fake = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 100
    res = client.post("/api/videos", files={"file": ("swing.mp4", fake, "video/mp4")})
    assert res.status_code == 422
    # Nothing is left behind on disk.
    assert list((isolated_storage / "videos").iterdir()) == []


def test_rejects_oversized_upload(client, sample_mp4, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("MAX_UPLOAD_MB", "0")
    get_settings.cache_clear()
    res = client.post("/api/videos", files={"file": ("swing.mp4", sample_mp4, "video/mp4")})
    assert res.status_code == 413


def test_invalid_id_is_404(client):
    assert client.get("/api/videos/..%2F..%2Fetc").status_code == 404
    assert client.get("/api/videos/not-a-real-id").status_code == 404
