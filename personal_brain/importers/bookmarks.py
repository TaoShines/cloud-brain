from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import BookmarkRecord, ImporterPayload


def import_chrome_bookmarks_source(bookmarks_path: Path) -> ImporterPayload:
    bookmarks = import_chrome_bookmarks(bookmarks_path)
    return ImporterPayload(
        source_key="chrome_bookmarks",
        source_type="bookmark",
        location=str(bookmarks_path),
        memory_items=[],
        documents=[],
        conversations=[],
        messages=[],
        bookmarks=bookmarks,
        tags_by_source_id={},
    )


def import_chrome_bookmarks(bookmarks_path: Path) -> List[BookmarkRecord]:
    payload = json.loads(bookmarks_path.read_text(encoding="utf-8"))
    roots = payload.get("roots", {})
    records: List[BookmarkRecord] = []
    for root_name, node in roots.items():
        if not isinstance(node, dict):
            continue
        folder_name = str(node.get("name") or root_name).strip() or root_name
        walk_bookmark_tree(
            node=node,
            current_path=[folder_name],
            source_path=str(bookmarks_path),
            results=records,
        )
    return records


def walk_bookmark_tree(
    node: Dict[str, Any],
    current_path: List[str],
    source_path: str,
    results: List[BookmarkRecord],
) -> None:
    node_type = node.get("type")
    if node_type == "url":
        url = node.get("url")
        bookmark_id = node.get("guid") or node.get("id")
        if isinstance(url, str) and bookmark_id:
            title = str(node.get("name") or url).strip() or url
            results.append(
                BookmarkRecord(
                    bookmark_id=f"bookmark:{bookmark_id}",
                    title=title,
                    url=url,
                    folder_path=" / ".join(current_path),
                    added_at=normalize_chrome_timestamp(node.get("date_added")),
                    source_path=source_path,
                )
            )
        return

    for child in node.get("children", []) or []:
        if not isinstance(child, dict):
            continue
        next_path = current_path
        child_name = str(child.get("name") or "").strip()
        if child.get("type") == "folder" and child_name:
            next_path = [*current_path, child_name]
        walk_bookmark_tree(child, next_path, source_path, results)


def normalize_chrome_timestamp(value: object) -> Optional[str]:
    if value is None:
        return None
    try:
        microseconds = int(str(value))
    except (TypeError, ValueError):
        return None
    epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
    return (epoch + timedelta(microseconds=microseconds)).isoformat()
