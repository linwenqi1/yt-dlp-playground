import type { Quality } from "../api/types";
import { qualityLabel } from "../lib/format";

interface QualityPickerProps {
  qualities: Quality[];
  value: string;
  onChange: (quality: string) => void;
}

export function QualityPicker({ qualities, value, onChange }: QualityPickerProps) {
  return (
    <div className="quality-picker" role="radiogroup" aria-label="清晰度">
      {qualities.map((quality) => (
        <button
          key={quality.id}
          type="button"
          role="radio"
          aria-checked={value === quality.id}
          className={`quality-option${value === quality.id ? " selected" : ""}${
            quality.kind === "audio" ? " audio" : ""
          }`}
          onClick={() => onChange(quality.id)}
        >
          {qualityLabel(quality)}
        </button>
      ))}
    </div>
  );
}
