import { useState } from "react";
import type { HitterLevel, HitterProfile } from "../api/types";

const LEVELS: { value: HitterLevel; label: string }[] = [
  { value: "youth", label: "Youth" },
  { value: "high_school", label: "High school" },
  { value: "college", label: "College" },
  { value: "pro", label: "Pro" },
  { value: "adult", label: "Adult / rec league" },
];

interface Props {
  initial: HitterProfile;
  submitLabel: string;
  onSubmit: (hitter: HitterProfile) => void;
}

/** Optional hitter details: height turns relative measurements into inches and mph. */
export default function HitterForm({ initial, submitLabel, onSubmit }: Props) {
  const [feet, setFeet] = useState(initial.height_in ? String(Math.floor(initial.height_in / 12)) : "");
  const [inches, setInches] = useState(initial.height_in ? String(Math.round(initial.height_in % 12)) : "");
  const [level, setLevel] = useState<HitterLevel | "">(initial.level ?? "");
  const [notes, setNotes] = useState(initial.notes ?? "");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const total = (Number(feet) || 0) * 12 + (Number(inches) || 0);
    onSubmit({
      height_in: total > 36 && total < 96 ? total : null,
      level: level || null,
      notes: notes.trim() || null,
    });
  };

  return (
    <form className="card hitter-form" onSubmit={submit}>
      <div className="form-row">
        <label>
          Height
          <span className="inline-inputs">
            <input type="number" min={3} max={7} placeholder="ft" value={feet} onChange={(e) => setFeet(e.target.value)} aria-label="Feet" />
            <input type="number" min={0} max={11} placeholder="in" value={inches} onChange={(e) => setInches(e.target.value)} aria-label="Inches" />
          </span>
        </label>
        <label>
          Level
          <select value={level} onChange={(e) => setLevel(e.target.value as HitterLevel | "")}>
            <option value="">Not specified</option>
            {LEVELS.map((l) => (
              <option key={l.value} value={l.value}>
                {l.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label>
        Notes for the coach <span className="muted">(optional)</span>
        <textarea
          rows={2}
          maxLength={1000}
          placeholder="e.g. Keeps rolling over on outside pitches"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </label>
      <div className="form-footer">
        <span className="muted small">Height lets us report stride in inches and hand speed in mph.</span>
        <button className="primary" type="submit">
          {submitLabel}
        </button>
      </div>
    </form>
  );
}
