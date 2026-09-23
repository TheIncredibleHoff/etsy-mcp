import type { Metric, MetricCategory } from "../api/types";

const CATEGORIES: { key: MetricCategory; title: string }[] = [
  { key: "rotation", title: "Rotation" },
  { key: "bat_path", title: "Bat path" },
  { key: "posture", title: "Posture" },
  { key: "stride", title: "Stride" },
  { key: "timing", title: "Timing" },
];

function format(m: Metric): string {
  if (m.value === null) return "—";
  const digits = Math.abs(m.value) >= 100 || m.unit === "ms" ? 0 : 1;
  return m.value.toFixed(digits);
}

interface Props {
  metrics: Metric[];
  highlighted: Set<string>;
}

export default function MetricsPanel({ metrics, highlighted }: Props) {
  return (
    <div className="metric-groups">
      {CATEGORIES.map(({ key, title }) => {
        const group = metrics.filter((m) => m.category === key);
        if (!group.length) return null;
        return (
          <section key={key} className="metric-group">
            <h3>{title}</h3>
            <div className="metric-grid">
              {group.map((m) => (
                <div
                  key={m.key}
                  className={`metric-tile${highlighted.has(m.key) ? " highlighted" : ""}`}
                  title={m.description}
                >
                  <div className="metric-label">{m.label}</div>
                  <div className="metric-value">
                    {format(m)}
                    {m.value !== null && <span className="metric-unit">{m.unit}</span>}
                  </div>
                  <div className="metric-desc">{m.description}</div>
                </div>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
