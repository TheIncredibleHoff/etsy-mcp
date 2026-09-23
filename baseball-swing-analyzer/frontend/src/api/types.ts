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
  error: string | null;
  info: VideoInfo;
}
