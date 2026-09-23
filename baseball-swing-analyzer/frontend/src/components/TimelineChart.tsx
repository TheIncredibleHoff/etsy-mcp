import { useEffect, useRef, useState } from "react";
import type { PhaseMark, PhaseName } from "../api/types";

export interface Series {
  name: string;
  values: number[];
  /** CSS color token, e.g. var(--series-1) */
  color: string;
}

interface Props {
  title: string;
  unit: string;
  series: Series[];
  fps: number;
  phases: Partial<Record<PhaseName, PhaseMark | null>>;
  currentFrame: number;
  onSeek: (frame: number) => void;
}

export const PHASE_LABELS: Record<PhaseName, string> = {
  stance: "Stance",
  stride_start: "Stride",
  foot_plant: "Foot plant",
  swing_start: "Swing",
  contact: "Contact",
};

const HEIGHT = 200;
const PAD = { top: 34, right: 16, bottom: 26, left: 44 };
const LABEL_GAP = 64;

function niceTicks(min: number, max: number, count = 4): number[] {
  const span = max - min || 1;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) ticks.push(+v.toFixed(6));
  return ticks;
}

/** Line chart over the clip's frames, with phase markers and a playhead synced to the video. */
export default function TimelineChart({ title, unit, series, fps, phases, currentFrame, onSeek }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(600);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const n = series[0]?.values.length ?? 0;
  if (n < 2) return null;

  const all = series.flatMap((s) => s.values);
  const ticks = niceTicks(Math.min(0, ...all), Math.max(0, ...all));
  const yMin = Math.min(ticks[0], ...all);
  const yMax = Math.max(ticks[ticks.length - 1], ...all);
  const plotW = Math.max(10, width - PAD.left - PAD.right);
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (i / (n - 1)) * plotW;
  const y = (v: number) => PAD.top + (1 - (v - yMin) / (yMax - yMin || 1)) * plotH;
  const frameAt = (clientX: number, rect: DOMRect) =>
    Math.max(0, Math.min(n - 1, Math.round(((clientX - rect.left - PAD.left) / plotW) * (n - 1))));

  const hoverFrame = hover ?? null;
  const phaseEntries = (
    (Object.entries(phases) as [PhaseName, PhaseMark | null][]).filter(
      ([name, p]) => p && name !== "stance",
    ) as [PhaseName, PhaseMark][]
  ).sort((a, b) => a[1].frame - b[1].frame);
  // Stagger labels onto two rows when phases are close together.
  let lastX = -Infinity;
  let row = 0;
  const labelRows = phaseEntries.map(([, p]) => {
    row = x(p.frame) - lastX < LABEL_GAP ? 1 - row : 0;
    lastX = x(p.frame);
    return row;
  });

  return (
    <figure className="chart">
      <figcaption>
        <span className="chart-title">
          {title} <span className="muted">({unit})</span>
        </span>
        {series.length > 1 && (
          <span className="legend">
            {series.map((s) => (
              <span key={s.name} className="legend-item">
                <span className="legend-swatch" style={{ background: s.color }} />
                {s.name}
              </span>
            ))}
          </span>
        )}
      </figcaption>
      <div ref={wrapRef} className="chart-body">
        <svg
          width={width}
          height={HEIGHT}
          role="img"
          aria-label={`${title} over the swing`}
          onMouseMove={(e) => setHover(frameAt(e.clientX, e.currentTarget.getBoundingClientRect()))}
          onMouseLeave={() => setHover(null)}
          onClick={(e) => onSeek(frameAt(e.clientX, e.currentTarget.getBoundingClientRect()))}
        >
          {ticks.map((t) => (
            <g key={t}>
              <line className={t === 0 ? "axis-zero" : "grid"} x1={PAD.left} x2={PAD.left + plotW} y1={y(t)} y2={y(t)} />
              <text className="tick" x={PAD.left - 6} y={y(t)} dy="0.32em" textAnchor="end">
                {t}
              </text>
            </g>
          ))}
          <text className="tick" x={PAD.left} y={HEIGHT - 6}>
            0s
          </text>
          <text className="tick" x={PAD.left + plotW} y={HEIGHT - 6} textAnchor="end">
            {((n - 1) / fps).toFixed(2)}s
          </text>

          {phaseEntries.map(([name, p], i) => (
            <g key={name}>
              <line className="phase-line" x1={x(p.frame)} x2={x(p.frame)} y1={PAD.top} y2={PAD.top + plotH} />
              <text
                className="phase-label"
                x={x(p.frame)}
                y={PAD.top - 6 - labelRows[i] * 13}
                textAnchor="middle"
              >
                {PHASE_LABELS[name]}
              </text>
            </g>
          ))}

          {series.map((s) => (
            <polyline
              key={s.name}
              fill="none"
              stroke={s.color}
              strokeWidth={2}
              strokeLinejoin="round"
              points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")}
            />
          ))}

          <line className="playhead" x1={x(currentFrame)} x2={x(currentFrame)} y1={PAD.top} y2={PAD.top + plotH} />

          {hoverFrame !== null && (
            <g>
              <line className="crosshair" x1={x(hoverFrame)} x2={x(hoverFrame)} y1={PAD.top} y2={PAD.top + plotH} />
              {series.map((s) => (
                <circle
                  key={s.name}
                  cx={x(hoverFrame)}
                  cy={y(s.values[hoverFrame])}
                  r={4}
                  fill={s.color}
                  stroke="var(--surface)"
                  strokeWidth={2}
                />
              ))}
            </g>
          )}
        </svg>
        {hoverFrame !== null && (
          <div
            className="chart-tooltip"
            style={{
              left: Math.min(x(hoverFrame) + 12, width - 150),
              top: PAD.top,
            }}
          >
            <div className="muted">{(hoverFrame / fps).toFixed(3)}s · click to jump</div>
            {series.map((s) => (
              <div key={s.name} className="tooltip-row">
                <span className="legend-swatch" style={{ background: s.color }} />
                {s.name}
                <strong>
                  {s.values[hoverFrame].toFixed(1)} {unit}
                </strong>
              </div>
            ))}
          </div>
        )}
      </div>
    </figure>
  );
}
