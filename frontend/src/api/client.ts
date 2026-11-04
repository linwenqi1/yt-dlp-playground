import type { Health, InfoResponse, Job, JobError, JobList } from "./types";

const configuredBase = import.meta.env.VITE_API_BASE_URL?.trim();
export const API_BASE = (configuredBase && configuredBase.length > 0 ? configuredBase : "/api/v1").replace(
  /\/+$/,
  "",
);

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown> | null;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

interface RequestOptions extends RequestInit {
  timeoutMs?: number;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = 30_000, signal, headers, ...rest } = options;
  const controller = new AbortController();
  const forwardAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) {
      controller.abort();
    } else {
      signal.addEventListener("abort", forwardAbort, { once: true });
    }
  }
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...rest,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(rest.body ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
    });

    if (!response.ok) {
      let code = `http_${response.status}`;
      let message = response.statusText || "请求失败";
      let details: Record<string, unknown> | null = null;
      try {
        const payload = (await response.json()) as { error?: JobError };
        if (payload.error) {
          code = payload.error.code;
          message = payload.error.message;
          details = payload.error.details;
        }
      } catch {
        // Non-JSON error body (proxy or Access page); keep the generic code.
      }
      throw new ApiError(response.status, code, message, details);
    }

    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if ((error as Error).name === "AbortError") {
      throw signal?.aborted
        ? new ApiError(0, "aborted", "请求已取消")
        : new ApiError(0, "timeout", "请求超时");
    }
    throw new ApiError(0, "network_error", "无法连接服务器");
  } finally {
    window.clearTimeout(timer);
    signal?.removeEventListener("abort", forwardAbort);
  }
}

export function getHealth(): Promise<Health> {
  return request<Health>("/health", { timeoutMs: 5_000 });
}

export function getInfo(url: string): Promise<InfoResponse> {
  return request<InfoResponse>("/info", {
    method: "POST",
    body: JSON.stringify({ url }),
    timeoutMs: 60_000,
  });
}

export function createJob(url: string, quality: string): Promise<Job> {
  return request<Job>("/jobs", {
    method: "POST",
    body: JSON.stringify({ url, quality }),
  });
}

export function getJob(id: string, signal?: AbortSignal): Promise<Job> {
  return request<Job>(`/jobs/${id}`, { signal, timeoutMs: 10_000 });
}

export function listJobs(limit = 20, signal?: AbortSignal): Promise<JobList> {
  return request<JobList>(`/jobs?limit=${limit}`, { signal, timeoutMs: 10_000 });
}

export function cancelJob(id: string): Promise<Job> {
  return request<Job>(`/jobs/${id}/cancel`, { method: "POST" });
}

export function deleteJob(id: string): Promise<void> {
  return request<void>(`/jobs/${id}`, { method: "DELETE" });
}

export function fileUrl(id: string): string {
  return `${API_BASE}/jobs/${id}/file`;
}
