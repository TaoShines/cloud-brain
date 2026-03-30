from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse

from .database import Database


def run_api_server(db_path, host: str = "127.0.0.1", port: int = 8765) -> None:
    handler_class = build_handler(db_path)
    server = ThreadingHTTPServer((host, port), handler_class)
    print(f"Serving Cloud Brain API at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Cloud Brain API server")
    finally:
        server.server_close()


def build_handler(db_path):
    class CloudBrainHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)

            if parsed.path == "/health":
                self._write_json(
                    200,
                    {
                        "status": "ok",
                        "database_path": str(db_path),
                    },
                )
                return

            with Database(db_path) as database:
                database.init()

                if parsed.path == "/stats":
                    self._write_json(200, {"stats": database.api_stats()})
                    return

                if parsed.path == "/timeline":
                    limit = _int_arg(query, "limit", 20)
                    source_type = _first_arg(query, "source_type")
                    item_type = _first_arg(query, "item_type")
                    tag = _first_arg(query, "tag")
                    rows = database.item_timeline(
                        limit=limit,
                        source_type=source_type,
                        item_type=item_type,
                        tag=tag,
                    )
                    items = [database.serialize_item(row, include_body=False) for row in rows]
                    self._write_json(200, {"items": items, "count": len(items)})
                    return

                if parsed.path == "/items":
                    limit = _int_arg(query, "limit", 20)
                    source_type = _first_arg(query, "source_type")
                    item_type = _first_arg(query, "item_type")
                    tag = _first_arg(query, "tag")
                    rows = database.list_items(
                        limit=limit,
                        source_type=source_type,
                        item_type=item_type,
                        tag=tag,
                    )
                    items = [database.serialize_item(row, include_body=False) for row in rows]
                    self._write_json(200, {"items": items, "count": len(items)})
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
                    rows = database.search_items(
                        text,
                        limit=limit,
                        source_type=source_type,
                        item_type=item_type,
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

        def log_message(self, format: str, *args: object) -> None:
            return

        def _write_json(self, status: int, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return CloudBrainHandler


def _first_arg(query: Dict[str, list[str]], key: str) -> Optional[str]:
    values = query.get(key)
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _int_arg(query: Dict[str, list[str]], key: str, default: int) -> int:
    raw = _first_arg(query, key)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(1, min(value, 200))
