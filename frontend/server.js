import http from "node:http";
import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const assets = new Map([
  ["/", ["index.html", "text/html; charset=utf-8"]],
  ["/app.js", ["app.js", "text/javascript; charset=utf-8"]],
  ["/api-client.js", ["api-client.js", "text/javascript; charset=utf-8"]],
  ["/styles.css", ["styles.css", "text/css; charset=utf-8"]],
  ["/favicon.svg", ["favicon.svg", "image/svg+xml"]],
]);
const uuid = "[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}";

export function createServer(
  apiOrigin = process.env.API_ORIGIN || "http://127.0.0.1:8000",
) {
  const upstream = new URL(apiOrigin);
  return http.createServer(async (req, res) => {
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("Referrer-Policy", "same-origin");
    res.setHeader(
      "Content-Security-Policy",
      "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
    );
    res.setHeader("Cache-Control", "no-store");
    const json = (status, data) => {
      res.writeHead(status, { "Content-Type": "application/json" });
      res.end(JSON.stringify(data));
    };
    try {
      const url = new URL(req.url, "http://localhost");
      if (url.pathname === "/healthz" && req.method === "GET")
        return json(200, { status: "ok" });
      if (url.pathname.startsWith("/api/")) {
        const path = url.pathname.slice(4);
        const allowed =
          (req.method === "GET" &&
            (path === "/healthz" ||
              path === "/leads" ||
              new RegExp(`^/leads/${uuid}$`, "i").test(path))) ||
          (req.method === "POST" &&
            (path === "/leads" ||
              new RegExp(`^/leads/${uuid}/retry$`, "i").test(path) ||
              new RegExp(`^/leads/${uuid}/review/(accepted|discarded)$`, "i").test(path)));
        if (!allowed) return json(404, { detail: "Endpoint not found." });
        // A remote development relay can preserve the browser's public Origin
        // while forwarding an internal Host. Fetch Metadata still identifies
        // a same-page request without weakening the cross-site write check.
        const fetchSite = req.headers["sec-fetch-site"];
        const forwardedHost = req.headers["x-forwarded-host"]
          ?.split(",")[0]
          .trim();
        const requestHost = forwardedHost || req.headers.host;
        if (
          req.method === "POST" &&
          req.headers.origin &&
          fetchSite !== "same-origin" &&
          new URL(req.headers.origin).host !== requestHost
        ) {
          return json(403, {
            detail: "Cross-origin requests are not allowed.",
          });
        }
        let size = 0;
        const chunks = [];
        for await (const chunk of req) {
          size += chunk.length;
          if (size > 32768)
            return json(413, { detail: "Lead details are too large." });
          chunks.push(chunk);
        }
        const response = await fetch(new URL(path + url.search, upstream), {
          method: req.method,
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: req.method === "POST" ? Buffer.concat(chunks) : undefined,
          signal: AbortSignal.timeout(90000),
          redirect: "error",
        });
        res.writeHead(response.status, { "Content-Type": "application/json" });
        return res.end(await response.text());
      }
      const asset = assets.get(url.pathname);
      if (!asset || !["GET", "HEAD"].includes(req.method))
        return json(404, { detail: "Page not found." });
      const content = await readFile(
        new URL(`./public/${asset[0]}`, import.meta.url),
      );
      res.writeHead(200, { "Content-Type": asset[1] });
      res.end(req.method === "HEAD" ? undefined : content);
    } catch (error) {
      console.error("Request failed:", error.message);
      if (!res.headersSent)
        json(502, {
          detail:
            req.method === "POST"
              ? "The request could not be confirmed. Refresh the inbox before submitting again; the lead may already be saved."
              : "The lead service is unavailable. Please try again shortly.",
        });
      else res.end();
    }
  });
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(resolve(process.argv[1])).href
) {
  const port = Number(process.env.PORT || 3000);
  createServer().listen(port, "0.0.0.0", () =>
    console.log(`Lead inbox ready on http://localhost:${port}`),
  );
}
