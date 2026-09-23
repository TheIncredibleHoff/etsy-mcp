export type VideoStatus = "uploaded" | "processing" | "complete" | "failed";

export interface VideoInfo {
  fps: number;
  frame_count: number;
  width: number;
  height: number;
  duration_s: number;
}

export type HitterLevel = "youth" | "high_school" | "college" | "pro" | "adult";

export interface HitterProfile {
  height_in: number | null;
  level: HitterLevel | null;
  notes: string | null;
}

export interface VideoRecord {
  id: string;
  original_filename: string;
  stored_filename: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
  status: VideoStatus;
  stage: string | null;
  progress: number;
  error: string | null;
  info: VideoInfo;
  hitter: HitterProfile;
}

/** [x, y, z, visibility] — x/y normalized to the frame (0..1 from top-left). */
export type ImageLandmark = [number, number, number, number];
/** [x, y, z] in meters, centered between the hips. */
export type WorldLandmark = [number, number, number];

export interface PoseFrame {
  image: ImageLandmark[];
  world: WorldLandmark[];
}

export interface PoseData {
  fps: number;
  width: number;
  height: number;
  frame_count: number;
  truncated: boolean;
  landmark_names: string[];
  connections: [number, number][];
  frames: (PoseFrame | null)[];
}

export type MetricCategory = "rotation" | "posture" | "bat_path" | "stride" | "timing";

export interface Metric {
  key: string;
  label: string;
  value: number | null;
  unit: string;
  category: MetricCategory;
  description: string;
}

export interface PhaseMark {
  frame: number;
  time_s: number;
}

export type PhaseName = "stance" | "stride_start" | "foot_plant" | "swing_start" | "contact";

export interface SwingMetrics {
  bats: "right" | "left";
  fps: number;
  hitter_height_in: number | null;
  tracking_coverage: number;
  phases: Record<PhaseName, PhaseMark | null>;
  metrics: Metric[];
  series: {
    hip_rotation: number[];
    shoulder_rotation: number[];
    separation: number[];
    hand_speed: number[];
  };
  /** Midpoint of the wrists per frame, normalized [x, y]. */
  hand_path: [number, number][];
  warnings: string[];
}

export interface CoachingFeedback {
  summary: string;
  strengths: { title: string; detail: string; metric_keys: string[] }[];
  issues: {
    title: string;
    priority: "high" | "medium" | "low";
    explanation: string;
    metric_keys: string[];
    drill: { name: string; how_to: string; why: string };
  }[];
  next_session_focus: string;
  caveats: string[];
}

export type FeedbackResult =
  | { status: "ok"; model: string; feedback: CoachingFeedback }
  | { status: "skipped" | "error"; error: string };

export interface Analysis {
  metrics: SwingMetrics;
  feedback: FeedbackResult | null;
}
