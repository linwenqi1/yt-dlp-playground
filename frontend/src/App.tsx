import { useCallback, useEffect, useState } from "react";

import { cancelJob, createJob, deleteJob, getHealth, getInfo, listJobs } from "./api/client";
import type { Health, InfoResponse, Job } from "./api/types";
import { InfoCard } from "./components/InfoCard";
import { JobPanel } from "./components/JobPanel";
import { RecentJobs } from "./components/RecentJobs";
import { UrlForm } from "./components/UrlForm";
import { useJobPolling } from "./hooks/useJobPolling";
import { describeError, extractUrl } from "./lib/format";

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState(false);

  const [url, setUrl] = useState("");
  const [info, setInfo] = useState<InfoResponse | null>(null);
  const [quality, setQuality] = useState("best");
  const [parsing, setParsing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [jobId, setJobId] = useState<string | null>(null);
  const [recent, setRecent] = useState<Job[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const refreshRecent = useCallback(async () => {
    setRefreshing(true);
    try {
      const result = await listJobs(20);
      setRecent(result.items);
    } catch {
      // Keep the last known list; the job panel already surfaces connection problems.
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    getHealth()
      .then((result) => {
        setHealth(result);
        setHealthError(false);
      })
      .catch(() => setHealthError(true));
    void refreshRecent();
  }, [refreshRecent]);

  const handleTerminal = useCallback(
    (finished: Job) => {
      setRecent((previous) => [finished, ...previous.filter((item) => item.id !== finished.id)].slice(0, 20));
      void refreshRecent();
    },
    [refreshRecent],
  );

  const { job, stale } = useJobPolling(jobId, handleTerminal);

  const handleParse = useCallback(async () => {
    const candidate = extractUrl(url);
    if (!candidate) {
      setMessage("没有找到有效链接，请粘贴完整的 http(s) 视频地址");
      return;
    }
    setParsing(true);
    setMessage(null);
    setActionError(null);
    try {
      const result = await getInfo(candidate);
      setUrl(result.url);
      setInfo(result);
      setQuality(result.qualities[0]?.id ?? "best");
    } catch (error) {
      setInfo(null);
      setMessage(describeError(error));
    } finally {
      setParsing(false);
    }
  }, [url]);

  const handleStart = useCallback(async () => {
    if (!info) {
      return;
    }
    setCreating(true);
    setActionError(null);
    try {
      const created = await createJob(info.url, quality);
      setJobId(created.id);
      setRecent((previous) => [created, ...previous.filter((item) => item.id !== created.id)].slice(0, 20));
      void refreshRecent();
    } catch (error) {
      setActionError(describeError(error));
    } finally {
      setCreating(false);
    }
  }, [info, quality, refreshRecent]);

  const handleCancel = useCallback(async () => {
    if (!jobId) {
      return;
    }
    try {
      await cancelJob(jobId);
    } catch (error) {
      setActionError(describeError(error));
    }
  }, [jobId]);

  const handleDelete = useCallback(
    async (target: Job) => {
      if (!window.confirm(`删除任务「${target.title || "未命名视频"}」？文件也会一并删除。`)) {
        return;
      }
      try {
        await deleteJob(target.id);
        setRecent((previous) => previous.filter((item) => item.id !== target.id));
        if (jobId === target.id) {
          setJobId(null);
        }
      } catch (error) {
        setActionError(describeError(error));
      }
    },
    [jobId],
  );

  const handleSelect = useCallback((target: Job) => {
    setActionError(null);
    setJobId(target.id);
  }, []);

  const healthText = healthError
    ? "后端未连接，请确认 API 已启动"
    : health
      ? `后端正常 · yt-dlp ${health.yt_dlp_version} · ${health.js_runtime ?? "无 JS 运行时"}${
          health.ffmpeg_available ? "" : " · 缺少 FFmpeg"
        }`
      : "正在连接后端…";

  return (
    <div className="page">
      <header className="hero">
        <h1>yt-dlp Playground</h1>
        <p className="muted">粘贴链接，查看清晰度，后台下载完成后保存到本地。</p>
        <p className={`health${healthError ? " error" : ""}`}>{healthText}</p>
      </header>

      <main className="stack">
        <section className="card">
          <UrlForm value={url} loading={parsing} onChange={setUrl} onSubmit={handleParse} />
          {message ? (
            <p className="alert" role="alert">
              {message}
            </p>
          ) : null}
        </section>

        {info ? (
          <InfoCard
            info={info}
            quality={quality}
            creating={creating}
            onQualityChange={setQuality}
            onStart={handleStart}
          />
        ) : null}

        {actionError ? (
          <p className="alert" role="alert">
            {actionError}
          </p>
        ) : null}

        {job ? (
          <JobPanel job={job} stale={stale} onCancel={handleCancel} onDelete={() => void handleDelete(job)} />
        ) : null}

        <RecentJobs
          jobs={recent}
          refreshing={refreshing}
          activeJobId={jobId}
          onSelect={handleSelect}
          onRefresh={() => void refreshRecent()}
          onDelete={(target) => void handleDelete(target)}
        />

        <p className="muted small footer">
          仅支持 YouTube / Bilibili 单视频，不处理播放列表、直播与 b23.tv 短链。请遵守平台条款与版权要求。
        </p>
      </main>
    </div>
  );
}
