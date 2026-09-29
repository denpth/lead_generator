import { test } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { createServer } from "../server.js";

async function listen(t, server) {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(
    () =>
      new Promise((resolve) => {
        server.closeAllConnections();
        server.close(resolve);
      }),
  );
  return `http://127.0.0.1:${server.address().port}`;
}

test("serves the frontend, but never arbitrary project files", async (t) => {
  const base = await listen(t, createServer());
  const page = await fetch(base);
  assert.equal(page.status, 200);
  assert.match(await page.text(), /Lead inbox/);
  assert.match(
    page.headers.get("content-security-policy"),
    /script-src 'self'/,
  );
  for (const path of [
    "/.env",
    "/server.js",
    "/package.json",
    "/api/not-an-endpoint",
  ]) {
    assert.equal((await fetch(base + path)).status, 404);
  }
});

test("forwards query parameters and JSON writes, preserving API responses", async (t) => {
  const seen = [];
  const upstream = await listen(
    t,
    http.createServer(async (req, res) => {
      let body = "";
      for await (const chunk of req) body += chunk;
      seen.push({ method: req.method, path: req.url, body });
      res.writeHead(req.method === "POST" ? 201 : 200, {
        "Content-Type": "application/json",
      });
      res.end(
        JSON.stringify(
          req.method === "POST"
            ? { id: "saved", status: "failed" }
            : { items: [], total: 0 },
        ),
      );
    }),
  );
  const base = await listen(t, createServer(upstream));
  assert.equal(
    (await fetch(base + "/api/leads?q=Acme&status=failed&limit=20")).status,
    200,
  );
  const payload = {
    email: "test@example.com",
    notes: "<script>alert(1)</script>",
  };
  const result = await fetch(base + "/api/leads", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  assert.equal(result.status, 201);
  assert.deepEqual(await result.json(), { id: "saved", status: "failed" });
  assert.equal(seen[0].path, "/leads?q=Acme&status=failed&limit=20");
  assert.deepEqual(JSON.parse(seen[1].body), payload);
});

test("preserves validation errors and rejects cross-origin or oversized writes", async (t) => {
  let calls = 0;
  const upstream = await listen(
    t,
    http.createServer((req, res) => {
      calls++;
      res.writeHead(422, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          detail: [{ loc: ["body", "email"], msg: "Invalid email" }],
        }),
      );
    }),
  );
  const base = await listen(t, createServer(upstream));
  const invalid = await fetch(base + "/api/leads", {
    method: "POST",
    body: "{}",
  });
  assert.equal(invalid.status, 422);
  assert.equal((await invalid.json()).detail[0].msg, "Invalid email");
  assert.equal(
    (
      await fetch(base + "/api/leads", {
        method: "POST",
        headers: { Origin: "https://example.com" },
        body: "{}",
      })
    ).status,
    403,
  );
  assert.equal(
    (
      await fetch(base + "/api/leads", {
        method: "POST",
        body: "x".repeat(33000),
      })
    ).status,
    413,
  );
  assert.equal(calls, 1);
});

test("accepts same-page writes through a remote development relay", async (t) => {
  let calls = 0;
  const upstream = await listen(
    t,
    http.createServer((req, res) => {
      calls++;
      res.writeHead(201, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ id: "saved" }));
    }),
  );
  const base = await listen(t, createServer(upstream));

  const fetchMetadata = await fetch(base + "/api/leads", {
    method: "POST",
    headers: {
      Origin: "https://remote-preview.example",
      "Sec-Fetch-Site": "same-origin",
    },
    body: "{}",
  });
  assert.equal(fetchMetadata.status, 201);

  const forwardedHost = await fetch(base + "/api/leads", {
    method: "POST",
    headers: {
      Origin: "https://remote-preview.example",
      "X-Forwarded-Host": "remote-preview.example",
    },
    body: "{}",
  });
  assert.equal(forwardedHost.status, 201);
  assert.equal(calls, 2);
});

test("reports an unavailable upstream without automatically repeating writes", async (t) => {
  const offline = http.createServer();
  await new Promise((resolve) => offline.listen(0, "127.0.0.1", resolve));
  const address = `http://127.0.0.1:${offline.address().port}`;
  await new Promise((resolve) => offline.close(resolve));
  const base = await listen(t, createServer(address));
  const result = await fetch(base + "/api/leads", {
    method: "POST",
    body: "{}",
  });
  assert.equal(result.status, 502);
  assert.match((await result.json()).detail, /may already be saved/);
});
