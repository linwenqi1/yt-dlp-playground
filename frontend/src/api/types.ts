export type Platform = "youtube" | "bilibili";

export type JobStatus = "queued" | "running" | "completed" | "failed" | "canceled";

export type JobPhase = "downloading" | "postprocessing";

export type ProgressStage = "video" | "audio";

export interface Health {
  status: string;
  version: string;
  yt_dlp_version: string;
  ffmpeg_available: boolean;
  js_runtime: string | null;
  queue_depth: number;
  active_jobs: number;
  disk_free_bytes: number;
}

export interface Quality {
  id: string;
  kind: "video" | "audio";
  height: number | null;
}

export interface InfoResponse {
  url: string;
  platform: Platform;
  video_id: string;
  title: string;
  uploader: string | null;
  duration_seconds: number | null;
  thumbnail_url: string | null;
  webpage_url: string;
  qualities: Quality[];
}

export interface JobProgress {
  percent: number | null;
  downloaded_bytes: number | null;
  total_bytes: number | null;
  speed_bps: number | null;
  eta_seconds: number | null;
  stage: ProgressStage | null;
}

export interface JobFile {
  name: string;
  size_bytes: number;
  content_type: string;
}

export interface JobError {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
}

export interface Job {
  id: string;
  status: JobStatus;
  phase: JobPhase | null;
  url: string;
  platform: Platform;
  title: string | null;
  quality: string;
  progress: JobProgress;
  file: JobFile | null;
  error: JobError | null;
  cancel_requested: boolean;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  expires_at: string;
}

export interface JobList {
  items: Job[];
}
