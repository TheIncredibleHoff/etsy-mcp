import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from .. import storage
from ..config import get_settings
from ..models import HitterProfile, VideoRecord, VideoStatus
from ..services import pipeline
from ..services.video import looks_like_mp4_or_mov, probe

router = APIRouter(prefix="/api/videos", tags=["videos"])

ALLOWED_EXTENSIONS = {".mp4": "video/mp4", ".mov": "video/quicktime"}
CHUNK_SIZE = 1024 * 1024


def _get_record(video_id: str) -> VideoRecord:
    try:
        return storage.load_record(video_id)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Video not found") from None


@router.post("", status_code=status.HTTP_201_CREATED, response_model=VideoRecord)
async def upload_video(file: UploadFile) -> VideoRecord:
    settings = get_settings()
    filename = Path(file.filename or "").name
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only .mp4 and .mov files are supported"
        )

    header = await file.read(12)
    if not looks_like_mp4_or_mov(header):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "File is not a valid MP4/MOV video"
        )

    video_id = uuid.uuid4().hex
    video_dir = storage.video_dir(video_id)
    video_dir.mkdir(parents=True)
    stored_filename = f"original{ext}"
    dest = video_dir / stored_filename

    try:
        size = len(header)
        with dest.open("wb") as out:
            out.write(header)
            while chunk := await file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        f"File exceeds the {settings.max_upload_mb} MB limit",
                    )
                out.write(chunk)

        try:
            info = probe(str(dest))
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unreadable video: {exc}"
            ) from None

        record = VideoRecord(
            id=video_id,
            original_filename=filename,
            stored_filename=stored_filename,
            content_type=ALLOWED_EXTENSIONS[ext],
            size_bytes=size,
            uploaded_at=datetime.now(timezone.utc),
            info=info,
        )
        storage.save_record(record)
    except BaseException:
        shutil.rmtree(video_dir, ignore_errors=True)
        raise
    return record


@router.get("", response_model=list[VideoRecord])
def list_videos() -> list[VideoRecord]:
    return storage.list_records()


@router.get("/{video_id}", response_model=VideoRecord)
def get_video(video_id: str) -> VideoRecord:
    return _get_record(video_id)


@router.get("/{video_id}/file")
def get_video_file(video_id: str) -> FileResponse:
    record = _get_record(video_id)
    return FileResponse(storage.video_file(record), media_type=record.content_type)


def _start_job(record: VideoRecord, **updates) -> VideoRecord:
    if record.status == VideoStatus.processing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Analysis is already running")
    record = record.model_copy(
        update={"status": VideoStatus.processing, "stage": "Queued", "progress": 0.0, "error": None}
        | updates
    )
    storage.save_record(record)
    return record


@router.post("/{video_id}/analyze", status_code=status.HTTP_202_ACCEPTED, response_model=VideoRecord)
def analyze_video(
    video_id: str, background: BackgroundTasks, hitter: HitterProfile | None = None
) -> VideoRecord:
    """Run the full analysis. The optional body describes the hitter."""
    record = _get_record(video_id)
    record = _start_job(record, hitter=hitter or record.hitter)
    storage.delete_json(video_id, pipeline.POSE_FILE, pipeline.METRICS_FILE, pipeline.FEEDBACK_FILE)
    background.add_task(pipeline.run_analysis, video_id)
    return record


@router.post("/{video_id}/feedback", status_code=status.HTTP_202_ACCEPTED, response_model=VideoRecord)
def regenerate_feedback(video_id: str, background: BackgroundTasks) -> VideoRecord:
    """Ask Claude again using the stored metrics, without re-running pose tracking."""
    record = _get_record(video_id)
    if storage.read_json(video_id, pipeline.METRICS_FILE) is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Analyze the video first")
    record = _start_job(record)
    background.add_task(pipeline.run_feedback_only, video_id)
    return record


@router.get("/{video_id}/pose")
def get_pose(video_id: str) -> dict:
    _get_record(video_id)
    pose = storage.read_json(video_id, pipeline.POSE_FILE)
    if pose is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pose data not available yet")
    return pose


@router.get("/{video_id}/analysis")
def get_analysis(video_id: str) -> dict:
    """Metrics plus Claude's feedback (feedback may be absent, skipped, or an error)."""
    _get_record(video_id)
    metrics = storage.read_json(video_id, pipeline.METRICS_FILE)
    if metrics is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not available yet")
    return {"metrics": metrics, "feedback": storage.read_json(video_id, pipeline.FEEDBACK_FILE)}


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(video_id: str) -> None:
    record = _get_record(video_id)
    shutil.rmtree(storage.video_dir(record.id), ignore_errors=True)
