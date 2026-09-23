from app.services import pipeline


def _upload(client, data):
    res = client.post("/api/videos", files={"file": ("swing.mp4", data, "video/mp4")})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _fake_pose(frames):
    return {"fps": 30.0, "width": 160, "height": 120, "frame_count": len(frames), "frames": frames}


def test_analyze_stores_pose(client, sample_mp4, monkeypatch):
    frame = {"image": [[0.5, 0.5, 0.0, 1.0]] * 33, "world": [[0.0, 0.0, 0.0]] * 33}
    monkeypatch.setattr(pipeline, "estimate_poses", lambda path, on_progress: _fake_pose([frame, None]))
    video_id = _upload(client, sample_mp4)

    assert client.get(f"/api/videos/{video_id}/pose").status_code == 404
    res = client.post(f"/api/videos/{video_id}/analyze")
    assert res.status_code == 202
    assert res.json()["status"] == "processing"

    # TestClient runs background tasks before returning.
    record = client.get(f"/api/videos/{video_id}").json()
    assert record["status"] == "complete", record
    pose = client.get(f"/api/videos/{video_id}/pose").json()
    assert pose["frame_count"] == 2


def test_analyze_fails_when_no_person(client, sample_mp4, monkeypatch):
    monkeypatch.setattr(pipeline, "estimate_poses", lambda path, on_progress: _fake_pose([None, None]))
    video_id = _upload(client, sample_mp4)
    client.post(f"/api/videos/{video_id}/analyze")
    record = client.get(f"/api/videos/{video_id}").json()
    assert record["status"] == "failed"
    assert "No person" in record["error"]


def test_cannot_start_twice(client, sample_mp4):
    from app import storage
    from app.models import VideoStatus

    video_id = _upload(client, sample_mp4)
    record = storage.load_record(video_id)
    storage.save_record(record.model_copy(update={"status": VideoStatus.processing}))
    assert client.post(f"/api/videos/{video_id}/analyze").status_code == 409


def test_interrupted_jobs_marked_failed(client, sample_mp4):
    from app import storage
    from app.models import VideoStatus

    video_id = _upload(client, sample_mp4)
    record = storage.load_record(video_id)
    storage.save_record(record.model_copy(update={"status": VideoStatus.processing}))
    pipeline.recover_interrupted_jobs()
    assert storage.load_record(video_id).status == VideoStatus.failed
