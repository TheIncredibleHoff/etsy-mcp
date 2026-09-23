import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getVideo, videoFileUrl } from "../api/client";
import type { VideoRecord } from "../api/types";

export default function ResultsPage() {
  const { id = "" } = useParams();
  const [video, setVideo] = useState<VideoRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getVideo(id)
      .then(setVideo)
      .catch((e) => setError(e.message));
  }, [id]);

  if (error) return <p className="error">{error}</p>;
  if (!video) return <p className="muted">Loading…</p>;

  return (
    <div className="page">
      <h1>{video.original_filename}</h1>
      <p className="muted">
        {video.info.width}×{video.info.height} · {video.info.fps.toFixed(0)} fps ·{" "}
        {video.info.duration_s.toFixed(1)}s
      </p>
      <video className="player" src={videoFileUrl(video.id)} controls playsInline />
    </div>
  );
}
