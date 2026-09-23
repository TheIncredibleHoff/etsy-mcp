export type VideoStatus = "uploaded" | "processing" | "complete" | "failed";

export interface VideoInfo {
  fps: number;
  frame_count: number;
  width: number;
  height: number;
  duration_s: number;
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
