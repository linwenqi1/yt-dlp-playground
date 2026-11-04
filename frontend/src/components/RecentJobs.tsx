import { fileUrl } from "../api/client";
import type { Job } from "../api/types";
import { formatBytes, qualityLabel, statusLabel } from "../lib/format";

interface RecentJobsProps {
  jobs: Job[];
  refreshing: boolean;
  activeJobId: string | null;
  onSelect: (job: Job) => void;
  onRefresh: () => void;
  onDelete: (job: Job) => void;
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

export function RecentJobs({
  jobs,
  refreshing,
  activeJobId,
  onSelect,
  onRefresh,
  onDelete,
}: RecentJobsProps) {
  return (
    <section className="card recent">
      <header className="panel-header">
        <h2>最近任务</h2>
        <button className="ghost" type="button" onClick={onRefresh} disabled={refreshing}>
          {refreshing ? "刷新中…" : "刷新"}
        </button>
      </header>

      {jobs.length === 0 ? (
        <p className="muted">还没有任务。粘贴链接开始第一次下载。</p>
      ) : (
        <ul className="job-list">
          {jobs.map((job) => {
            const terminal = job.status === "completed" || job.status === "failed" || job.status === "canceled";
            return (
              <li key={job.id} className={job.id === activeJobId ? "active" : undefined}>
                <button className="job-row" type="button" onClick={() => onSelect(job)}>
                  <span className="job-row-main">
                    <span className="job-row-title">{job.title || "未命名视频"}</span>
                    <span className="muted small">
                      {qualityLabel(job.quality)} · {formatTimestamp(job.created_at)}
                      {job.file ? ` · ${formatBytes(job.file.size_bytes)}` : ""}
                    </span>
                  </span>
                  <span className={`status-badge ${job.status}`}>{statusLabel(job.status)}</span>
                </button>
                <div className="job-row-actions">
                  {job.status === "completed" ? (
                    <a className="link" href={fileUrl(job.id)} download={job.file?.name}>
                      下载
                    </a>
                  ) : null}
                  {terminal ? (
                    <button className="link danger" type="button" onClick={() => onDelete(job)}>
                      删除
                    </button>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
