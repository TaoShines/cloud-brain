const CAPTURE_WEB_MANIFEST = {
  name: "Cloud Brain Capture",
  short_name: "Capture",
  start_url: "/capture",
  display: "standalone",
  background_color: "#f3efe5",
  theme_color: "#1f5c4a",
  icons: [
    {
      src: "/capture-icon.svg",
      sizes: "any",
      type: "image/svg+xml",
      purpose: "any",
    },
  ],
};

const CAPTURE_ICON_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <rect width="256" height="256" rx="56" fill="#1f5c4a"/>
  <path fill="#f7f1e4" d="M128 44c-24.3 0-44 19.7-44 44v32c0 24.3 19.7 44 44 44s44-19.7 44-44V88c0-24.3-19.7-44-44-44zm-60 76a12 12 0 1 1 24 0c0 19.9 16.1 36 36 36s36-16.1 36-36a12 12 0 1 1 24 0c0 28.8-20.5 52.8-48 58.4V200h28a12 12 0 1 1 0 24H108a12 12 0 1 1 0-24h28v-21.6C88.5 172.8 68 148.8 68 120z"/>
</svg>`;

const CAPTURE_PAGE_HTML = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Cloud Brain Capture</title>
  <meta name="theme-color" content="#1f5c4a">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <link rel="manifest" href="/capture.webmanifest">
  <style>
    :root {
      color-scheme: light;
      --bg: #f3efe5;
      --panel: rgba(255, 252, 246, 0.9);
      --text: #17312a;
      --muted: #5e6b67;
      --accent: #1f5c4a;
      --accent-strong: #15463a;
      --border: rgba(31, 92, 74, 0.14);
      --ok: #2f7f57;
      --error: #b5473e;
      --shadow: 0 20px 48px rgba(30, 52, 44, 0.12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Avenir Next", "Noto Sans SC", "PingFang SC", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(241, 204, 138, 0.42), transparent 30%),
        radial-gradient(circle at bottom right, rgba(119, 173, 156, 0.26), transparent 34%),
        var(--bg);
      color: var(--text);
    }
    main {
      width: min(100%, 720px);
      margin: 0 auto;
      padding: 24px 18px 40px;
    }
    .card {
      background: var(--panel);
      backdrop-filter: blur(10px);
      border: 1px solid var(--border);
      border-radius: 28px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    .hero {
      padding: 28px 22px 18px;
      background: linear-gradient(135deg, rgba(31, 92, 74, 0.92), rgba(45, 119, 92, 0.86));
      color: #f9f5eb;
    }
    .eyebrow {
      margin: 0 0 10px;
      font-size: 12px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      opacity: 0.72;
    }
    h1 {
      margin: 0;
      font-size: 34px;
      line-height: 1.02;
    }
    .subtitle {
      margin: 14px 0 0;
      font-size: 16px;
      line-height: 1.5;
      opacity: 0.92;
    }
    .content { padding: 20px 18px 22px; }
    .tips {
      margin: 0 0 16px;
      padding: 14px 16px;
      border-radius: 18px;
      background: rgba(31, 92, 74, 0.07);
      color: var(--muted);
      line-height: 1.55;
      font-size: 14px;
    }
    label {
      display: block;
      margin: 0 0 8px;
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--muted);
    }
    textarea, input {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 16px 18px;
      font: inherit;
      color: var(--text);
      background: rgba(255, 255, 255, 0.82);
      outline: none;
    }
    textarea {
      min-height: 220px;
      resize: vertical;
      line-height: 1.55;
      font-size: 18px;
    }
    input {
      margin-top: 14px;
      font-size: 16px;
    }
    textarea:focus, input:focus {
      border-color: rgba(31, 92, 74, 0.5);
      box-shadow: 0 0 0 4px rgba(31, 92, 74, 0.1);
    }
    .actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-top: 16px;
    }
    button {
      border: none;
      border-radius: 999px;
      padding: 15px 18px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }
    .primary {
      background: var(--accent);
      color: #f6f3eb;
    }
    .secondary {
      background: rgba(31, 92, 74, 0.08);
      color: var(--text);
    }
    .status {
      min-height: 24px;
      margin-top: 14px;
      font-size: 14px;
      line-height: 1.5;
    }
    .status.ok { color: var(--ok); }
    .status.error { color: var(--error); }
    .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 16px;
    }
    .chip {
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(31, 92, 74, 0.08);
      color: var(--muted);
      font-size: 13px;
    }
    .recent {
      margin-top: 20px;
      padding-top: 18px;
      border-top: 1px solid rgba(31, 92, 74, 0.12);
    }
    .recent h2 {
      margin: 0 0 10px;
      font-size: 16px;
    }
    .recent-item {
      padding: 12px 14px;
      border-radius: 18px;
      background: rgba(31, 92, 74, 0.06);
      margin-top: 10px;
      font-size: 14px;
      line-height: 1.5;
    }
    .recent-time {
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }
    @media (max-width: 560px) {
      h1 { font-size: 28px; }
      .actions { grid-template-columns: 1fr; }
      textarea { min-height: 180px; }
    }
  </style>
</head>
<body>
  <main>
    <section class="card">
      <div class="hero">
        <p class="eyebrow">Cloud Brain</p>
        <h1>随手捕捉你的想法</h1>
        <p class="subtitle">这个版本适合公网长期使用。打开网页，说话转文字，点一次保存，就进入云端 capture 数据库。</p>
      </div>
      <div class="content">
        <p class="tips">建议用法：先点进下面的大输入框，切到 Typeless AI 键盘说话，文字出来后点一次“保存到 Cloud Brain”。如果你想让它更像 App，可以把这个页面添加到安卓桌面。</p>
        <label for="capture-body">想法内容</label>
        <textarea id="capture-body" placeholder="想到什么，就直接说出来或打出来。"></textarea>
        <label for="capture-title" style="margin-top: 16px;">标题（可选）</label>
        <input id="capture-title" type="text" placeholder="不填也可以，系统会自动生成标题">
        <div class="actions">
          <button id="save-button" class="primary" type="button">保存到 Cloud Brain</button>
          <button id="clear-button" class="secondary" type="button">清空输入</button>
        </div>
        <p id="status" class="status" aria-live="polite"></p>
        <div class="meta">
          <span class="chip" id="device-chip">设备: 检测中</span>
          <span class="chip">输入来源: Typeless AI</span>
          <span class="chip">存储: Cloudflare D1</span>
        </div>
        <section class="recent">
          <h2>最近保存</h2>
          <div id="recent-list"></div>
        </section>
      </div>
    </section>
  </main>
  <script>
    const bodyField = document.getElementById("capture-body");
    const titleField = document.getElementById("capture-title");
    const saveButton = document.getElementById("save-button");
    const clearButton = document.getElementById("clear-button");
    const statusNode = document.getElementById("status");
    const deviceChip = document.getElementById("device-chip");
    const recentList = document.getElementById("recent-list");
    const token = new URLSearchParams(window.location.search).get("token") || "";
    const userAgent = navigator.userAgent || "";
    const detectedDevice = /Android/i.test(userAgent) ? "android" : "mobile_web";
    deviceChip.textContent = "设备: " + detectedDevice;

    function setStatus(message, tone) {
      statusNode.textContent = message;
      statusNode.className = "status" + (tone ? " " + tone : "");
    }

    function renderRecent(items) {
      recentList.innerHTML = "";
      if (!items.length) {
        recentList.innerHTML = '<div class="recent-item">还没有保存记录。</div>';
        return;
      }
      for (const item of items) {
        const node = document.createElement("div");
        node.className = "recent-item";
        const time = document.createElement("div");
        time.className = "recent-time";
        time.textContent = item.created_at || "";
        const body = document.createElement("div");
        body.textContent = item.body || item.title || "";
        node.appendChild(time);
        node.appendChild(body);
        recentList.appendChild(node);
      }
    }

    async function loadRecent() {
      if (!token) {
        renderRecent([]);
        setStatus("链接里缺少 token，当前页面不能保存。", "error");
        return;
      }
      const response = await fetch("/captures?limit=5", {
        headers: {
          "X-Cloud-Brain-Token": token
        }
      });
      if (!response.ok) {
        throw new Error("最近记录加载失败");
      }
      const payload = await response.json();
      renderRecent(payload.items || []);
    }

    async function saveCapture() {
      const body = bodyField.value.trim();
      const title = titleField.value.trim();
      if (!body) {
        setStatus("先把内容说出来或贴进输入框，再保存。", "error");
        bodyField.focus();
        return;
      }
      if (!token) {
        setStatus("当前链接没有 token，不能保存。", "error");
        return;
      }

      saveButton.disabled = true;
      saveButton.textContent = "保存中...";
      setStatus("正在把这条想法写进 Cloud Brain...", "");

      try {
        const response = await fetch("/captures", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Cloud-Brain-Token": token
          },
          body: JSON.stringify({
            body,
            title: title || null,
            device: detectedDevice,
            input_type: "voice",
            source_label: "typeless_ai",
            tags: ["voice", "quick_capture", detectedDevice]
          })
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error || "保存失败");
        }

        const savedAt = payload.item && payload.item.created_at ? payload.item.created_at : "";
        setStatus("已保存。你的想法已经进入云端 capture 数据库。" + (savedAt ? " 时间: " + savedAt : ""), "ok");
        bodyField.value = "";
        titleField.value = "";
        bodyField.focus();
        await loadRecent();
      } catch (error) {
        const message = error && error.message ? error.message : "未知错误";
        setStatus("保存失败：" + message, "error");
      } finally {
        saveButton.disabled = false;
        saveButton.textContent = "保存到 Cloud Brain";
      }
    }

    saveButton.addEventListener("click", saveCapture);
    clearButton.addEventListener("click", () => {
      bodyField.value = "";
      titleField.value = "";
      setStatus("", "");
      bodyField.focus();
    });

    loadRecent().catch((error) => {
      setStatus(error.message || "页面初始化失败", "error");
    });
    bodyField.focus();
  </script>
</body>
</html>`;

function jsonResponse(payload, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      ...extraHeaders,
    },
  });
}

function textResponse(text, contentType = "text/plain; charset=utf-8", status = 200) {
  return new Response(text, {
    status,
    headers: {
      "content-type": contentType,
      "cache-control": "no-store",
    },
  });
}

function unauthorizedResponse() {
  return jsonResponse(
    {
      error: "Unauthorized",
      message: "Missing or invalid token",
    },
    401
  );
}

function resolveToken(requestUrl, request) {
  return (
    requestUrl.searchParams.get("token") ||
    bearerToken(request.headers.get("authorization")) ||
    optionalHeader(request.headers.get("x-cloud-brain-token"))
  );
}

function optionalHeader(value) {
  if (!value) {
    return null;
  }
  const text = value.trim();
  return text || null;
}

function bearerToken(value) {
  const text = optionalHeader(value);
  if (!text) {
    return null;
  }
  const prefix = "bearer ";
  if (text.toLowerCase().startsWith(prefix)) {
    const token = text.slice(prefix.length).trim();
    return token || null;
  }
  return null;
}

function requireAuth(env, requestUrl, request) {
  if (!env.CAPTURE_TOKEN) {
    return true;
  }
  return resolveToken(requestUrl, request) === env.CAPTURE_TOKEN;
}

function normalizeTags(tags, device) {
  const values = Array.isArray(tags) ? tags : [];
  const normalized = [];
  const seen = new Set();
  for (const tag of values) {
    const cleaned = String(tag || "").trim().toLowerCase();
    if (!cleaned || seen.has(cleaned)) {
      continue;
    }
    normalized.push(cleaned);
    seen.add(cleaned);
  }
  for (const fallback of ["capture", "mobile", device || "unknown"]) {
    if (!seen.has(fallback)) {
      normalized.push(fallback);
      seen.add(fallback);
    }
  }
  return normalized;
}

function buildTitle(title, body) {
  const cleanedTitle = String(title || "").trim();
  if (cleanedTitle) {
    return cleanedTitle.slice(0, 120);
  }
  const firstLine = body.split(/\r?\n/).find((line) => line.trim()) || body;
  if (firstLine.length <= 80) {
    return firstLine;
  }
  return `${firstLine.slice(0, 77).trimEnd()}...`;
}

async function parseJson(request) {
  try {
    const payload = await request.json();
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw new Error("Request body must be a JSON object");
    }
    return payload;
  } catch (error) {
    throw new Error("Request body must be valid JSON");
  }
}

function mapCaptureRow(row) {
  return {
    item_id: row.item_id,
    title: row.title,
    body: row.body,
    created_at: row.created_at,
    device: row.device,
    input_type: row.input_type,
    source_label: row.source_label,
    tags: row.tags_json ? JSON.parse(row.tags_json) : [],
  };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return jsonResponse({
        status: "ok",
        service: "cloudflare-capture",
      });
    }

    if (url.pathname === "/capture") {
      if (!requireAuth(env, url, request)) {
        return unauthorizedResponse();
      }
      return textResponse(CAPTURE_PAGE_HTML, "text/html; charset=utf-8");
    }

    if (url.pathname === "/capture.webmanifest") {
      if (!requireAuth(env, url, request)) {
        return unauthorizedResponse();
      }
      return jsonResponse(CAPTURE_WEB_MANIFEST, 200, {
        "content-type": "application/manifest+json; charset=utf-8",
      });
    }

    if (url.pathname === "/capture-icon.svg") {
      if (!requireAuth(env, url, request)) {
        return unauthorizedResponse();
      }
      return textResponse(CAPTURE_ICON_SVG, "image/svg+xml; charset=utf-8");
    }

    if (url.pathname === "/captures" && request.method === "GET") {
      if (!requireAuth(env, url, request)) {
        return unauthorizedResponse();
      }
      const limit = Math.max(1, Math.min(Number(url.searchParams.get("limit") || "5"), 20));
      const result = await env.DB.prepare(
        `SELECT item_id, title, body, created_at, device, input_type, source_label, tags_json
         FROM captures
         ORDER BY created_at DESC
         LIMIT ?`
      )
        .bind(limit)
        .all();
      return jsonResponse({
        items: (result.results || []).map(mapCaptureRow),
        count: (result.results || []).length,
      });
    }

    if (url.pathname === "/captures" && request.method === "POST") {
      if (!requireAuth(env, url, request)) {
        return unauthorizedResponse();
      }

      let payload;
      try {
        payload = await parseJson(request);
      } catch (error) {
        return jsonResponse({ error: error.message }, 400);
      }

      const body = String(payload.body || "").trim();
      if (!body) {
        return jsonResponse({ error: "Missing required field: body" }, 400);
      }

      const createdAt = String(payload.created_at || new Date().toISOString()).trim();
      const device = String(payload.device || "mobile_web").trim();
      const inputType = String(payload.input_type || "text").trim();
      const sourceLabel = String(payload.source_label || "typeless_ai").trim();
      const title = buildTitle(payload.title, body);
      const tags = normalizeTags(payload.tags, device);
      const itemId = `capture:${crypto.randomUUID()}`;

      await env.DB.prepare(
        `INSERT INTO captures (
          item_id, title, body, created_at, device, input_type, source_label, tags_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
      )
        .bind(itemId, title, body, createdAt, device, inputType, sourceLabel, JSON.stringify(tags))
        .run();

      return jsonResponse(
        {
          item: {
            item_id: itemId,
            title,
            body,
            created_at: createdAt,
            device,
            input_type: inputType,
            source_label: sourceLabel,
            tags,
          },
        },
        201
      );
    }

    return jsonResponse(
      {
        error: "Not found",
        path: url.pathname,
      },
      404
    );
  },
};
