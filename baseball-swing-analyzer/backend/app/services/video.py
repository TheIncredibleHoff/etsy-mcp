import cv2

from ..models import VideoInfo

# Both MP4 and QuickTime (MOV) files are ISO base-media containers: bytes 4-8
# hold the type of the first box. Modern files start with "ftyp"; older
# QuickTime files may start with one of the others.
_CONTAINER_BOX_TYPES = {b"ftyp", b"moov", b"mdat", b"wide", b"free", b"skip", b"pnot"}


def looks_like_mp4_or_mov(header: bytes) -> bool:
    return len(header) >= 8 and header[4:8] in _CONTAINER_BOX_TYPES


def probe(path: str) -> VideoInfo:
    """Read basic stream info. Raises ValueError if OpenCV can't decode the file."""
    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            raise ValueError("Could not open video")
        ok, _ = cap.read()
        if not ok:
            raise ValueError("Could not decode any frames")
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        cap.release()
    return VideoInfo(
        fps=round(fps, 3),
        frame_count=frame_count,
        width=width,
        height=height,
        duration_s=round(frame_count / fps, 3) if fps else 0.0,
    )
