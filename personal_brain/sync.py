from __future__ import annotations

from dataclasses import dataclass

from .config import AppConfig
from .database import Database
from .importers.cloud_capture import import_cloud_capture_source
from .importers import load_importer_payloads


@dataclass
class SyncSummary:
    document_count: int
    conversation_count: int
    message_count: int
    bookmark_count: int
    record_count: int


@dataclass
class CloudCaptureSyncSummary:
    item_count: int
    record_count: int


def sync_configured_sources(config: AppConfig) -> SyncSummary:
    payloads = load_importer_payloads(config)
    if not payloads:
        raise ValueError(
            "No data sources configured. Set at least one source path in "
            "config.local.json or your chosen config file."
        )

    with Database(config.database_path) as database:
        database.init()

        all_memory_items = []
        canonical_source_keys = []
        document_count = 0
        conversation_count = 0
        message_count = 0
        bookmark_count = 0

        for payload in payloads:
            all_memory_items.extend(payload.memory_items)
            canonical_source_keys.append(payload.source_key)
            if payload.documents:
                document_count += database.replace_documents(
                    source_key=payload.source_key,
                    location=payload.location,
                    documents=payload.documents,
                    tags_by_source_id=payload.tags_by_source_id,
                )
            if payload.conversations or payload.messages:
                inserted_conversations, inserted_messages = database.replace_conversations(
                    source_key=payload.source_key,
                    location=payload.location,
                    conversations=payload.conversations,
                    messages=payload.messages,
                )
                conversation_count += inserted_conversations
                message_count += inserted_messages
            if payload.bookmarks:
                bookmark_count += database.sync_bookmarks(
                    source_key=payload.source_key,
                    location=payload.location,
                    bookmarks=payload.bookmarks,
                )
                all_memory_items.extend(
                    database.export_bookmark_memory_items(payload.source_key)
                )

        record_count = database.replace_memory_items(
            all_memory_items,
            source_keys=canonical_source_keys,
        )

    return SyncSummary(
        document_count=document_count,
        conversation_count=conversation_count,
        message_count=message_count,
        bookmark_count=bookmark_count,
        record_count=record_count,
    )


def sync_cloud_capture_to_local(config: AppConfig) -> CloudCaptureSyncSummary:
    if not config.cloud_capture_project_path:
        raise ValueError("cloud_capture_project_path is not configured")

    payload = import_cloud_capture_source(config)
    with Database(config.database_path) as database:
        database.init()
        record_count = database.replace_memory_items(
            payload.memory_items,
            source_keys=[payload.source_key],
        )

    return CloudCaptureSyncSummary(
        item_count=len(payload.memory_items),
        record_count=record_count,
    )
