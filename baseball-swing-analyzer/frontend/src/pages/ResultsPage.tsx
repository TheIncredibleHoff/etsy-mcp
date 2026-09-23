import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { analyzeVideo, getPose, getVideo, videoFileUrl } from "../api/client";
import type { PoseData, VideoRecord } from "../api/types";
import PoseOverlay from "../components/PoseOverlay";
import VideoControls from "../components/VideoControls";

const POLL_MS = 1000;

export default function ResultsPage() {
  const { id = "" } = useParams();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [video, setVideo] = useState<VideoRecord | null>(null);
  const [pose, setPose] = useState<PoseData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showSkeleton, setShowSkeleton] = useState(true);

  const refresh = useCallback(async () => {
    const record = await getVideo(id);
    setVideo(record);
    if (record.status === "complete") setPose(await getPose(id));
    return record;
  }, [id]);

  useEffect(() => {
    setVideo(null);
    setPose(null);
    setError(null);
    refresh().catch((e) => setError(e.message));
  }, [refresh]);

  // Poll while the analysis job runs.
  const processing = video?.status === "processing";
  useEffect(() => {
    if (!processing) return;
    const timer = setInterval(() => {
      refresh().catch((e) => setError(e.message));
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [processing, refresh]);

  const startAnalysis = async () => {
    setError(null);
    try {
      setVideo(await analyzeVideo(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start analysis");
    }
  };

  if (!video) return error ? <p className="error">{error}</p> : <p className="muted">Loading…</p>;

  return (
    <div className="page">
      <div className="results-header">
        <div>
          <h1>{video.original_filename}</h1>
          <p className="muted">
            {video.info.width}×{video.info.height} · {video.info.fps.toFixed(0)} fps ·{" "}
            {video.info.duration_s.toFixed(1)}s
          </p>
        </div>
        {!processing && (
          <button className="primary" onClick={startAnalysis}>
            {video.status === "uploaded" ? "Analyze swing" : "Re-analyze"}
          </button>
        )}
      </div>

      {processing && (
        <div className="progress" aria-label="Analysis progress">
          <div className="progress-bar" style={{ width: `${Math.round(video.progress * 100)}%` }} />
          <span>
            {video.stage ?? "Working"}… {Math.round(video.progress * 100)}%
          </span>
        </div>
      )}
      {video.status === "failed" && <p className="error">Analysis failed: {video.error}</p>}
      {error && <p className="error">{error}</p>}

      <div className="player-wrap">
        <video
          ref={videoRef}
          className="player"
          src={videoFileUrl(video.id)}
          controls
          playsInline
          muted
        />
        {pose && <PoseOverlay videoRef={videoRef} pose={pose} options={{ skeleton: showSkeleton }} />}
      </div>

      <div className="toolbar">
        <VideoControls videoRef={videoRef} fps={video.info.fps} />
        {pose && (
          <label className="toggle">
            <input
              type="checkbox"
              checked={showSkeleton}
              onChange={(e) => setShowSkeleton(e.target.checked)}
            />
            Skeleton
          </label>
        )}
      </div>
      {pose && (
        <p className="muted small">
          Tracked the hitter in {pose.frames.filter(Boolean).length} of {pose.frame_count} frames
          {pose.truncated ? " (clip was trimmed to the first part)" : ""}.
        </p>
      )}
    </div>
  );
}
