import type { Job } from "../api/types";
import { fileUrl } from "../api/client";
import {
  errorMessage,
  formatBytes,
  formatEta,
  formatSpeed,
  platformLabel,
  qualityLabel,
  stageLabel,
  statusLabel,
} from "../lib/format";

interface JobPanelProps {
  job: Job;
  stale: boolean;
  onCancel: () => void;
  onDelete: () => void;
}

export function JobPanel({ job, stale, onCancel, onDelete }: JobPanelProps) {
  const percent = job.progress.percent;
  const indeterminate = job.status === "running" && percent === null;
  const width = job.status === "completed" ? 100 : (percent ?? 0);
  const active = job.status === "queued" || job.status === "running";

  let statusText = statusLabel(job.status);
  if (job.status === "running" && job.phase === "postprocessing") {
    statusText = "正在合并音视频";
  } else if (job.status === "running" && job.progress.stage) {
    statusText = `${statusLabel(job.status)}（${stageLabel(job.progress.stage)}）`;
  }

  return (
    <section className="card job-panel" aria-live="polite">
      <header className="panel-header">
        <div>
          <span className={`status-badge ${job.status}`}>{statusText}</span>
          <h2 className="job-title">{job.title || "下载任务"}</h2>
          <p className="muted small">
            {platformLabel(job.platform)} · {qualityLabel(job.quality)}
            {job.file ? ` · ${job.file.name}` : ""}
          </p>
        </div>
        <div className="panel-actions">
          {active ? (
            <button className="ghost" type="button" onClick={onCancel} disabled={job.cancel_requested}>
              {job.cancel_requested ? "取消中…" : "取消"}
            </button>
          ) : (
            <>
              {job.status === "completed" ? (
                <a className="primary" href={fileUrl(job.id)} download={job.file?.name}>
                  保存文件
                </a>
              ) : null}
              <button className="ghost" type="button" onClick={onDelete}>
                删除
              </button>
            </>
          )}
        </div>
      </header>

      <div className={`progress-track${indeterminate ? " indeterminate" : ""}`}>
        <div className="progress-fill" style={{ width: `${width}%` }} />
      </div>

      <div className="progress-meta">
        <span>{percent === null ? (job.status === "queued" ? "等待中" : "—") : `${percent.toFixed(1)}%`}</span>
        <span>
          {formatBytes(job.progress.downloaded_bytes)} / {formatBytes(job.progress.total_bytes)}
        </span>
        {job.status === "running" ? (
          <span>
            {formatSpeed(job.progress.speed_bps)}
            {job.progress.eta_seconds !== null ? ` · ${formatEta(job.progress.eta_seconds)}` : ""}
          </span>
        ) : null}
        {job.file ? <span>{formatBytes(job.file.size_bytes)}</span> : null}
      </div>

      {job.error ? (
        <p className="alert" role="alert">
          {errorMessage(job.error.code, job.error.message)}
        </p>
      ) : null}
      {stale ? <p className="muted small">状态刷新失败，正在自动重试…</p> : null}
    </section>
  );
}
