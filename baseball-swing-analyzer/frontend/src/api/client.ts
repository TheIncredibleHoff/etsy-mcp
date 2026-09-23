import type { PoseData, VideoRecord } from "./types";

const BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // not JSON
    }
    throw new ApiError(res.status, detail);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const videoFileUrl = (id: string) => `${BASE}/api/videos/${id}/file`;

export const listVideos = () => request<VideoRecord[]>("/api/videos");
export const getVideo = (id: string) => request<VideoRecord>(`/api/videos/${id}`);
export const analyzeVideo = (id: string) =>
  request<VideoRecord>(`/api/videos/${id}/analyze`, { method: "POST" });
export const getPose = (id: string) => request<PoseData>(`/api/videos/${id}/pose`);
export const deleteVideo = (id: string) =>
  request<void>(`/api/videos/${id}`, { method: "DELETE" });

/** Uploads with XHR (fetch has no upload progress events). */
export function uploadVideo(
  file: File,
  onProgress: (fraction: number) => void,
): Promise<VideoRecord> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE}/api/videos`);
    xhr.responseType = "json";
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response as VideoRecord);
      } else {
        const detail = xhr.response?.detail;
        reject(new ApiError(xhr.status, typeof detail === "string" ? detail : "Upload failed"));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "Network error — is the backend running?"));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}
