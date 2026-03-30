from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..config import AppConfig
from ..models import ConversationRecord, ImporterPayload, MemoryItem, MessageRecord


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


def import_codex_source(state_db_path: Path, config: AppConfig) -> ImporterPayload:
    conversations, messages = import_codex_history(state_db_path, config)
    memory_items = build_codex_memory_items(conversations, messages)
    return ImporterPayload(
        source_key="codex_history",
        source_type="codex",
        location=str(state_db_path),
        memory_items=memory_items,
        documents=[],
        conversations=conversations,
        messages=messages,
        tags_by_source_id={},
    )


def build_codex_memory_items(
    conversations: List[ConversationRecord], messages: List[MessageRecord]
) -> List[MemoryItem]:
    items: List[MemoryItem] = []
    conversation_locations = {
        conversation.thread_id: conversation.rollout_path for conversation in conversations
    }

    for conversation in conversations:
        items.append(
            MemoryItem(
                item_id=conversation.thread_id,
                source_key="codex_history",
                source_type="codex",
                external_id=conversation.thread_id,
                item_type="conversation",
                title=conversation.title,
                body=conversation.title,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
                imported_at=None,
                checksum=build_checksum(
                    conversation.thread_id,
                    conversation.title,
                    conversation.cwd,
                    conversation.updated_at,
                ),
                location=conversation.rollout_path,
                parent_id=None,
                metadata={
                    "cwd": conversation.cwd,
                    "model": conversation.model,
                    "source": conversation.source,
                },
                tags=["codex", "conversation"],
            )
        )

    for message in messages:
        item_id = f"{message.thread_id}:{message.message_index}"
        role_title = message.role if not message.phase else f"{message.role} {message.phase}"
        items.append(
            MemoryItem(
                item_id=item_id,
                source_key="codex_history",
                source_type="codex",
                external_id=item_id,
                item_type="message",
                title=role_title,
                body=message.content,
                created_at=message.created_at,
                updated_at=message.created_at,
                imported_at=None,
                checksum=build_checksum(
                    item_id,
                    role_title,
                    message.content,
                    message.created_at,
                ),
                location=conversation_locations.get(message.thread_id),
                parent_id=message.thread_id,
                metadata={
                    "thread_id": message.thread_id,
                    "message_index": message.message_index,
                    "role": message.role,
                    "phase": message.phase,
                },
                tags=["codex", message.role] + ([message.phase] if message.phase else []),
            )
        )

    return items


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


def build_checksum(*parts: Optional[str]) -> str:
    import hashlib

    normalized = "||".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
