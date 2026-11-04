import withCloudflareAccess from "@cloudflare/pages-plugin-cloudflare-access";

interface Env {
  ENVIRONMENT?: string;
  ACCESS_DOMAIN?: string;
  ACCESS_AUD?: string;
}

function jsonError(status: number, code: string, message: string): Response {
  return new Response(JSON.stringify({ error: { code, message, details: null } }), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

/**
 * Fail closed for every /api/* request.
 *
 * Access protects the Pages custom domain, but the production *.pages.dev alias
 * cannot be protected. Without validating the Access JWT here, anyone could use
 * that alias to make the proxy inject the backend API token.
 */
export const onRequest: PagesFunction<Env> = async (context) => {
  if (context.env.ENVIRONMENT === "development") {
    return context.next();
  }

  const domain = context.env.ACCESS_DOMAIN;
  const aud = context.env.ACCESS_AUD;
  if (!domain || !aud) {
    return jsonError(500, "internal_error", "Cloudflare Access 未配置");
  }

  if (!context.request.headers.get("Cf-Access-Jwt-Assertion")) {
    return jsonError(401, "unauthorized", "未登录或 Access 会话已过期");
  }

  const handler = withCloudflareAccess({
    domain: domain as `https://${string}.cloudflareaccess.com`,
    aud,
  });
  const response = await handler(context);

  // The plugin redirects to the Access login page on validation failure; API
  // clients need a JSON answer instead of an HTML redirect.
  if (response.status === 302) {
    return jsonError(401, "unauthorized", "Access JWT 校验失败");
  }
  return response;
};
