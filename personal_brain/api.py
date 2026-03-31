from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse

from .config import AppConfig
from .database import Database
from .sync import sync_cloud_capture_to_local
from .time_filters import normalize_created_range

CAPTURE_WEB_MANIFEST = {
    "name": "Cloud Brain Capture",
    "short_name": "Capture",
    "start_url": "/capture",
    "display": "standalone",
    "background_color": "#f3efe5",
    "theme_color": "#1f5c4a",
    "icons": [
        {
            "src": "/capture-icon.svg",
            "sizes": "any",
            "type": "image/svg+xml",
            "purpose": "any",
        }
    ],
}

CAPTURE_PAGE_HTML = """<!doctype html>
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
      --panel: rgba(255, 252, 246, 0.86);
      --text: #17312a;
      --muted: #5e6b67;
      --accent: #1f5c4a;
      --accent-strong: #15463a;
      --border: rgba(31, 92, 74, 0.14);
      --ok: #2f7f57;
      --error: #b5473e;
      --shadow: 0 20px 48px rgba(30, 52, 44, 0.12);
    }

    * {
      box-sizing: border-box;
    }

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

    .content {
      padding: 20px 18px 22px;
    }

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

    textarea,
    input {
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

    textarea:focus,
    input:focus {
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
      transition: transform 120ms ease, opacity 120ms ease, background 120ms ease;
    }

    button:active {
      transform: translateY(1px) scale(0.995);
    }

    .primary {
      background: var(--accent);
      color: #f6f3eb;
    }

    .primary:hover {
      background: var(--accent-strong);
    }

    .secondary {
      background: rgba(31, 92, 74, 0.08);
      color: var(--text);
    }

    .secondary:hover {
      background: rgba(31, 92, 74, 0.14);
    }

    .status {
      min-height: 24px;
      margin-top: 14px;
      font-size: 14px;
      line-height: 1.5;
    }

    .status.ok {
      color: var(--ok);
    }

    .status.error {
      color: var(--error);
    }

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

    @media (max-width: 560px) {
      h1 {
        font-size: 28px;
      }

      .actions {
        grid-template-columns: 1fr;
      }

      textarea {
        min-height: 180px;
      }
    }
  </style>
</head>
<body>
  <main>
    <section class="card">
      <div class="hero">
        <p class="eyebrow">Cloud Brain</p>
        <h1>随手捕捉你的想法</h1>
        <p class="subtitle">在安卓上打开这个页面，用 Typeless AI 语音输入，把想到的内容直接送进你的数据库。</p>
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
          <span class="chip">保存方式: 进入本地数据库</span>
        </div>
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
    const token = new URLSearchParams(window.location.search).get("token") || "";

    const userAgent = navigator.userAgent || "";
    const detectedDevice = /Android/i.test(userAgent) ? "android" : "mobile_web";
    deviceChip.textContent = "设备: " + detectedDevice;

    function setStatus(message, tone) {
      statusNode.textContent = message;
      statusNode.className = "status" + (tone ? " " + tone : "");
    }

    async function saveCapture() {
      const body = bodyField.value.trim();
      const title = titleField.value.trim();
      if (!body) {
        setStatus("先把内容说出来或贴进输入框，再保存。", "error");
        bodyField.focus();
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
            ...(token ? { "X-Cloud-Brain-Token": token } : {})
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
        setStatus("已保存。你的想法已经进入数据库。" + (savedAt ? " 时间: " + savedAt : ""), "ok");
        bodyField.value = "";
        titleField.value = "";
        bodyField.focus();
      } catch (error) {
        setStatus("保存失败：" + (error && error.message ? error.message : "未知错误"), "error");
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

    bodyField.focus();
  </script>
</body>
</html>
"""

CAPTURE_ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <rect width="256" height="256" rx="56" fill="#1f5c4a"/>
  <path fill="#f7f1e4" d="M128 44c-24.3 0-44 19.7-44 44v32c0 24.3 19.7 44 44 44s44-19.7 44-44V88c0-24.3-19.7-44-44-44zm-60 76a12 12 0 1 1 24 0c0 19.9 16.1 36 36 36s36-16.1 36-36a12 12 0 1 1 24 0c0 28.8-20.5 52.8-48 58.4V200h28a12 12 0 1 1 0 24H108a12 12 0 1 1 0-24h28v-21.6C88.5 172.8 68 148.8 68 120z"/>
</svg>
"""


def run_api_server(
    config: AppConfig,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    auto_sync = None
    if config.cloud_capture_project_path and config.cloud_capture_auto_sync_enabled:
        auto_sync = CloudCaptureAutoSync(config)
        auto_sync.start()
    handler_class = build_handler(
        config.database_path,
        capture_token=config.capture_token,
        auto_sync=auto_sync,
    )
    server = ThreadingHTTPServer((host, port), handler_class)
    print(f"Serving Cloud Brain API at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Cloud Brain API server")
    finally:
        if auto_sync:
            auto_sync.stop()
        server.server_close()


def build_handler(
    db_path,
    capture_token: Optional[str] = None,
    auto_sync: Optional["CloudCaptureAutoSync"] = None,
):
    class CloudBrainHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)

            if parsed.path == "/capture":
                if not self._is_authorized(query):
                    self._write_unauthorized()
                    return
                self._write_html(200, CAPTURE_PAGE_HTML)
                return

            if parsed.path == "/capture.webmanifest":
                if not self._is_authorized(query):
                    self._write_unauthorized()
                    return
                self._write_json(200, CAPTURE_WEB_MANIFEST, content_type="application/manifest+json")
                return

            if parsed.path == "/capture-icon.svg":
                if not self._is_authorized(query):
                    self._write_unauthorized()
                    return
                self._write_text(200, CAPTURE_ICON_SVG, "image/svg+xml; charset=utf-8")
                return

            if parsed.path == "/health":
                self._write_json(
                    200,
                    {
                        "status": "ok",
                        "database_path": str(db_path),
                        "cloud_capture_sync": auto_sync.snapshot() if auto_sync else None,
                    },
                )
                return

            if not self._is_authorized(query):
                self._write_unauthorized()
                return

            with Database(db_path) as database:
                database.init()

                if parsed.path == "/stats":
                    self._write_json(200, {"stats": database.api_stats()})
                    return

                if parsed.path == "/migrations":
                    limit = _int_arg(query, "limit", 50)
                    rows = database.list_schema_migrations()[:limit]
                    self._write_json(
                        200,
                        {
                            "migrations": [
                                {
                                    "version": row["version"],
                                    "applied_at": row["applied_at"],
                                }
                                for row in rows
                            ],
                            "count": len(rows),
                        },
                    )
                    return

                if parsed.path == "/sync-runs":
                    limit = _int_arg(query, "limit", 20)
                    source_key = _first_arg(query, "source_key")
                    status = _first_arg(query, "status")
                    rows = database.list_sync_runs(
                        limit=limit,
                        source_key=source_key,
                        status=status,
                    )
                    runs = [database.serialize_sync_run(row) for row in rows]
                    self._write_json(200, {"sync_runs": runs, "count": len(runs)})
                    return

                if parsed.path == "/timeline":
                    limit = _int_arg(query, "limit", 20)
                    offset = _int_arg(query, "offset", 0, minimum=0)
                    source_type = _first_arg(query, "source_type")
                    item_type = _first_arg(query, "item_type")
                    tag = _first_arg(query, "tag")
                    status = _first_arg(query, "status")
                    domain = _first_arg(query, "domain")
                    try:
                        created_after, created_before = normalize_created_range(
                            _first_arg(query, "created_after"),
                            _first_arg(query, "created_before"),
                        )
                    except ValueError as exc:
                        self._write_json(400, {"error": str(exc)})
                        return
                    rows = database.item_timeline(
                        limit=limit,
                        offset=offset,
                        source_type=source_type,
                        item_type=item_type,
                        tag=tag,
                        status=status,
                        domain=domain,
                        created_after=created_after,
                        created_before=created_before,
                    )
                    items = [database.serialize_item(row, include_body=False) for row in rows]
                    self._write_json(200, {"items": items, "count": len(items)})
                    return

                if parsed.path == "/items":
                    limit = _int_arg(query, "limit", 20)
                    offset = _int_arg(query, "offset", 0, minimum=0)
                    source_type = _first_arg(query, "source_type")
                    item_type = _first_arg(query, "item_type")
                    tag = _first_arg(query, "tag")
                    status = _first_arg(query, "status")
                    domain = _first_arg(query, "domain")
                    try:
                        created_after, created_before = normalize_created_range(
                            _first_arg(query, "created_after"),
                            _first_arg(query, "created_before"),
                        )
                    except ValueError as exc:
                        self._write_json(400, {"error": str(exc)})
                        return
                    rows = database.list_items(
                        limit=limit,
                        offset=offset,
                        source_type=source_type,
                        item_type=item_type,
                        tag=tag,
                        status=status,
                        domain=domain,
                        created_after=created_after,
                        created_before=created_before,
                    )
                    items = [database.serialize_item(row, include_body=False) for row in rows]
                    self._write_json(200, {"items": items, "count": len(items)})
                    return

                if parsed.path.startswith("/items/") and parsed.path.endswith("/related"):
                    item_id = unquote(parsed.path[len("/items/") : -len("/related")])
                    limit = _int_arg(query, "limit", 10)
                    relation_type = _first_arg(query, "relation_type")
                    rows = database.list_related_items(
                        item_id,
                        limit=limit,
                        relation_type=relation_type,
                    )
                    items = [
                        database.serialize_related_item(row, include_body=False)
                        for row in rows
                    ]
                    self._write_json(
                        200,
                        {
                            "item_id": item_id,
                            "items": items,
                            "count": len(items),
                        },
                    )
                    return

                if parsed.path.startswith("/items/"):
                    item_id = unquote(parsed.path[len("/items/") :])
                    row = database.get_item(item_id)
                    if not row:
                        self._write_json(404, {"error": "Item not found", "item_id": item_id})
                        return
                    self._write_json(200, {"item": database.serialize_item(row, include_body=True)})
                    return

                if parsed.path == "/search":
                    text = _first_arg(query, "q")
                    if not text:
                        self._write_json(400, {"error": "Missing required query parameter: q"})
                        return
                    limit = _int_arg(query, "limit", 10)
                    source_type = _first_arg(query, "source_type")
                    item_type = _first_arg(query, "item_type")
                    tag = _first_arg(query, "tag")
                    status = _first_arg(query, "status")
                    domain = _first_arg(query, "domain")
                    try:
                        created_after, created_before = normalize_created_range(
                            _first_arg(query, "created_after"),
                            _first_arg(query, "created_before"),
                        )
                    except ValueError as exc:
                        self._write_json(400, {"error": str(exc)})
                        return
                    rows = database.search_items(
                        text,
                        limit=limit,
                        source_type=source_type,
                        item_type=item_type,
                        tag=tag,
                        status=status,
                        domain=domain,
                        created_after=created_after,
                        created_before=created_before,
                    )
                    items = [database.serialize_item(row, include_body=False) for row in rows]
                    self._write_json(
                        200,
                        {
                            "query": text,
                            "items": items,
                            "count": len(items),
                        },
                    )
                    return

            self._write_json(404, {"error": "Not found", "path": parsed.path})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path != "/captures":
                self._write_json(404, {"error": "Not found", "path": parsed.path})
                return

            if not self._is_authorized(query):
                self._write_unauthorized()
                return

            try:
                payload = self._read_json_body()
            except ValueError as exc:
                self._write_json(400, {"error": str(exc)})
                return

            body = str(payload.get("body") or "").strip()
            if not body:
                self._write_json(400, {"error": "Missing required field: body"})
                return

            title = _optional_string(payload, "title")
            created_at = _optional_string(payload, "created_at")
            device = _optional_string(payload, "device")
            input_type = _optional_string(payload, "input_type")
            source_label = _optional_string(payload, "source_label")
            tags = _string_list(payload.get("tags"))

            with Database(db_path) as database:
                database.init()
                try:
                    item = database.create_capture_item(
                        body=body,
                        title=title,
                        created_at=created_at,
                        device=device,
                        input_type=input_type,
                        source_label=source_label,
                        tags=tags,
                    )
                except ValueError as exc:
                    self._write_json(400, {"error": str(exc)})
                    return
                row = database.get_item(item.item_id)
                serialized_item = database.serialize_item(row, include_body=True)

            self._write_json(
                201,
                {
                    "item": serialized_item,
                },
            )

        def log_message(self, format: str, *args: object) -> None:
            return

        def _write_json(
            self,
            status: int,
            payload: Dict[str, Any],
            content_type: str = "application/json; charset=utf-8",
        ) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _write_html(self, status: int, html: str) -> None:
            self._write_text(status, html, "text/html; charset=utf-8")

        def _write_text(self, status: int, text: str, content_type: str) -> None:
            body = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> Dict[str, Any]:
            length_header = self.headers.get("Content-Length")
            if not length_header:
                raise ValueError("Missing request body")
            try:
                content_length = int(length_header)
            except ValueError as exc:
                raise ValueError("Invalid Content-Length header") from exc
            raw_body = self.rfile.read(max(0, content_length))
            if not raw_body:
                raise ValueError("Missing request body")
            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("Request body must be valid UTF-8 JSON") from exc
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object")
            return payload

        def _is_authorized(self, query: Dict[str, list[str]]) -> bool:
            if not capture_token:
                return True
            provided = (
                _first_arg(query, "token")
                or _bearer_token(self.headers.get("Authorization"))
                or _optional_header(self.headers.get("X-Cloud-Brain-Token"))
            )
            return provided == capture_token

        def _write_unauthorized(self) -> None:
            self._write_json(
                401,
                {
                    "error": "Unauthorized",
                    "message": "Missing or invalid token",
                },
            )

    return CloudBrainHandler


class CloudCaptureAutoSync:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.interval_seconds = config.cloud_capture_auto_sync_interval_seconds
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._status: Dict[str, Any] = {
            "enabled": True,
            "interval_seconds": self.interval_seconds,
            "last_attempt_at": None,
            "last_success_at": None,
            "last_error": None,
        }

    def start(self) -> None:
        self.sync_once()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="cloud-capture-auto-sync",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def sync_once(self) -> None:
        with self._lock:
            attempted_at = _utc_now_isoformat()
            self._status["last_attempt_at"] = attempted_at
            try:
                summary = sync_cloud_capture_to_local(self.config)
            except Exception as exc:
                self._status["last_error"] = str(exc)
                print(f"[cloud-capture-auto-sync] Sync failed at {attempted_at}: {exc}")
                return
            self._status["last_success_at"] = attempted_at
            self._status["last_error"] = None
            self._status["last_item_count"] = summary.item_count
            print(
                "[cloud-capture-auto-sync] "
                f"Sync completed at {attempted_at} with {summary.item_count} items"
            )

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def _run_loop(self) -> None:
        while not self._stop_event.wait(self.interval_seconds):
            self.sync_once()


def _first_arg(query: Dict[str, list[str]], key: str) -> Optional[str]:
    values = query.get(key)
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _int_arg(
    query: Dict[str, list[str]], key: str, default: int, minimum: int = 1, maximum: int = 200
) -> int:
    raw = _first_arg(query, key)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def _optional_string(payload: Dict[str, Any], key: str) -> Optional[str]:
    value = payload.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: Any) -> Optional[list[str]]:
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    values = [str(entry).strip() for entry in value]
    return [entry for entry in values if entry]


def _optional_header(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _bearer_token(value: Optional[str]) -> Optional[str]:
    text = _optional_header(value)
    if not text:
        return None
    prefix = "bearer "
    lowered = text.lower()
    if lowered.startswith(prefix):
        token = text[len(prefix) :].strip()
        return token or None
    return None


def _utc_now_isoformat() -> str:
    return datetime.now(timezone.utc).isoformat()
