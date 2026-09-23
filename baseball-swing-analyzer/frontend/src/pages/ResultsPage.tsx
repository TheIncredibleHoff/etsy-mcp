import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  analyzeVideo,
  getAnalysis,
  getPose,
  getVideo,
  regenerateFeedback,
  videoFileUrl,
} from "../api/client";
import type { Analysis, HitterProfile, PhaseName, PoseData, VideoRecord } from "../api/types";
import FeedbackPanel from "../components/FeedbackPanel";
import HitterForm from "../components/HitterForm";
import MetricsPanel from "../components/MetricsPanel";
import PoseOverlay, { type OverlayOptions, type ToPx } from "../components/PoseOverlay";
import TimelineChart, { PHASE_LABELS } from "../components/TimelineChart";
import VideoControls from "../components/VideoControls";

const POLL_MS = 1000;
const PHASE_ORDER: PhaseName[] = ["stance", "stride_start", "foot_plant", "swing_start", "contact"];

export default function ResultsPage() {
  const { id = "" } = useParams();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [video, setVideo] = useState<VideoRecord | null>(null);
  const [pose, setPose] = useState<PoseData | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [showSkeleton, setShowSkeleton] = useState(true);
  const [showHandPath, setShowHandPath] = useState(true);
  const [frame, setFrame] = useState(0);
  const [highlighted, setHighlighted] = useState<Set<string>>(new Set());

  const refresh = useCallback(async () => {
    const record = await getVideo(id);
    setVideo(record);
    if (record.status === "complete") {
      const [p, a] = await Promise.all([getPose(id), getAnalysis(id)]);
      setPose(p);
      setAnalysis(a);
    }
    return record;
  }, [id]);

  useEffect(() => {
    setVideo(null);
    setPose(null);
    setAnalysis(null);
    setError(null);
    refresh().catch((e) => setError(e.message));
  }, [refresh]);

  // Poll while a job runs.
  const processing = video?.status === "processing";
  useEffect(() => {
    if (!processing) return;
    const timer = setInterval(() => {
      refresh().catch((e) => setError(e.message));
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [processing, refresh]);

  const startJob = async (job: () => Promise<VideoRecord>) => {
    setError(null);
    setShowForm(false);
    try {
      setVideo(await job());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start analysis");
    }
  };

  const metrics = analysis?.metrics ?? null;
  const fps = metrics?.fps ?? video?.info.fps ?? 30;

  const seek = useCallback(
    (f: number) => {
      const v = videoRef.current;
      if (!v) return;
      v.pause();
      v.currentTime = (f + 0.1) / fps;
    },
    [fps],
  );

  // Draw the hands' path (our bat-path proxy) up to the current frame.
  const drawHandPath = useCallback(
    (ctx: CanvasRenderingContext2D, toPx: ToPx, index: number) => {
      if (!metrics) return;
      const path = metrics.hand_path;
      const contact = metrics.phases.contact?.frame ?? path.length - 1;
      const start = metrics.phases.swing_start?.frame ?? 0;
      const from = Math.max(0, start - Math.round(fps * 0.15));
      const to = Math.min(index, path.length - 1, contact + Math.round(fps * 0.25));
      if (to <= from) return;
      ctx.lineWidth = 4;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.strokeStyle = "rgba(255, 214, 10, 0.9)";
      ctx.beginPath();
      path.slice(from, to + 1).forEach(([x, y], i) => {
        const [px, py] = toPx(x, y);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      });
      ctx.stroke();
      if (index >= contact) {
        const [cx, cy] = toPx(...path[contact]);
        ctx.beginPath();
        ctx.arc(cx, cy, 8, 0, Math.PI * 2);
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    },
    [metrics, fps],
  );

  const overlayOptions: OverlayOptions = useMemo(
    () => ({ skeleton: showSkeleton, extras: showHandPath ? drawHandPath : undefined }),
    [showSkeleton, showHandPath, drawHandPath],
  );

  const currentPhase = useMemo(() => {
    if (!metrics) return null;
    let current: PhaseName | null = null;
    for (const name of PHASE_ORDER) {
      const p = metrics.phases[name];
      if (p && p.frame <= frame) current = name;
    }
    return current;
  }, [metrics, frame]);

  if (!video) return error ? <p className="error">{error}</p> : <p className="muted">Loading…</p>;

  const hasResults = video.status === "complete" && metrics && pose && analysis;
  const needsForm = !processing && (video.status === "uploaded" || showForm);

  return (
    <div className="page">
      <div className="results-header">
        <div>
          <h1>{video.original_filename}</h1>
          <p className="muted">
            {video.info.width}×{video.info.height} · {video.info.fps.toFixed(0)} fps ·{" "}
            {video.info.duration_s.toFixed(1)}s
            {metrics && ` · ${metrics.bats === "right" ? "Right" : "Left"}-handed hitter`}
          </p>
        </div>
        {!processing && video.status !== "uploaded" && !showForm && (
          <button onClick={() => setShowForm(true)}>Re-analyze</button>
        )}
      </div>

      {needsForm && (
        <HitterForm
          initial={video.hitter}
          submitLabel={video.status === "uploaded" ? "Analyze swing" : "Re-analyze"}
          onSubmit={(hitter: HitterProfile) => startJob(() => analyzeVideo(id, hitter))}
        />
      )}

      {processing && (
        <div className="progress" aria-label="Analysis progress">
          <div className="progress-bar" style={{ width: `${Math.round(video.progress * 100)}%` }} />
          <span>
            {video.stage ?? "Working"}
            {video.progress > 0 && video.progress < 1 ? ` · ${Math.round(video.progress * 100)}%` : "…"}
          </span>
        </div>
      )}
      {video.status === "failed" && <p className="error">Analysis failed: {video.error}</p>}
      {error && <p className="error">{error}</p>}

      <div className={hasResults ? "results-layout" : undefined}>
        <div className="results-main">
          <div className="player-wrap">
            <video
              ref={videoRef}
              className="player"
              src={videoFileUrl(video.id)}
              controls
              playsInline
              muted
            />
            {pose && (
              <PoseOverlay videoRef={videoRef} pose={pose} options={overlayOptions} onFrame={setFrame} />
            )}
            {currentPhase && <span className="phase-badge">{PHASE_LABELS[currentPhase]}</span>}
          </div>

          <div className="toolbar">
            <VideoControls videoRef={videoRef} fps={fps} />
            {pose && (
              <span>
                <label className="toggle">
                  <input type="checkbox" checked={showSkeleton} onChange={(e) => setShowSkeleton(e.target.checked)} />
                  Skeleton
                </label>
                {metrics && (
                  <label className="toggle">
                    <input type="checkbox" checked={showHandPath} onChange={(e) => setShowHandPath(e.target.checked)} />
                    Hand path
                  </label>
                )}
              </span>
            )}
          </div>

          {metrics && (
            <div className="phase-buttons" role="group" aria-label="Jump to swing phase">
              {PHASE_ORDER.map((name) => {
                const p = metrics.phases[name];
                return (
                  <button
                    key={name}
                    disabled={!p}
                    className={currentPhase === name ? "active" : undefined}
                    onClick={() => p && seek(p.frame)}
                  >
                    {PHASE_LABELS[name]}
                    {p && <span className="muted"> {p.time_s.toFixed(2)}s</span>}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {hasResults && (
          <aside className="results-side">
            <FeedbackPanel
              result={analysis.feedback}
              busy={processing}
              onRegenerate={() => startJob(() => regenerateFeedback(id))}
              onHighlight={(keys) => setHighlighted(new Set(keys))}
            />
          </aside>
        )}
      </div>

      {hasResults && (
        <>
          {metrics.warnings.length > 0 && (
            <ul className="warnings">
              {metrics.warnings.map((w) => (
                <li key={w}>⚠️ {w}</li>
              ))}
            </ul>
          )}

          <h2 className="section-title">Swing metrics</h2>
          <MetricsPanel metrics={metrics.metrics} highlighted={highlighted} />

          <h2 className="section-title">Through the swing</h2>
          <div className="charts">
            <TimelineChart
              title="Rotation from stance"
              unit="°"
              fps={fps}
              phases={metrics.phases}
              currentFrame={frame}
              onSeek={seek}
              series={[
                { name: "Hips", values: metrics.series.hip_rotation, color: "var(--series-1)" },
                { name: "Shoulders", values: metrics.series.shoulder_rotation, color: "var(--series-2)" },
              ]}
            />
            <TimelineChart
              title="Hand speed"
              unit="ht/s"
              fps={fps}
              phases={metrics.phases}
              currentFrame={frame}
              onSeek={seek}
              series={[{ name: "Hand speed", values: metrics.series.hand_speed, color: "var(--series-1)" }]}
            />
          </div>
          <p className="muted small">
            Tracked the hitter in {Math.round(metrics.tracking_coverage * 100)}% of {pose.frame_count} frames
            {pose.truncated ? " (long clip — only the first part was analyzed)" : ""}. Hand speed is in body
            heights per second.
          </p>
        </>
      )}
    </div>
  );
}
