import { useEffect, useRef, type RefObject } from "react";
import type { PoseData } from "../api/types";

const MIN_VISIBILITY = 0.5;

// Landmarks 0-10 are the face; we draw the head as a single point (the nose).
const FACE_LANDMARKS = new Set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);

export interface OverlayOptions {
  skeleton: boolean;
  /** Extra drawing on top of the skeleton, e.g. the bat path. */
  extras?: (ctx: CanvasRenderingContext2D, toPx: ToPx, frameIndex: number) => void;
}

export type ToPx = (x: number, y: number) => [number, number];

interface Props {
  videoRef: RefObject<HTMLVideoElement | null>;
  pose: PoseData;
  options: OverlayOptions;
  onFrame?: (frameIndex: number) => void;
}

export function frameIndexAt(time: number, pose: PoseData): number {
  return Math.max(0, Math.min(pose.frames.length - 1, Math.round(time * pose.fps)));
}

/** A canvas laid over a <video> that redraws the pose for whatever frame is showing. */
export default function PoseOverlay({ videoRef, pose, options, onFrame }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const optionsRef = useRef(options);
  optionsRef.current = options;
  const onFrameRef = useRef(onFrame);
  onFrameRef.current = onFrame;
  const redrawRef = useRef<() => void>(() => {});

  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    const ctx = canvas.getContext("2d")!;
    let lastIndex = -1;

    const draw = (time: number) => {
      const dpr = window.devicePixelRatio || 1;
      const cw = video.clientWidth;
      const ch = video.clientHeight;
      if (canvas.width !== Math.round(cw * dpr) || canvas.height !== Math.round(ch * dpr)) {
        canvas.width = Math.round(cw * dpr);
        canvas.height = Math.round(ch * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, cw, ch);

      // The video is letterboxed (object-fit: contain) inside its element.
      const vw = video.videoWidth || pose.width;
      const vh = video.videoHeight || pose.height;
      const scale = Math.min(cw / vw, ch / vh);
      const dw = vw * scale;
      const dh = vh * scale;
      const ox = (cw - dw) / 2;
      const oy = (ch - dh) / 2;
      const toPx: ToPx = (x, y) => [ox + x * dw, oy + y * dh];

      const index = frameIndexAt(time, pose);
      if (index !== lastIndex) {
        lastIndex = index;
        onFrameRef.current?.(index);
      }
      const frame = pose.frames[index];
      const { skeleton, extras } = optionsRef.current;

      if (frame && skeleton) {
        const lm = frame.image;
        const visible = (i: number) => lm[i][3] >= MIN_VISIBILITY;
        ctx.lineWidth = 3;
        ctx.lineCap = "round";
        ctx.strokeStyle = "rgba(255, 255, 255, 0.85)";
        for (const [a, b] of pose.connections) {
          if (FACE_LANDMARKS.has(a) || FACE_LANDMARKS.has(b)) continue;
          if (!visible(a) || !visible(b)) continue;
          const [x1, y1] = toPx(lm[a][0], lm[a][1]);
          const [x2, y2] = toPx(lm[b][0], lm[b][1]);
          ctx.beginPath();
          ctx.moveTo(x1, y1);
          ctx.lineTo(x2, y2);
          ctx.stroke();
        }
        lm.forEach((p, i) => {
          if (FACE_LANDMARKS.has(i) || p[3] < MIN_VISIBILITY) return;
          const [x, y] = toPx(p[0], p[1]);
          ctx.beginPath();
          ctx.arc(x, y, 4, 0, Math.PI * 2);
          // Left side of the body in orange, right side in blue.
          ctx.fillStyle = i === 0 ? "#ffffff" : i % 2 === 1 ? "#ff9f1c" : "#2ec4f1";
          ctx.fill();
        });
      }
      extras?.(ctx, toPx, index);
    };

    let handle = 0;
    let cancelled = false;
    const hasVfc = "requestVideoFrameCallback" in HTMLVideoElement.prototype;

    // requestVideoFrameCallback gives the exact media time of the frame that
    // was just presented, keeping the overlay in sync while playing.
    const onVideoFrame = (_now: number, meta: VideoFrameCallbackMetadata) => {
      if (cancelled) return;
      draw(meta.mediaTime);
      handle = video.requestVideoFrameCallback(onVideoFrame);
    };
    const onAnimationFrame = () => {
      if (cancelled) return;
      draw(video.currentTime);
      handle = requestAnimationFrame(onAnimationFrame);
    };
    if (hasVfc) handle = video.requestVideoFrameCallback(onVideoFrame);
    else handle = requestAnimationFrame(onAnimationFrame);

    // Frame callbacks don't fire while paused, so also redraw on seeks/resizes.
    const redraw = () => draw(video.currentTime);
    redrawRef.current = redraw;
    video.addEventListener("seeked", redraw);
    video.addEventListener("loadeddata", redraw);
    const resize = new ResizeObserver(redraw);
    resize.observe(video);
    redraw();

    return () => {
      cancelled = true;
      if (hasVfc) video.cancelVideoFrameCallback(handle);
      else cancelAnimationFrame(handle);
      video.removeEventListener("seeked", redraw);
      video.removeEventListener("loadeddata", redraw);
      resize.disconnect();
    };
  }, [videoRef, pose]);

  // Redraw immediately when toggles change while paused.
  useEffect(() => redrawRef.current(), [options.skeleton, options.extras]);

  return <canvas ref={canvasRef} className="overlay" />;
}
