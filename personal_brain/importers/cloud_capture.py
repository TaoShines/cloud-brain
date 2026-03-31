from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from ..config import AppConfig
from ..models import ImporterPayload, MemoryItem


def import_cloud_capture_source(config: AppConfig) -> ImporterPayload:
    if not config.cloud_capture_project_path:
        raise ValueError("cloud_capture_project_path is not configured")
    rows = fetch_cloud_capture_rows(
        project_path=config.cloud_capture_project_path,
        database_name=config.cloud_capture_database_name or "cloud-brain-capture",
    )
    memory_items = build_cloud_capture_memory_items(rows)
    return ImporterPayload(
        source_key="cloudflare_capture",
        source_type="capture",
        location=str(config.cloud_capture_project_path),
        memory_items=memory_items,
        documents=[],
        conversations=[],
        messages=[],
        bookmarks=[],
        tags_by_source_id={},
    )


def fetch_cloud_capture_rows(project_path: Path, database_name: str) -> List[Dict[str, Any]]:
    command = [
        "npx",
        "wrangler",
        "d1",
        "execute",
        database_name,
        "--remote",
        "--json",
        "--command",
        (
            "SELECT item_id, title, body, created_at, device, input_type, "
            "source_label, tags_json FROM captures ORDER BY created_at DESC"
        ),
    ]
    env = {
        **dict(os.environ),
        "PATH": _build_node20_path(),
    }
    completed = subprocess.run(
        command,
        cwd=project_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    if not payload:
        return []
    first_entry = payload[0]
    return list(first_entry.get("results", []))


def build_cloud_capture_memory_items(rows: List[Dict[str, Any]]) -> List[MemoryItem]:
    items: List[MemoryItem] = []
    for row in rows:
        item_id = str(row["item_id"]).strip()
        title = str(row.get("title") or "").strip() or "capture"
        body = str(row.get("body") or "").strip()
        created_at = _optional_text(row.get("created_at"))
        device = _optional_text(row.get("device"))
        input_type = _optional_text(row.get("input_type"))
        source_label = _optional_text(row.get("source_label"))
        tags = _decode_tags(row.get("tags_json"))
        items.append(
            MemoryItem(
                item_id=item_id,
                source_key="cloudflare_capture",
                source_type="capture",
                external_id=item_id,
                item_type="capture",
                title=title,
                body=body,
                created_at=created_at,
                updated_at=created_at,
                imported_at=None,
                checksum=build_checksum(item_id, title, body, created_at),
                location=f"cloudflare-d1:{item_id}",
                parent_id=None,
                metadata={
                    "capture_kind": "cloud",
                    "device": device,
                    "input_type": input_type,
                    "source_label": source_label,
                    "synced_from": "cloudflare_d1",
                },
                tags=tags,
            )
        )
    return items


def build_checksum(*parts: object) -> str:
    import hashlib

    normalized = "||".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decode_tags(value: object) -> List[str]:
    if value is None:
        return ["capture", "cloud"]
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError:
        payload = []
    values = payload if isinstance(payload, list) else []
    normalized: List[str] = []
    seen = set()
    for tag in values:
        cleaned = str(tag).strip().lower()
        if not cleaned or cleaned in seen:
            continue
        normalized.append(cleaned)
        seen.add(cleaned)
    for fallback in ["capture", "cloud"]:
        if fallback not in seen:
            normalized.append(fallback)
            seen.add(fallback)
    return normalized


def _build_node20_path() -> str:
    current_path = os.environ.get("PATH", "")
    node20_bin = "/opt/homebrew/opt/node@20/bin"
    if node20_bin in current_path.split(":"):
        return current_path
    return f"{node20_bin}:{current_path}" if current_path else node20_bin
