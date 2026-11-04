interface UrlFormProps {
  value: string;
  loading: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export function UrlForm({ value, loading, onChange, onSubmit }: UrlFormProps) {
  return (
    <form
      className="url-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <label className="sr-only" htmlFor="video-url">
        视频链接
      </label>
      <input
        id="video-url"
        name="url"
        type="text"
        inputMode="url"
        autoComplete="off"
        spellCheck={false}
        placeholder="粘贴 YouTube 或 Bilibili 视频链接"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <button className="primary" type="submit" disabled={loading || value.trim().length === 0}>
        {loading ? "解析中…" : "解析"}
      </button>
    </form>
  );
}
