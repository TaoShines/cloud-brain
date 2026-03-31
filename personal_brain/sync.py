from __future__ import annotations

from dataclasses import dataclass

from .config import AppConfig
from .database import Database
from .importers.cloud_capture import import_cloud_capture_source
from .importers import load_importer_payloads

FULL_REPLACE_MEMORY_SOURCE_KEYS = {"gemini_exports"}


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
        root_run_id = database.start_sync_run(
            "sync_configured_sources",
            location=str(config.database_path),
        )

        try:
            all_memory_items = []
            canonical_source_keys = []
            document_count = 0
            conversation_count = 0
            message_count = 0
            bookmark_count = 0

            for payload in payloads:
                source_run_id = database.start_sync_run(
                    "sync_source",
                    source_key=payload.source_key,
                    source_type=payload.source_type,
                    location=payload.location,
                    parent_run_id=root_run_id,
                )
                try:
                    if payload.source_key in FULL_REPLACE_MEMORY_SOURCE_KEYS:
                        database.purge_memory_items_for_source(payload.source_key)
                    database.upsert_source(
                        payload.source_key,
                        payload.source_type,
                        payload.location,
                    )
                    all_memory_items.extend(payload.memory_items)
                    canonical_source_keys.append(payload.source_key)
                    inserted_documents = 0
                    inserted_conversations = 0
                    inserted_messages = 0
                    synced_bookmarks = 0
                    if payload.documents:
                        inserted_documents = database.replace_documents(
                            source_key=payload.source_key,
                            location=payload.location,
                            documents=payload.documents,
                            tags_by_source_id=payload.tags_by_source_id,
                        )
                        document_count += inserted_documents
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
                        synced_bookmarks = database.sync_bookmarks(
                            source_key=payload.source_key,
                            location=payload.location,
                            bookmarks=payload.bookmarks,
                        )
                        bookmark_count += synced_bookmarks
                        all_memory_items.extend(
                            database.export_bookmark_memory_items(payload.source_key)
                        )
                    database.finish_sync_run(
                        source_run_id,
                        status="success",
                        stats={
                            "memory_items": len(payload.memory_items),
                            "documents": inserted_documents,
                            "conversations": inserted_conversations,
                            "messages": inserted_messages,
                            "bookmarks": synced_bookmarks,
                        },
                    )
                except Exception as exc:
                    database.finish_sync_run(
                        source_run_id,
                        status="failed",
                        stats={"memory_items": len(payload.memory_items)},
                        error_message=str(exc),
                    )
                    raise

            record_count = database.replace_memory_items(
                all_memory_items,
                source_keys=canonical_source_keys,
            )
            summary = SyncSummary(
                document_count=document_count,
                conversation_count=conversation_count,
                message_count=message_count,
                bookmark_count=bookmark_count,
                record_count=record_count,
            )
            database.finish_sync_run(
                root_run_id,
                status="success",
                stats={
                    "documents": summary.document_count,
                    "conversations": summary.conversation_count,
                    "messages": summary.message_count,
                    "bookmarks": summary.bookmark_count,
                    "records": summary.record_count,
                    "sources": len(canonical_source_keys),
                    "memory_items": len(all_memory_items),
                },
            )
            return summary
        except Exception as exc:
            database.finish_sync_run(
                root_run_id,
                status="failed",
                error_message=str(exc),
            )
            raise



def sync_cloud_capture_to_local(config: AppConfig) -> CloudCaptureSyncSummary:
    if not config.cloud_capture_project_path:
        raise ValueError("cloud_capture_project_path is not configured")

    payload = import_cloud_capture_source(config)
    with Database(config.database_path) as database:
        database.init()
        run_id = database.start_sync_run(
            "sync_cloud_capture_to_local",
            source_key=payload.source_key,
            source_type=payload.source_type,
            location=payload.location,
        )
        try:
            record_count = database.replace_memory_items(
                payload.memory_items,
                source_keys=[payload.source_key],
            )
            summary = CloudCaptureSyncSummary(
                item_count=len(payload.memory_items),
                record_count=record_count,
            )
            database.finish_sync_run(
                run_id,
                status="success",
                stats={
                    "items": summary.item_count,
                    "records": summary.record_count,
                },
            )
            return summary
        except Exception as exc:
            database.finish_sync_run(
                run_id,
                status="failed",
                stats={"items": len(payload.memory_items)},
                error_message=str(exc),
            )
            raise
