import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from .. import storage
from ..config import get_settings
from ..models import VideoRecord
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


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(video_id: str) -> None:
    record = _get_record(video_id)
    shutil.rmtree(storage.video_dir(record.id), ignore_errors=True)
