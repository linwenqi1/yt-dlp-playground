import { useState } from "react";

import type { InfoResponse } from "../api/types";
import { formatDuration, platformLabel } from "../lib/format";
import { QualityPicker } from "./QualityPicker";

interface InfoCardProps {
  info: InfoResponse;
  quality: string;
  creating: boolean;
  onQualityChange: (quality: string) => void;
  onStart: () => void;
}

export function InfoCard({ info, quality, creating, onQualityChange, onStart }: InfoCardProps) {
  const [thumbnailFailed, setThumbnailFailed] = useState(false);

  return (
    <section className="card info-card">
      <div className="thumbnail">
        {info.thumbnail_url && !thumbnailFailed ? (
          <img
            src={info.thumbnail_url}
            alt=""
            referrerPolicy="no-referrer"
            loading="lazy"
            onError={() => setThumbnailFailed(true)}
          />
        ) : (
          <div className="thumbnail-placeholder" aria-hidden="true">
            {platformLabel(info.platform)}
          </div>
        )}
      </div>

      <div className="info-body">
        <div className="info-heading">
          <span className={`platform-badge ${info.platform}`}>{platformLabel(info.platform)}</span>
          {info.duration_seconds ? (
            <span className="muted small">时长 {formatDuration(info.duration_seconds)}</span>
          ) : null}
        </div>
        <h2 className="info-title">{info.title}</h2>
        {info.uploader ? <p className="muted">{info.uploader}</p> : null}

        <div className="field">
          <span className="field-label">清晰度</span>
          <QualityPicker qualities={info.qualities} value={quality} onChange={onQualityChange} />
          <p className="muted small">清晰度是上限：若视频没有该档位，会自动选择最接近的较低清晰度。</p>
        </div>

        <button className="primary wide" type="button" onClick={onStart} disabled={creating}>
          {creating ? "创建任务中…" : "开始下载"}
        </button>
      </div>
    </section>
  );
}
