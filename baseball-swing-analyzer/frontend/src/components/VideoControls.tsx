import type { RefObject } from "react";

interface Props {
  videoRef: RefObject<HTMLVideoElement | null>;
  fps: number;
}

const RATES = [0.25, 0.5, 1];

/** Frame stepping and slow-motion controls — the useful ones for swing review. */
export default function VideoControls({ videoRef, fps }: Props) {
  const step = (frames: number) => {
    const v = videoRef.current;
    if (!v) return;
    v.pause();
    v.currentTime = Math.max(0, Math.min(v.duration || 0, v.currentTime + frames / fps));
  };
  const setRate = (rate: number) => {
    if (videoRef.current) videoRef.current.playbackRate = rate;
  };

  return (
    <div className="video-controls">
      <button onClick={() => step(-1)} title="Previous frame">
        ◀ Frame
      </button>
      <button onClick={() => step(1)} title="Next frame">
        Frame ▶
      </button>
      <span className="muted">Speed</span>
      {RATES.map((r) => (
        <button key={r} onClick={() => setRate(r)}>
          {r}×
        </button>
      ))}
    </div>
  );
}
