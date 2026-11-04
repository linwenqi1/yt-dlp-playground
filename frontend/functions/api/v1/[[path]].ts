interface Env {
  API_ORIGIN?: string;
  API_TOKEN?: string;
}

// Only forward what the API actually needs. Never forward browser cookies,
// authorization headers, cf-* metadata or the original host.
const REQUEST_HEADER_ALLOWLIST = [
  "accept",
  "accept-language",
  "content-type",
  "range",
  "if-range",
  "user-agent",
];

const RESPONSE_HEADER_ALLOWLIST = [
  "content-type",
  "content-range",
  "accept-ranges",
  "content-disposition",
  "cache-control",
  "etag",
  "last-modified",
];

function jsonError(status: number, code: string, message: string): Response {
  return new Response(JSON.stringify({ error: { code, message, details: null } }), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const origin = context.env.API_ORIGIN?.trim().replace(/\/+$/, "");
  if (!origin || !/^https?:\/\/[^/]+$/i.test(origin)) {
    return jsonError(500, "internal_error", "API_ORIGIN 未正确配置（只填协议 + 域名）");
  }

  const incoming = new URL(context.request.url);
  let target: URL;
  try {
    target = new URL(`${incoming.pathname}${incoming.search}`, origin);
  } catch {
    return jsonError(500, "internal_error", "API_ORIGIN 无法解析");
  }

  const headers = new Headers();
  for (const name of REQUEST_HEADER_ALLOWLIST) {
    const value = context.request.headers.get(name);
    if (value) {
      headers.set(name, value);
    }
  }
  if (context.env.API_TOKEN) {
    headers.set("X-API-Token", context.env.API_TOKEN);
  }

  const method = context.request.method;
  const bodyAllowed = method !== "GET" && method !== "HEAD";

  let upstream: Response;
  try {
    upstream = await fetch(target.toString(), {
      method,
      headers,
      body: bodyAllowed ? context.request.body : undefined,
      redirect: "manual",
    });
  } catch {
    return jsonError(502, "upstream_unavailable", "后端服务不可用");
  }

  const responseHeaders = new Headers();
  for (const name of RESPONSE_HEADER_ALLOWLIST) {
    const value = upstream.headers.get(name);
    if (value) {
      responseHeaders.set(name, value);
    }
  }
  responseHeaders.set("X-Content-Type-Options", "nosniff");

  // Stream through: never buffer with arrayBuffer()/text(), or large files
  // would exhaust Function memory.
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
};
