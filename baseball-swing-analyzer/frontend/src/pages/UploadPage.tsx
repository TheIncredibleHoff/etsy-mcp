import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { listVideos, uploadVideo } from "../api/client";
import type { VideoRecord } from "../api/types";
import Dropzone, { isAcceptedFile } from "../components/Dropzone";

export default function UploadPage() {
  const navigate = useNavigate();
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recent, setRecent] = useState<VideoRecord[]>([]);

  useEffect(() => {
    listVideos()
      .then(setRecent)
      .catch(() => setRecent([]));
  }, []);

  const handleFile = async (file: File) => {
    setError(null);
    if (!isAcceptedFile(file)) {
      setError("Please choose an .mp4 or .mov file.");
      return;
    }
    setProgress(0);
    try {
      const record = await uploadVideo(file, setProgress);
      navigate(`/videos/${record.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
      setProgress(null);
    }
  };

  return (
    <div className="page">
      <h1>Analyze a swing</h1>
      <p className="muted">
        Upload a clip of a hitter's swing. We'll track their body frame by frame and turn the
        mechanics into coaching feedback.
      </p>

      <Dropzone disabled={progress !== null} onFile={handleFile} />

      {progress !== null && (
        <div className="progress" aria-label="Upload progress">
          <div className="progress-bar" style={{ width: `${Math.round(progress * 100)}%` }} />
          <span>{progress < 1 ? `Uploading… ${Math.round(progress * 100)}%` : "Processing upload…"}</span>
        </div>
      )}
      {error && <p className="error">{error}</p>}

      {recent.length > 0 && (
        <section className="recent">
          <h2>Recent uploads</h2>
          <ul>
            {recent.map((v) => (
              <li key={v.id}>
                <Link to={`/videos/${v.id}`}>{v.original_filename}</Link>
                <span className="muted">
                  {new Date(v.uploaded_at).toLocaleString()} · {v.info.duration_s.toFixed(1)}s
                </span>
                <span className={`badge badge-${v.status}`}>{v.status}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
