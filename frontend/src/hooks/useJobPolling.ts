import { useEffect, useRef, useState } from "react";

import { ApiError, getJob } from "../api/client";
import type { Job, JobStatus } from "../api/types";

const TERMINAL: JobStatus[] = ["completed", "failed", "canceled"];
const BASE_DELAY_MS = 750;
const MAX_DELAY_MS = 5_000;

function isTerminal(status: JobStatus): boolean {
  return TERMINAL.includes(status);
}

export function useJobPolling(
  jobId: string | null,
  onTerminal: (job: Job) => void,
): { job: Job | null; stale: boolean } {
  const [job, setJob] = useState<Job | null>(null);
  const [stale, setStale] = useState(false);
  const onTerminalRef = useRef(onTerminal);

  useEffect(() => {
    onTerminalRef.current = onTerminal;
  }, [onTerminal]);

  useEffect(() => {
    setJob(null);
    setStale(false);
    if (!jobId) {
      return;
    }

    let cancelled = false;
    let timer = 0;
    let controller: AbortController | null = null;
    let delay = BASE_DELAY_MS;

    const tick = async () => {
      controller = new AbortController();
      try {
        const next = await getJob(jobId, controller.signal);
        if (cancelled) {
          return;
        }
        setJob(next);
        setStale(false);
        delay = BASE_DELAY_MS;
        if (isTerminal(next.status)) {
          onTerminalRef.current(next);
          return;
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        if (error instanceof ApiError && error.status === 404) {
          setJob(null);
          return;
        }
        setStale(true);
        delay = Math.min(delay * 2, MAX_DELAY_MS);
      }
      timer = window.setTimeout(tick, delay);
    };

    void tick();

    return () => {
      cancelled = true;
      controller?.abort();
      window.clearTimeout(timer);
    };
  }, [jobId]);

  return { job, stale };
}
