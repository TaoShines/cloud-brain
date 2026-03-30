from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..config import AppConfig
from ..models import ConversationRecord, MessageRecord


def import_codex_history(
    state_db_path: Path, config: AppConfig
) -> Tuple[List[ConversationRecord], List[MessageRecord]]:
    connection = sqlite3.connect(state_db_path)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT
            id,
            title,
            cwd,
            source,
            model,
            created_at,
            updated_at,
            rollout_path
        FROM threads
        ORDER BY updated_at DESC
        """
    ).fetchall()
    connection.close()

    conversations: List[ConversationRecord] = []
    messages: List[MessageRecord] = []

    for row in rows:
        rollout_path = Path(row["rollout_path"])
        conversations.append(
            ConversationRecord(
                thread_id=row["id"],
                title=row["title"].strip(),
                cwd=row["cwd"],
                source=row["source"],
                model=row["model"],
                created_at=normalize_unix(row["created_at"]),
                updated_at=normalize_unix(row["updated_at"]),
                rollout_path=str(rollout_path),
            )
        )
        if rollout_path.exists():
            messages.extend(parse_rollout_messages(rollout_path, row["id"], config))

    return conversations, messages


def parse_rollout_messages(
    rollout_path: Path, thread_id: str, config: AppConfig
) -> List[MessageRecord]:
    results: List[MessageRecord] = []
    next_index = 0

    for line in rollout_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("type") != "response_item":
            continue
        payload = record.get("payload") or {}
        if payload.get("type") != "message":
            continue

        role = payload.get("role")
        if role not in {"user", "assistant"}:
            continue

        phase = payload.get("phase")
        if role == "assistant":
            if phase == "commentary" and not config.include_assistant_commentary:
                continue
            if phase == "final_answer" and not config.include_assistant_final_answers:
                continue

        content = flatten_message_content(payload.get("content") or [])
        if not content.strip():
            continue

        results.append(
            MessageRecord(
                thread_id=thread_id,
                message_index=next_index,
                role=role,
                phase=phase,
                content=content.strip(),
                created_at=record.get("timestamp"),
            )
        )
        next_index += 1

    return results


def flatten_message_content(items: List[Dict[str, object]]) -> str:
    chunks: List[str] = []
    for item in items:
        item_type = item.get("type")
        if item_type in {"input_text", "output_text"}:
            text = item.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunks)


def normalize_unix(value: object) -> Optional[str]:
    if value is None:
        return None
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
