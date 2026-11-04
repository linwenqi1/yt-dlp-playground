import type { JobStatus, Platform, Quality } from "../api/types";

const UNITS = ["B", "KB", "MB", "GB", "TB"];

export function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  let amount = value;
  let unit = 0;
  while (amount >= 1024 && unit < UNITS.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${amount.toFixed(amount >= 100 || unit === 0 ? 0 : 1)} ${UNITS[unit]}`;
}

export function formatSpeed(bytesPerSecond: number | null | undefined): string {
  if (!bytesPerSecond) {
    return "—";
  }
  return `${formatBytes(bytesPerSecond)}/s`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds < 0) {
    return "—";
  }
  const total = Math.round(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const padded = (value: number) => value.toString().padStart(2, "0");
  return hours > 0 ? `${hours}:${padded(minutes)}:${padded(secs)}` : `${minutes}:${padded(secs)}`;
}

export function formatEta(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) {
    return "—";
  }
  if (seconds < 60) {
    return `约 ${Math.max(1, Math.round(seconds))} 秒`;
  }
  return `约 ${Math.round(seconds / 60)} 分钟`;
}

const STATUS_LABELS: Record<JobStatus, string> = {
  queued: "排队中",
  running: "下载中",
  completed: "已完成",
  failed: "失败",
  canceled: "已取消",
};

export function statusLabel(status: JobStatus): string {
  return STATUS_LABELS[status] ?? status;
}

export function stageLabel(stage: "video" | "audio" | null): string {
  if (stage === "video") return "视频轨";
  if (stage === "audio") return "音频轨";
  return "";
}

export function platformLabel(platform: Platform): string {
  return platform === "youtube" ? "YouTube" : "Bilibili";
}

export function qualityLabel(quality: Quality | string): string {
  if (typeof quality === "string") {
    if (quality === "best") return "最佳画质";
    if (quality === "audio") return "仅音频 (MP3)";
    return quality;
  }
  if (quality.kind === "audio") {
    return "仅音频 (MP3)";
  }
  if (quality.id === "best") {
    return "最佳画质";
  }
  return quality.height ? `${quality.height}p` : quality.id;
}

const ERROR_MESSAGES: Record<string, string> = {
  invalid_request: "请求参数不正确，请检查后重试",
  invalid_url: "链接格式不正确，请粘贴完整的视频地址",
  unsupported_site: "仅支持 YouTube 和 Bilibili 链接；b23.tv 短链请先展开为 bilibili.com 链接",
  invalid_quality: "该清晰度不可用，请选择其他选项",
  unauthorized: "访问被拒绝，请刷新页面后重试",
  forbidden: "访问被拒绝：Cloudflare Access 会话可能已过期，请刷新页面重新登录",
  job_not_found: "任务不存在，可能已被删除或过期",
  job_not_cancellable: "任务已结束，无法取消",
  job_not_deletable: "任务仍在进行，无法删除",
  file_not_ready: "文件还没有准备好，请等待下载完成",
  file_gone: "文件已不存在或已过期，请重新下载",
  video_unavailable: "视频不可用：可能已删除、被隐藏或链接有误",
  video_private: "私密视频无法下载",
  login_required: "平台要求登录验证，请在服务端配置 cookies 后重试",
  age_restricted: "视频有年龄限制，需要登录 cookies 才能下载",
  region_blocked: "视频在当前网络区域不可用",
  live_stream_unsupported: "暂不支持直播",
  playlist_not_supported: "暂不支持播放列表或多 P 视频，请粘贴单个视频链接",
  format_unavailable: "没有匹配的清晰度，请换一个选项",
  internal_error: "服务器内部错误，请稍后重试",
  extraction_failed: "解析视频信息失败，请稍后重试",
  upstream_unavailable: "上游平台暂时不可用，请稍后重试",
  queue_full: "下载队列已满，请等待当前任务结束后重试",
  insufficient_storage: "服务器磁盘空间不足",
  download_failed: "下载失败，请稍后重试",
  merge_failed: "音视频合并失败，请检查服务端的 FFmpeg",
  file_too_large: "文件超过大小限制",
  timeout: "任务超时，请重试",
  interrupted: "服务重启导致任务中断，请重新创建任务",
  network_error: "无法连接服务器，请确认后端已启动",
  http_403: "访问被拒绝，请刷新页面后重试",
  http_404: "接口不存在",
  http_500: "服务器错误",
  http_502: "上游服务不可用",
  http_503: "服务暂时不可用",
};

export function errorMessage(code: string | undefined, fallback?: string): string {
  if (code && ERROR_MESSAGES[code]) {
    return ERROR_MESSAGES[code];
  }
  return fallback || "操作失败，请稍后重试";
}

export function describeError(error: unknown): string {
  if (error && typeof error === "object" && "code" in error) {
    const typed = error as { code: string; message?: string };
    return errorMessage(typed.code, typed.message);
  }
  return "操作失败，请稍后重试";
}

export function extractUrl(text: string): string {
  const match = text.match(/https?:\/\/[^\s<>"']+/i);
  if (!match) {
    return "";
  }
  return match[0].replace(/[)\]}>，。；、！？,;!?]+$/u, "");
}
