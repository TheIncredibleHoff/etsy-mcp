from app.services import pipeline

from .synthetic import make_pose


def _upload(client, data):
    res = client.post("/api/videos", files={"file": ("swing.mp4", data, "video/mp4")})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _fake_pose(frames):
    return {"fps": 30.0, "width": 160, "height": 120, "frame_count": len(frames), "frames": frames}


FAKE_FEEDBACK = {"status": "ok", "model": "test", "feedback": {"summary": "Nice swing."}}


def test_full_analysis(client, sample_mp4, monkeypatch):
    monkeypatch.setattr(pipeline, "estimate_poses", lambda path, on_progress: make_pose())
    seen = {}

    def fake_feedback(metrics, hitter):
        seen["hitter"] = hitter
        return FAKE_FEEDBACK

    monkeypatch.setattr(pipeline, "generate_feedback", fake_feedback)
    video_id = _upload(client, sample_mp4)

    assert client.get(f"/api/videos/{video_id}/pose").status_code == 404
    assert client.get(f"/api/videos/{video_id}/analysis").status_code == 404
    res = client.post(
        f"/api/videos/{video_id}/analyze", json={"height_in": 70, "level": "high_school"}
    )
    assert res.status_code == 202
    assert res.json()["status"] == "processing"

    # TestClient runs background tasks before returning.
    record = client.get(f"/api/videos/{video_id}").json()
    assert record["status"] == "complete", record
    assert record["hitter"]["height_in"] == 70
    assert seen["hitter"].level == "high_school"
    assert client.get(f"/api/videos/{video_id}/pose").json()["frame_count"] > 0

    analysis = client.get(f"/api/videos/{video_id}/analysis").json()
    assert analysis["metrics"]["bats"] == "right"
    assert analysis["feedback"] == FAKE_FEEDBACK


def test_analyze_without_body(client, sample_mp4, monkeypatch):
    monkeypatch.setattr(pipeline, "estimate_poses", lambda path, on_progress: make_pose())
    monkeypatch.setattr(pipeline, "generate_feedback", lambda m, h: FAKE_FEEDBACK)
    video_id = _upload(client, sample_mp4)
    assert client.post(f"/api/videos/{video_id}/analyze").status_code == 202
    assert client.get(f"/api/videos/{video_id}").json()["status"] == "complete"


def test_rejects_bad_hitter_profile(client, sample_mp4):
    video_id = _upload(client, sample_mp4)
    res = client.post(f"/api/videos/{video_id}/analyze", json={"height_in": 500})
    assert res.status_code == 422


def test_feedback_error_keeps_metrics(client, sample_mp4, monkeypatch):
    from app.services.coaching import CoachingError

    def boom(metrics, hitter):
        raise CoachingError("API down")

    monkeypatch.setattr(pipeline, "estimate_poses", lambda path, on_progress: make_pose())
    monkeypatch.setattr(pipeline, "generate_feedback", boom)
    video_id = _upload(client, sample_mp4)
    client.post(f"/api/videos/{video_id}/analyze")

    assert client.get(f"/api/videos/{video_id}").json()["status"] == "complete"
    analysis = client.get(f"/api/videos/{video_id}/analysis").json()
    assert analysis["feedback"] == {"status": "error", "error": "API down"}

    # Regenerating only re-runs the feedback step.
    monkeypatch.setattr(pipeline, "estimate_poses", None)
    monkeypatch.setattr(pipeline, "generate_feedback", lambda m, h: FAKE_FEEDBACK)
    assert client.post(f"/api/videos/{video_id}/feedback").status_code == 202
    assert client.get(f"/api/videos/{video_id}/analysis").json()["feedback"] == FAKE_FEEDBACK


def test_feedback_requires_analysis(client, sample_mp4):
    video_id = _upload(client, sample_mp4)
    assert client.post(f"/api/videos/{video_id}/feedback").status_code == 409


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
