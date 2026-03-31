from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from .models import (
    BookmarkRecord,
    ConversationRecord,
    DocumentRecord,
    ItemLink,
    MemoryItem,
    MessageRecord,
    UnifiedRecord,
)


BASE_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL,
    location TEXT NOT NULL,
    last_synced_at TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL UNIQUE,
    doc_type TEXT NOT NULL,
    title TEXT NOT NULL,
    slug TEXT,
    summary TEXT,
    content TEXT NOT NULL,
    source_path TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS document_tags (
    document_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (document_id, tag),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    cwd TEXT NOT NULL,
    source TEXT NOT NULL,
    model TEXT,
    created_at TEXT,
    updated_at TEXT,
    rollout_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,
    message_index INTEGER NOT NULL,
    role TEXT NOT NULL,
    phase TEXT,
    content TEXT NOT NULL,
    created_at TEXT,
    UNIQUE (thread_id, message_index),
    FOREIGN KEY (thread_id) REFERENCES conversations(thread_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_key TEXT NOT NULL UNIQUE,
    record_type TEXT NOT NULL,
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT,
    location TEXT,
    parent_key TEXT
);

CREATE TABLE IF NOT EXISTS record_tags (
    record_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (record_id, tag),
    FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL UNIQUE,
    source_key TEXT NOT NULL,
    source_type TEXT NOT NULL,
    external_id TEXT NOT NULL,
    item_type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT,
    imported_at TEXT,
    checksum TEXT NOT NULL,
    location TEXT,
    parent_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS item_tags (
    item_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (item_id, tag),
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bookmark_id TEXT NOT NULL UNIQUE,
    source_key TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    folder_path TEXT NOT NULL,
    added_at TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    deleted_at TEXT,
    status TEXT NOT NULL,
    source_path TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    entity_type,
    entity_key,
    title,
    body,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""

MIGRATIONS: List[Tuple[str, str]] = [
    (
        "2026_04_01_001_item_links",
        """
        CREATE TABLE IF NOT EXISTS item_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_item_id TEXT NOT NULL,
            target_item_id TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            relation_value TEXT,
            score REAL NOT NULL DEFAULT 1.0,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (source_item_id, target_item_id, relation_type, relation_value),
            FOREIGN KEY (source_item_id) REFERENCES items(item_id) ON DELETE CASCADE,
            FOREIGN KEY (target_item_id) REFERENCES items(item_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_item_links_source_item_id
        ON item_links(source_item_id);
        CREATE INDEX IF NOT EXISTS idx_item_links_target_item_id
        ON item_links(target_item_id);
        CREATE INDEX IF NOT EXISTS idx_item_links_relation_type
        ON item_links(relation_type);
        """,
    ),
    (
        "2026_04_01_002_sync_runs",
        """
        CREATE TABLE IF NOT EXISTS sync_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_run_id INTEGER,
            sync_type TEXT NOT NULL,
            source_key TEXT,
            source_type TEXT,
            location TEXT,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            error_message TEXT,
            stats_json TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (parent_run_id) REFERENCES sync_runs(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sync_runs_started_at
        ON sync_runs(started_at DESC);
        CREATE INDEX IF NOT EXISTS idx_sync_runs_source_key
        ON sync_runs(source_key);
        CREATE INDEX IF NOT EXISTS idx_sync_runs_status
        ON sync_runs(status);
        """,
    ),
    (
        "2026_04_01_003_sync_run_warnings",
        """
        ALTER TABLE sync_runs
        ADD COLUMN warnings_json TEXT NOT NULL DEFAULT '[]';
        """,
    ),
]


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(db_path)
        self.connection.row_factory = sqlite3.Row
        self._closed = False

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self.connection.close()
        self._closed = True

    def init(self) -> None:
        self.connection.executescript(BASE_SCHEMA)
        self._apply_migrations()
        self._backfill_item_metadata_contract()
        self.connection.commit()

    def _apply_migrations(self) -> None:
        applied_versions = {
            row["version"]
            for row in self.connection.execute(
                "SELECT version FROM schema_migrations"
            ).fetchall()
        }
        for version, sql in MIGRATIONS:
            if version in applied_versions:
                continue
            try:
                self.connection.executescript(sql)
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
            self.connection.execute(
                """
                INSERT INTO schema_migrations (version, applied_at)
                VALUES (?, datetime('now'))
                """,
                (version,),
            )

    def list_schema_migrations(self) -> List[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT version, applied_at
            FROM schema_migrations
            ORDER BY applied_at ASC, version ASC
            """
        ).fetchall()

    def _backfill_item_metadata_contract(self) -> None:
        rows = self.connection.execute(
            """
            SELECT item_id, metadata_json
            FROM items
            """
        ).fetchall()
        for row in rows:
            metadata = self._decode_raw_metadata(row["metadata_json"])
            normalized = self._normalize_item_metadata(metadata)
            encoded = json.dumps(normalized, ensure_ascii=True, sort_keys=True)
            if encoded == (row["metadata_json"] or ""):
                continue
            self.connection.execute(
                """
                UPDATE items
                SET metadata_json = ?
                WHERE item_id = ?
                """,
                (encoded, row["item_id"]),
            )

    def upsert_source(self, source_key: str, source_type: str, location: str) -> None:
        self.connection.execute(
            """
            INSERT INTO sources (source_key, source_type, location, last_synced_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(source_key) DO UPDATE SET
                source_type = excluded.source_type,
                location = excluded.location,
                last_synced_at = datetime('now')
            """,
            (source_key, source_type, location),
        )

    def replace_documents(
        self,
        source_key: str,
        location: str,
        documents: Iterable[DocumentRecord],
        tags_by_source_id: Dict[str, List[str]],
    ) -> int:
        docs = list(documents)
        self.upsert_source(source_key, "blog", location)
        self.connection.execute("DELETE FROM search_index WHERE entity_type = 'document'")
        self.connection.execute("DELETE FROM document_tags")
        self.connection.execute("DELETE FROM documents")

        inserted = 0
        for doc in docs:
            cursor = self.connection.execute(
                """
                INSERT INTO documents (
                    source_id, doc_type, title, slug, summary, content, source_path,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc.source_id,
                    doc.doc_type,
                    doc.title,
                    doc.slug,
                    doc.summary,
                    doc.content,
                    doc.source_path,
                    doc.created_at,
                    doc.updated_at,
                ),
            )
            document_id = cursor.lastrowid
            for tag in tags_by_source_id.get(doc.source_id, []):
                self.connection.execute(
                    "INSERT INTO document_tags (document_id, tag) VALUES (?, ?)",
                    (document_id, tag),
                )
            self.connection.execute(
                """
                INSERT INTO search_index (entity_type, entity_key, title, body)
                VALUES (?, ?, ?, ?)
                """,
                ("document", doc.source_id, doc.title, doc.content),
            )
            inserted += 1

        self.connection.commit()
        return inserted

    def replace_conversations(
        self,
        source_key: str,
        location: str,
        conversations: Iterable[ConversationRecord],
        messages: Iterable[MessageRecord],
    ) -> Tuple[int, int]:
        conversation_rows = list(conversations)
        message_rows = list(messages)

        self.upsert_source(source_key, "codex", location)
        self.connection.execute(
            "DELETE FROM search_index WHERE entity_type IN ('conversation', 'message')"
        )
        self.connection.execute("DELETE FROM messages")
        self.connection.execute("DELETE FROM conversations")

        inserted_conversations = 0
        inserted_messages = 0

        for conversation in conversation_rows:
            self.connection.execute(
                """
                INSERT INTO conversations (
                    thread_id, title, cwd, source, model, created_at, updated_at, rollout_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation.thread_id,
                    conversation.title,
                    conversation.cwd,
                    conversation.source,
                    conversation.model,
                    conversation.created_at,
                    conversation.updated_at,
                    conversation.rollout_path,
                ),
            )
            self.connection.execute(
                """
                INSERT INTO search_index (entity_type, entity_key, title, body)
                VALUES (?, ?, ?, ?)
                """,
                (
                    "conversation",
                    conversation.thread_id,
                    conversation.title,
                    conversation.cwd,
                ),
            )
            inserted_conversations += 1

        for message in message_rows:
            entity_key = f"{message.thread_id}:{message.message_index}"
            self.connection.execute(
                """
                INSERT INTO messages (
                    thread_id, message_index, role, phase, content, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message.thread_id,
                    message.message_index,
                    message.role,
                    message.phase,
                    message.content,
                    message.created_at,
                ),
            )
            self.connection.execute(
                """
                INSERT INTO search_index (entity_type, entity_key, title, body)
                VALUES (?, ?, ?, ?)
                """,
                (
                    "message",
                    entity_key,
                    f"{message.role} {message.phase or ''}".strip(),
                    message.content,
                ),
            )
            inserted_messages += 1

        self.connection.commit()
        return inserted_conversations, inserted_messages

    def stats(self) -> sqlite3.Row:
        return self.connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM records) AS record_count,
                (SELECT COUNT(*) FROM items) AS item_count,
                (SELECT COUNT(*) FROM item_links) AS item_link_count,
                (SELECT COUNT(*) FROM schema_migrations) AS schema_migration_count,
                (SELECT COUNT(*) FROM sync_runs) AS sync_run_count,
                (SELECT COUNT(*) FROM documents) AS document_count,
                (SELECT COUNT(*) FROM document_tags) AS document_tag_count,
                (SELECT COUNT(*) FROM item_tags) AS item_tag_count,
                (SELECT COUNT(*) FROM conversations) AS conversation_count,
                (SELECT COUNT(*) FROM messages) AS message_count,
                (SELECT COUNT(*) FROM bookmarks) AS bookmark_count,
                (SELECT COUNT(*) FROM search_index) AS search_index_count
            """
        ).fetchone()

    def api_stats(self) -> Dict[str, int]:
        stats = self.stats()
        return {
            "records": stats["record_count"],
            "items": stats["item_count"],
            "item_links": stats["item_link_count"],
            "schema_migrations": stats["schema_migration_count"],
            "sync_runs": stats["sync_run_count"],
            "documents": stats["document_count"],
            "document_tags": stats["document_tag_count"],
            "item_tags": stats["item_tag_count"],
            "conversations": stats["conversation_count"],
            "messages": stats["message_count"],
            "bookmarks": stats["bookmark_count"],
            "search_index": stats["search_index_count"],
        }

    def sync_bookmarks(
        self, source_key: str, location: str, bookmarks: Iterable[BookmarkRecord]
    ) -> int:
        bookmark_rows = list(bookmarks)
        self.upsert_source(source_key, "bookmark", location)

        seen_ids: List[str] = []
        for bookmark in bookmark_rows:
            seen_ids.append(bookmark.bookmark_id)
            self.connection.execute(
                """
                INSERT INTO bookmarks (
                    bookmark_id, source_key, title, url, folder_path, added_at,
                    first_seen_at, last_seen_at, deleted_at, status, source_path
                ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), NULL, 'active', ?)
                ON CONFLICT(bookmark_id) DO UPDATE SET
                    title = excluded.title,
                    url = excluded.url,
                    folder_path = excluded.folder_path,
                    added_at = excluded.added_at,
                    last_seen_at = datetime('now'),
                    deleted_at = NULL,
                    status = 'active',
                    source_path = excluded.source_path
                """,
                (
                    bookmark.bookmark_id,
                    source_key,
                    bookmark.title,
                    bookmark.url,
                    bookmark.folder_path,
                    bookmark.added_at,
                    bookmark.source_path,
                ),
            )

        if seen_ids:
            placeholders = ", ".join("?" for _ in seen_ids)
            self.connection.execute(
                f"""
                UPDATE bookmarks
                SET status = 'deleted',
                    deleted_at = COALESCE(deleted_at, datetime('now'))
                WHERE source_key = ?
                  AND bookmark_id NOT IN ({placeholders})
                  AND status != 'deleted'
                """,
                [source_key, *seen_ids],
            )
        else:
            self.connection.execute(
                """
                UPDATE bookmarks
                SET status = 'deleted',
                    deleted_at = COALESCE(deleted_at, datetime('now'))
                WHERE source_key = ?
                  AND status != 'deleted'
                """,
                (source_key,),
            )

        self.connection.commit()
        return len(bookmark_rows)

    def export_bookmark_memory_items(self, source_key: str) -> List[MemoryItem]:
        rows = self.connection.execute(
            """
            SELECT
                bookmark_id,
                source_key,
                title,
                url,
                folder_path,
                added_at,
                deleted_at,
                status,
                source_path
            FROM bookmarks
            WHERE source_key = ?
            ORDER BY added_at DESC, id DESC
            """,
            (source_key,),
        ).fetchall()

        items: List[MemoryItem] = []
        for row in rows:
            deleted_at = row["deleted_at"]
            status = row["status"]
            body = row["url"] if not deleted_at else f"{row['url']}\nDeleted at: {deleted_at}"
            items.append(
                MemoryItem(
                    item_id=row["bookmark_id"],
                    source_key=row["source_key"],
                    source_type="bookmark",
                    external_id=row["bookmark_id"],
                    item_type="bookmark",
                    title=row["title"],
                    body=body,
                    created_at=row["added_at"],
                    updated_at=deleted_at or row["added_at"],
                    imported_at=None,
                    checksum=self._build_checksum(
                        row["bookmark_id"],
                        row["title"],
                        row["url"],
                        row["folder_path"],
                        status,
                        deleted_at,
                    ),
                    location=row["source_path"],
                    parent_id=None,
                    metadata={
                        "domain": self._extract_domain(row["url"]),
                        "url": row["url"],
                        "folder_path": row["folder_path"],
                        "status": status,
                        "deleted_at": deleted_at,
                    },
                    tags=["bookmark", status],
                )
            )
        return items

    def search(
        self, query: str, entity_type: Optional[str] = None, limit: int = 10
    ) -> List[sqlite3.Row]:
        sql = """
            SELECT
                entity_type,
                entity_key,
                title,
                CASE
                    WHEN entity_type = 'document' THEN (
                        SELECT created_at FROM documents WHERE source_id = entity_key
                    )
                    WHEN entity_type = 'conversation' THEN (
                        SELECT created_at FROM conversations WHERE thread_id = entity_key
                    )
                    WHEN entity_type = 'message' THEN (
                        SELECT created_at
                        FROM messages
                        WHERE messages.thread_id || ':' || messages.message_index = entity_key
                    )
                END AS created_at,
                snippet(search_index, 3, '[', ']', ' ... ', 16) AS snippet
            FROM search_index
            WHERE search_index MATCH ?
        """
        parameters: list[object] = [query]
        if entity_type:
            sql += " AND entity_type = ?"
            parameters.append(entity_type)
        sql += " ORDER BY rank LIMIT ?"
        parameters.append(limit)
        rows = self.connection.execute(sql, parameters).fetchall()
        if rows:
            return rows

        fallback_sql = """
            SELECT
                entity_type,
                entity_key,
                title,
                CASE
                    WHEN entity_type = 'document' THEN (
                        SELECT created_at FROM documents WHERE source_id = entity_key
                    )
                    WHEN entity_type = 'conversation' THEN (
                        SELECT created_at FROM conversations WHERE thread_id = entity_key
                    )
                    WHEN entity_type = 'message' THEN (
                        SELECT created_at
                        FROM messages
                        WHERE messages.thread_id || ':' || messages.message_index = entity_key
                    )
                END AS created_at,
                CASE
                    WHEN instr(body, ?) > 0 THEN substr(
                        body,
                        CASE
                            WHEN instr(body, ?) - 40 > 1 THEN instr(body, ?) - 40
                            ELSE 1
                        END,
                        200
                    )
                    WHEN instr(title, ?) > 0 THEN title
                    ELSE substr(body, 1, 160)
                END AS snippet
            FROM search_index
            WHERE (title LIKE ? OR body LIKE ?)
        """
        like_pattern = f"%{query}%"
        fallback_parameters: List[object] = [
            query,
            query,
            query,
            query,
            like_pattern,
            like_pattern,
        ]
        if entity_type:
            fallback_sql += " AND entity_type = ?"
            fallback_parameters.append(entity_type)
        fallback_sql += " ORDER BY entity_type, entity_key LIMIT ?"
        fallback_parameters.append(limit)
        return self.connection.execute(fallback_sql, fallback_parameters).fetchall()

    def search_items(
        self,
        query: str,
        limit: int = 10,
        source_type: Optional[str] = None,
        item_type: Optional[str] = None,
        tag: Optional[str] = None,
        status: Optional[str] = None,
        domain: Optional[str] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
    ) -> List[sqlite3.Row]:
        sql = """
            SELECT
                items.item_id,
                items.source_key,
                items.source_type,
                items.external_id,
                items.item_type,
                items.title,
                items.body,
                items.created_at,
                items.updated_at,
                items.imported_at,
                items.checksum,
                items.location,
                items.parent_id,
                items.metadata_json
            FROM search_index
            JOIN items ON items.item_id = search_index.entity_key
            WHERE search_index MATCH ?
              AND search_index.entity_type = 'item'
        """
        parameters: List[object] = [query]
        if status is None:
            sql += " AND coalesce(json_extract(items.metadata_json, '$.status'), 'active') != 'deleted'"
        if source_type:
            sql += " AND items.source_type = ?"
            parameters.append(source_type)
        if item_type:
            sql += " AND items.item_type = ?"
            parameters.append(item_type)
        if tag:
            sql += """
                AND EXISTS (
                    SELECT 1
                    FROM item_tags
                    WHERE item_tags.item_id = items.id
                      AND item_tags.tag = ?
                )
            """
            parameters.append(tag)
        if status:
            sql += " AND json_extract(items.metadata_json, '$.status') = ?"
            parameters.append(status)
        if domain:
            sql += " AND lower(json_extract(items.metadata_json, '$.domain')) = lower(?)"
            parameters.append(domain)
        if created_after:
            sql += " AND items.created_at >= ?"
            parameters.append(created_after)
        if created_before:
            sql += " AND items.created_at <= ?"
            parameters.append(created_before)
        sql += " ORDER BY rank LIMIT ?"
        parameters.append(limit)
        rows = self.connection.execute(sql, parameters).fetchall()
        if rows:
            return rows

        fallback_sql = """
            SELECT
                item_id,
                source_key,
                source_type,
                external_id,
                item_type,
                title,
                body,
                created_at,
                updated_at,
                imported_at,
                checksum,
                location,
                parent_id,
                metadata_json,
                CASE
                    WHEN instr(lower(body), lower(?)) > 0 THEN substr(
                        body,
                        CASE
                            WHEN instr(lower(body), lower(?)) - 40 > 1 THEN instr(lower(body), lower(?)) - 40
                            ELSE 1
                        END,
                        200
                    )
                    WHEN instr(lower(title), lower(?)) > 0 THEN title
                    ELSE substr(body, 1, 160)
                END AS snippet
            FROM items
            WHERE (lower(title) LIKE lower(?) OR lower(body) LIKE lower(?))
        """
        like_pattern = f"%{query}%"
        fallback_parameters: List[object] = [
            query,
            query,
            query,
            query,
            like_pattern,
            like_pattern,
        ]
        if status is None:
            fallback_sql += " AND coalesce(json_extract(metadata_json, '$.status'), 'active') != 'deleted'"
        if source_type:
            fallback_sql += " AND source_type = ?"
            fallback_parameters.append(source_type)
        if item_type:
            fallback_sql += " AND item_type = ?"
            fallback_parameters.append(item_type)
        if status:
            fallback_sql += " AND json_extract(metadata_json, '$.status') = ?"
            fallback_parameters.append(status)
        if domain:
            fallback_sql += " AND lower(json_extract(metadata_json, '$.domain')) = lower(?)"
            fallback_parameters.append(domain)
        if created_after:
            fallback_sql += " AND created_at >= ?"
            fallback_parameters.append(created_after)
        if created_before:
            fallback_sql += " AND created_at <= ?"
            fallback_parameters.append(created_before)
        fallback_sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
        fallback_parameters.append(limit)
        return self.connection.execute(fallback_sql, fallback_parameters).fetchall()

    def list_items(
        self,
        limit: int = 20,
        offset: int = 0,
        source_type: Optional[str] = None,
        item_type: Optional[str] = None,
        tag: Optional[str] = None,
        status: Optional[str] = None,
        domain: Optional[str] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
    ) -> List[sqlite3.Row]:
        sql = """
            SELECT
                items.item_id,
                items.source_key,
                items.source_type,
                items.external_id,
                items.item_type,
                items.title,
                items.body,
                items.created_at,
                items.updated_at,
                items.imported_at,
                items.checksum,
                items.location,
                items.parent_id,
                items.metadata_json
            FROM items
        """
        parameters: List[object] = []
        if tag:
            sql += """
                JOIN item_tags ON item_tags.item_id = items.id
            """
        sql += " WHERE 1 = 1"
        if status is None:
            sql += " AND coalesce(json_extract(items.metadata_json, '$.status'), 'active') != 'deleted'"
        if source_type:
            sql += " AND items.source_type = ?"
            parameters.append(source_type)
        if item_type:
            sql += " AND items.item_type = ?"
            parameters.append(item_type)
        if tag:
            sql += " AND item_tags.tag = ?"
            parameters.append(tag)
        if status:
            sql += " AND json_extract(items.metadata_json, '$.status') = ?"
            parameters.append(status)
        if domain:
            sql += " AND lower(json_extract(items.metadata_json, '$.domain')) = lower(?)"
            parameters.append(domain)
        if created_after:
            sql += " AND items.created_at >= ?"
            parameters.append(created_after)
        if created_before:
            sql += " AND items.created_at <= ?"
            parameters.append(created_before)
        sql += """
            ORDER BY
                CASE WHEN items.created_at IS NULL THEN 1 ELSE 0 END,
                items.created_at DESC,
                items.id DESC
            LIMIT ? OFFSET ?
        """
        parameters.append(limit)
        parameters.append(max(0, offset))
        return self.connection.execute(sql, parameters).fetchall()

    def item_timeline(
        self,
        limit: int = 20,
        offset: int = 0,
        source_type: Optional[str] = None,
        item_type: Optional[str] = None,
        tag: Optional[str] = None,
        status: Optional[str] = None,
        domain: Optional[str] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
    ) -> List[sqlite3.Row]:
        rows = self.list_items(
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
        return rows

    def get_item(self, item_id: str) -> Optional[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT
                item_id,
                source_key,
                source_type,
                external_id,
                item_type,
                title,
                body,
                created_at,
                updated_at,
                imported_at,
                checksum,
                location,
                parent_id,
                metadata_json
            FROM items
            WHERE item_id = ?
            """,
            (item_id,),
        ).fetchone()

    def list_related_items(
        self,
        item_id: str,
        limit: int = 10,
        relation_type: Optional[str] = None,
    ) -> List[sqlite3.Row]:
        sql = """
            SELECT
                item_links.relation_type,
                CASE
                    WHEN item_links.relation_type = 'shares_tag'
                    THEN group_concat(DISTINCT item_links.relation_value)
                    ELSE max(item_links.relation_value)
                END AS relation_value,
                max(item_links.score) AS score,
                items.item_id,
                items.source_key,
                items.source_type,
                items.external_id,
                items.item_type,
                items.title,
                items.body,
                items.created_at,
                items.updated_at,
                items.imported_at,
                items.checksum,
                items.location,
                items.parent_id,
                items.metadata_json
            FROM item_links
            JOIN items ON items.item_id = item_links.target_item_id
            WHERE item_links.source_item_id = ?
              AND coalesce(json_extract(items.metadata_json, '$.status'), 'active') != 'deleted'
        """
        parameters: List[object] = [item_id]
        if relation_type:
            sql += " AND item_links.relation_type = ?"
            parameters.append(relation_type)
        sql += """
            GROUP BY
                item_links.relation_type,
                items.item_id,
                items.source_key,
                items.source_type,
                items.external_id,
                items.item_type,
                items.title,
                items.body,
                items.created_at,
                items.updated_at,
                items.imported_at,
                items.checksum,
                items.location,
                items.parent_id,
                items.metadata_json
            ORDER BY
                score DESC,
                CASE WHEN items.created_at IS NULL THEN 1 ELSE 0 END,
                items.created_at DESC,
                items.id DESC
            LIMIT ?
        """
        parameters.append(limit)
        return self.connection.execute(sql, parameters).fetchall()

    def get_item_tags(self, item_id: str) -> List[str]:
        rows = self.connection.execute(
            """
            SELECT item_tags.tag
            FROM item_tags
            JOIN items ON items.id = item_tags.item_id
            WHERE items.item_id = ?
            ORDER BY item_tags.tag
            """,
            (item_id,),
        ).fetchall()
        return [row["tag"] for row in rows]

    def serialize_item(self, row: sqlite3.Row, include_body: bool = True) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "item_id": row["item_id"],
            "source_key": row["source_key"],
            "source_type": row["source_type"],
            "external_id": row["external_id"],
            "item_type": row["item_type"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "imported_at": row["imported_at"],
            "checksum": row["checksum"],
            "location": row["location"],
            "parent_id": row["parent_id"],
            "metadata": self._decode_metadata(row["metadata_json"]),
            "tags": self.get_item_tags(row["item_id"]),
        }
        if include_body:
            payload["body"] = row["body"]
        if "snippet" in row.keys():
            payload["snippet"] = row["snippet"]
        return payload

    def serialize_related_item(self, row: sqlite3.Row, include_body: bool = False) -> Dict[str, Any]:
        payload = self.serialize_item(row, include_body=include_body)
        payload["relation"] = {
            "type": row["relation_type"],
            "value": row["relation_value"],
            "score": row["score"],
        }
        return payload

    def start_sync_run(
        self,
        sync_type: str,
        *,
        source_key: Optional[str] = None,
        source_type: Optional[str] = None,
        location: Optional[str] = None,
        parent_run_id: Optional[int] = None,
    ) -> int:
        started_at = datetime.now(timezone.utc).isoformat()
        cursor = self.connection.execute(
            """
            INSERT INTO sync_runs (
                parent_run_id,
                sync_type,
                source_key,
                source_type,
                location,
                status,
                started_at
            ) VALUES (?, ?, ?, ?, ?, 'running', ?)
            """,
            (
                parent_run_id,
                sync_type,
                source_key,
                source_type,
                location,
                started_at,
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def finish_sync_run(
        self,
        run_id: int,
        *,
        status: str,
        stats: Optional[Dict[str, object]] = None,
        error_message: Optional[str] = None,
        warnings: Optional[List[str]] = None,
    ) -> None:
        self.connection.execute(
            """
            UPDATE sync_runs
            SET status = ?,
                finished_at = ?,
                error_message = ?,
                stats_json = ?,
                warnings_json = ?
            WHERE id = ?
            """,
            (
                status,
                datetime.now(timezone.utc).isoformat(),
                error_message,
                json.dumps(stats or {}, ensure_ascii=True, sort_keys=True),
                json.dumps(warnings or [], ensure_ascii=True),
                run_id,
            ),
        )
        self.connection.commit()

    def list_sync_runs(
        self,
        limit: int = 20,
        source_key: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[sqlite3.Row]:
        sql = """
            SELECT
                id,
                parent_run_id,
                sync_type,
                source_key,
                source_type,
                location,
                status,
                started_at,
                finished_at,
                error_message,
                stats_json,
                warnings_json
            FROM sync_runs
            WHERE 1 = 1
        """
        parameters: List[object] = []
        if source_key:
            sql += " AND source_key = ?"
            parameters.append(source_key)
        if status:
            sql += " AND status = ?"
            parameters.append(status)
        sql += """
            ORDER BY started_at DESC, id DESC
            LIMIT ?
        """
        parameters.append(limit)
        return self.connection.execute(sql, parameters).fetchall()

    def serialize_sync_run(self, row: sqlite3.Row) -> Dict[str, Any]:
        duration_seconds = None
        started_at = row["started_at"]
        finished_at = row["finished_at"]
        if started_at and finished_at:
            try:
                duration_seconds = round(
                    (
                        datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
                        - datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    ).total_seconds(),
                    3,
                )
            except ValueError:
                duration_seconds = None
        return {
            "id": row["id"],
            "parent_run_id": row["parent_run_id"],
            "sync_type": row["sync_type"],
            "source_key": row["source_key"],
            "source_type": row["source_type"],
            "location": row["location"],
            "status": row["status"],
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": duration_seconds,
            "error_message": row["error_message"],
            "stats": self._decode_raw_metadata(row["stats_json"]),
            "warnings": self._decode_string_list(row["warnings_json"]),
        }

    def list_source_health(self) -> List[sqlite3.Row]:
        return self.connection.execute(
            """
            WITH latest_source_runs AS (
                SELECT
                    sync_runs.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY sync_runs.source_key
                        ORDER BY sync_runs.started_at DESC, sync_runs.id DESC
                    ) AS row_number
                FROM sync_runs
                WHERE sync_runs.source_key IS NOT NULL
            ),
            latest_success_runs AS (
                SELECT
                    source_key,
                    MAX(finished_at) AS last_success_at
                FROM sync_runs
                WHERE source_key IS NOT NULL
                  AND status = 'success'
                GROUP BY source_key
            )
            SELECT
                sources.source_key,
                sources.source_type,
                sources.location,
                sources.last_synced_at,
                latest_source_runs.status AS last_run_status,
                latest_source_runs.started_at AS last_run_started_at,
                latest_source_runs.finished_at AS last_run_finished_at,
                latest_source_runs.error_message AS last_error_message,
                latest_source_runs.stats_json AS last_stats_json,
                latest_source_runs.warnings_json AS last_warnings_json,
                latest_success_runs.last_success_at
            FROM sources
            LEFT JOIN latest_source_runs
              ON latest_source_runs.source_key = sources.source_key
             AND latest_source_runs.row_number = 1
            LEFT JOIN latest_success_runs
              ON latest_success_runs.source_key = sources.source_key
            ORDER BY sources.source_type, sources.source_key
            """
        ).fetchall()

    def serialize_source_health(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "source_key": row["source_key"],
            "source_type": row["source_type"],
            "location": row["location"],
            "last_synced_at": row["last_synced_at"],
            "last_run_status": row["last_run_status"] or "never_run",
            "last_run_started_at": row["last_run_started_at"],
            "last_run_finished_at": row["last_run_finished_at"],
            "last_success_at": row["last_success_at"],
            "last_error_message": row["last_error_message"],
            "last_stats": self._decode_raw_metadata(row["last_stats_json"]),
            "last_warnings": self._decode_string_list(row["last_warnings_json"]),
        }

    def get_entity_content(self, entity_type: str, entity_key: str) -> Optional[sqlite3.Row]:
        if entity_type == "document":
            return self.connection.execute(
                """
                SELECT
                    title,
                    created_at,
                    content
                FROM documents
                WHERE source_id = ?
                """,
                (entity_key,),
            ).fetchone()
        if entity_type == "conversation":
            return self.connection.execute(
                """
                SELECT
                    title,
                    created_at,
                    title || char(10) || cwd AS content
                FROM conversations
                WHERE thread_id = ?
                """,
                (entity_key,),
            ).fetchone()
        if entity_type == "message":
            thread_id, _, index_text = entity_key.rpartition(":")
            try:
                message_index = int(index_text)
            except ValueError:
                return None
            return self.connection.execute(
                """
                SELECT
                    role || COALESCE(' ' || phase, '') AS title,
                    created_at,
                    content
                FROM messages
                WHERE thread_id = ? AND message_index = ?
                """,
                (thread_id, message_index),
            ).fetchone()
        return None

    def get_entity_details(self, entity_type: str, entity_key: str) -> Optional[sqlite3.Row]:
        if entity_type == "document":
            return self.connection.execute(
                """
                SELECT
                    title,
                    created_at,
                    content,
                    source_path AS location
                FROM documents
                WHERE source_id = ?
                """,
                (entity_key,),
            ).fetchone()
        if entity_type == "conversation":
            return self.connection.execute(
                """
                SELECT
                    title,
                    created_at,
                    title || char(10) || cwd AS content,
                    rollout_path AS location
                FROM conversations
                WHERE thread_id = ?
                """,
                (entity_key,),
            ).fetchone()
        if entity_type == "message":
            thread_id, _, index_text = entity_key.rpartition(":")
            try:
                message_index = int(index_text)
            except ValueError:
                return None
            return self.connection.execute(
                """
                SELECT
                    role || COALESCE(' ' || phase, '') AS title,
                    messages.created_at AS created_at,
                    messages.content AS content,
                    conversations.rollout_path AS location
                FROM messages
                JOIN conversations ON conversations.thread_id = messages.thread_id
                WHERE messages.thread_id = ? AND messages.message_index = ?
                """,
                (thread_id, message_index),
            ).fetchone()
        return None

    def rebuild_unified_records(
        self,
        documents: Iterable[DocumentRecord],
        tags_by_source_id: Dict[str, List[str]],
        conversations: Iterable[ConversationRecord],
        messages: Iterable[MessageRecord],
    ) -> int:
        return self.rebuild_memory_items(
            documents=documents,
            tags_by_source_id=tags_by_source_id,
            conversations=conversations,
            messages=messages,
        )

    def rebuild_memory_items(
        self,
        documents: Iterable[DocumentRecord],
        tags_by_source_id: Dict[str, List[str]],
        conversations: Iterable[ConversationRecord],
        messages: Iterable[MessageRecord],
    ) -> int:
        document_rows = list(documents)
        conversation_rows = list(conversations)
        message_rows = list(messages)

        memory_items = self._build_memory_items(
            document_rows, tags_by_source_id, conversation_rows, message_rows
        )
        return self.replace_memory_items(memory_items)

    def replace_memory_items(
        self,
        memory_items: Iterable[MemoryItem],
        source_keys: Optional[Iterable[str]] = None,
    ) -> int:
        item_rows = list(memory_items)
        resolved_source_keys = sorted(set(source_keys or {item.source_key for item in item_rows}))
        if resolved_source_keys:
            active_item_ids_by_source: Dict[str, List[str]] = {}
            for item in item_rows:
                active_item_ids_by_source.setdefault(item.source_key, []).append(item.item_id)
            self._mark_missing_memory_items_deleted(
                resolved_source_keys,
                active_item_ids_by_source,
            )
        else:
            self.connection.execute("DELETE FROM search_index WHERE entity_type = 'item'")
            self.connection.execute("DELETE FROM item_tags")
            self.connection.execute("DELETE FROM items")
            self.connection.execute("DELETE FROM record_tags")
            self.connection.execute("DELETE FROM records")

        total = 0
        for item in item_rows:
            total += self._insert_item(item)
            total += self._insert_record(
                UnifiedRecord(
                    record_key=item.item_id,
                    record_type=item.item_type,
                    source_type=item.source_type,
                    title=item.title,
                    body=item.body,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                    location=item.location,
                    parent_key=item.parent_id,
                    tags=item.tags,
                )
            )

        self.rebuild_item_links()
        self.connection.commit()
        return total

    def purge_memory_items_for_source(self, source_key: str) -> None:
        rows = self.connection.execute(
            """
            SELECT id, item_id
            FROM items
            WHERE source_key = ?
            """,
            (source_key,),
        ).fetchall()
        if not rows:
            return

        item_row_ids = [row["id"] for row in rows]
        item_ids = [row["item_id"] for row in rows]
        row_placeholders = ", ".join("?" for _ in item_row_ids)
        key_placeholders = ", ".join("?" for _ in item_ids)

        self.connection.execute(
            f"DELETE FROM item_tags WHERE item_id IN ({row_placeholders})",
            item_row_ids,
        )
        self.connection.execute(
            f"""
            DELETE FROM search_index
            WHERE entity_type = 'item'
              AND entity_key IN ({key_placeholders})
            """,
            item_ids,
        )
        self.connection.execute(
            f"DELETE FROM record_tags WHERE record_id IN (SELECT id FROM records WHERE record_key IN ({key_placeholders}))",
            item_ids,
        )
        self.connection.execute(
            f"DELETE FROM records WHERE record_key IN ({key_placeholders})",
            item_ids,
        )
        self.connection.execute(
            f"DELETE FROM items WHERE id IN ({row_placeholders})",
            item_row_ids,
        )
        self.connection.commit()

    def create_capture_item(
        self,
        body: str,
        title: Optional[str] = None,
        created_at: Optional[str] = None,
        device: Optional[str] = None,
        input_type: Optional[str] = None,
        source_label: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> MemoryItem:
        normalized_body = body.strip()
        if not normalized_body:
            raise ValueError("Capture body must not be empty")

        timestamp = created_at or datetime.now(timezone.utc).isoformat()
        external_id = self._build_item_id("capture")
        item_id = f"capture:{external_id}"
        normalized_tags = self._normalize_tags(tags)
        resolved_title = self._build_capture_title(title, normalized_body)
        metadata = {
            "capture_kind": "mobile",
            "device": device,
            "input_type": input_type or "text",
            "source_label": source_label or "mobile_capture_api",
        }
        item = MemoryItem(
            item_id=item_id,
            source_key="mobile_capture",
            source_type="capture",
            external_id=external_id,
            item_type="capture",
            title=resolved_title,
            body=normalized_body,
            created_at=timestamp,
            updated_at=timestamp,
            imported_at=None,
            checksum=self._build_checksum(item_id, resolved_title, normalized_body, timestamp),
            location=f"api:/captures/{external_id}",
            parent_id=None,
            metadata={key: value for key, value in metadata.items() if value},
            tags=normalized_tags,
        )
        self.upsert_source("mobile_capture", "capture", "api:/captures")
        self._insert_item(item)
        self._insert_record(
            UnifiedRecord(
                record_key=item.item_id,
                record_type=item.item_type,
                source_type=item.source_type,
                title=item.title,
                body=item.body,
                created_at=item.created_at,
                updated_at=item.updated_at,
                location=item.location,
                parent_key=item.parent_id,
                tags=item.tags,
            )
        )
        self.rebuild_item_links()
        self.connection.commit()
        return item

    def timeline(
        self,
        limit: int = 20,
        source_type: Optional[str] = None,
        record_type: Optional[str] = None,
        tag: Optional[str] = None,
        status: Optional[str] = None,
        domain: Optional[str] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
    ) -> List[sqlite3.Row]:
        sql = """
            SELECT
                item_id AS record_key,
                item_type AS record_type,
                source_type,
                title,
                created_at,
                location,
                substr(body, 1, 220) AS preview
            FROM items
        """
        parameters: List[object] = []
        if tag:
            sql += """
                JOIN item_tags ON item_tags.item_id = items.id
            """
        sql += " WHERE 1 = 1"
        if status is None:
            sql += " AND coalesce(json_extract(metadata_json, '$.status'), 'active') != 'deleted'"
        if source_type:
            sql += " AND source_type = ?"
            parameters.append(source_type)
        if record_type:
            sql += " AND item_type = ?"
            parameters.append(record_type)
        if tag:
            sql += " AND item_tags.tag = ?"
            parameters.append(tag)
        if status:
            sql += " AND json_extract(metadata_json, '$.status') = ?"
            parameters.append(status)
        if domain:
            sql += " AND lower(json_extract(metadata_json, '$.domain')) = lower(?)"
            parameters.append(domain)
        if created_after:
            sql += " AND created_at >= ?"
            parameters.append(created_after)
        if created_before:
            sql += " AND created_at <= ?"
            parameters.append(created_before)
        sql += """
            ORDER BY
                CASE WHEN created_at IS NULL THEN 1 ELSE 0 END,
                created_at DESC,
                id DESC
            LIMIT ?
        """
        parameters.append(limit)
        return self.connection.execute(sql, parameters).fetchall()

    def get_record(self, record_key: str) -> Optional[sqlite3.Row]:
        row = self.connection.execute(
            """
            SELECT
                item_id AS record_key,
                item_type AS record_type,
                source_type,
                title,
                body,
                created_at,
                updated_at,
                location,
                parent_id AS parent_key,
                source_key,
                external_id,
                imported_at,
                checksum,
                metadata_json
            FROM items
            WHERE item_id = ?
            """,
            (record_key,),
        ).fetchone()
        if row:
            return row
        return self.connection.execute(
            """
            SELECT
                record_key,
                record_type,
                source_type,
                title,
                body,
                created_at,
                updated_at,
                location,
                parent_key,
                NULL AS source_key,
                NULL AS external_id,
                NULL AS imported_at,
                NULL AS checksum,
                '{}' AS metadata_json
            FROM records
            WHERE record_key = ?
            """,
            (record_key,),
        ).fetchone()

    def _build_memory_items(
        self,
        documents: List[DocumentRecord],
        tags_by_source_id: Dict[str, List[str]],
        conversations: List[ConversationRecord],
        messages: List[MessageRecord],
    ) -> List[MemoryItem]:
        items: List[MemoryItem] = []

        for document in documents:
            items.append(
                MemoryItem(
                    item_id=document.source_id,
                    source_key="blog_repo",
                    source_type="blog",
                    external_id=document.source_id,
                    item_type=document.doc_type,
                    title=document.title,
                    body=document.content,
                    created_at=document.created_at,
                    updated_at=document.updated_at,
                    imported_at=None,
                    checksum=self._build_checksum(
                        document.source_id,
                        document.title,
                        document.content,
                        document.updated_at,
                    ),
                    location=document.source_path,
                    parent_id=None,
                    metadata={
                        "slug": document.slug,
                        "summary": document.summary,
                        "doc_type": document.doc_type,
                    },
                    tags=tags_by_source_id.get(document.source_id, []),
                )
            )

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
                    checksum=self._build_checksum(
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
                    checksum=self._build_checksum(
                        item_id,
                        role_title,
                        message.content,
                        message.created_at,
                    ),
                    location=self._conversation_location(message.thread_id),
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

    def _insert_record(self, record: UnifiedRecord) -> int:
        self.connection.execute(
            """
            INSERT INTO records (
                record_key, record_type, source_type, title, body, created_at,
                updated_at, location, parent_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(record_key) DO UPDATE SET
                record_type = excluded.record_type,
                source_type = excluded.source_type,
                title = excluded.title,
                body = excluded.body,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at,
                location = excluded.location,
                parent_key = excluded.parent_key
            """,
            (
                record.record_key,
                record.record_type,
                record.source_type,
                record.title,
                record.body,
                record.created_at,
                record.updated_at,
                record.location,
                record.parent_key,
            ),
        )
        record_row = self.connection.execute(
            "SELECT id FROM records WHERE record_key = ?",
            (record.record_key,),
        ).fetchone()
        if not record_row:
            return 0
        record_id = record_row["id"]
        self.connection.execute("DELETE FROM record_tags WHERE record_id = ?", (record_id,))
        for tag in record.tags:
            self.connection.execute(
                "INSERT OR IGNORE INTO record_tags (record_id, tag) VALUES (?, ?)",
                (record_id, tag),
            )
        return 1

    def _insert_item(self, item: MemoryItem) -> int:
        normalized_metadata = self._normalize_item_metadata(item.metadata)
        self.connection.execute(
            """
            INSERT INTO items (
                item_id, source_key, source_type, external_id, item_type, title, body,
                created_at, updated_at, imported_at, checksum, location, parent_id,
                metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, ?, ?)
            ON CONFLICT(item_id) DO UPDATE SET
                source_key = excluded.source_key,
                source_type = excluded.source_type,
                external_id = excluded.external_id,
                item_type = excluded.item_type,
                title = excluded.title,
                body = excluded.body,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at,
                imported_at = datetime('now'),
                checksum = excluded.checksum,
                location = excluded.location,
                parent_id = excluded.parent_id,
                metadata_json = excluded.metadata_json
            """,
            (
                item.item_id,
                item.source_key,
                item.source_type,
                item.external_id,
                item.item_type,
                item.title,
                item.body,
                item.created_at,
                item.updated_at,
                item.checksum,
                item.location,
                item.parent_id,
                json.dumps(normalized_metadata, ensure_ascii=True, sort_keys=True),
            ),
        )
        item_row = self.connection.execute(
            "SELECT id FROM items WHERE item_id = ?",
            (item.item_id,),
        ).fetchone()
        if not item_row:
            return 0
        item_row_id = item_row["id"]
        self.connection.execute("DELETE FROM item_tags WHERE item_id = ?", (item_row_id,))
        for tag in item.tags:
            self.connection.execute(
                "INSERT OR IGNORE INTO item_tags (item_id, tag) VALUES (?, ?)",
                (item_row_id, tag),
            )
        self.connection.execute(
            """
            DELETE FROM search_index
            WHERE entity_type = 'item' AND entity_key = ?
            """,
            (item.item_id,),
        )
        self.connection.execute(
            """
            INSERT INTO search_index (entity_type, entity_key, title, body)
            VALUES (?, ?, ?, ?)
            """,
            ("item", item.item_id, item.title, item.body),
        )
        return 0

    def rebuild_item_links(self) -> int:
        self.connection.execute("DELETE FROM item_links")
        links = self._build_parent_child_links()
        links.extend(self._build_shared_tag_links())
        for link in links:
            self._insert_item_link(link)
        return len(links)

    def _mark_missing_memory_items_deleted(
        self,
        source_keys: List[str],
        active_item_ids_by_source: Dict[str, List[str]],
    ) -> None:
        for source_key in source_keys:
            active_item_ids = sorted(set(active_item_ids_by_source.get(source_key, [])))
            if active_item_ids:
                placeholders = ", ".join("?" for _ in active_item_ids)
                rows = self.connection.execute(
                    f"""
                    SELECT item_id, metadata_json
                    FROM items
                    WHERE source_key = ?
                      AND item_id NOT IN ({placeholders})
                    """,
                    [source_key, *active_item_ids],
                ).fetchall()
            else:
                rows = self.connection.execute(
                    """
                    SELECT item_id, metadata_json
                    FROM items
                    WHERE source_key = ?
                    """,
                    (source_key,),
                ).fetchall()

            for row in rows:
                metadata = self._decode_metadata(row["metadata_json"])
                if metadata.get("status") == "deleted":
                    continue
                deleted_at = datetime.now(timezone.utc).isoformat()
                updated_metadata = {
                    **metadata,
                    "status": "deleted",
                    "deleted_at": deleted_at,
                }
                self.connection.execute(
                    """
                    UPDATE items
                    SET updated_at = ?,
                        imported_at = datetime('now'),
                        metadata_json = ?
                    WHERE item_id = ?
                    """,
                    (
                        deleted_at,
                        json.dumps(updated_metadata, ensure_ascii=True, sort_keys=True),
                        row["item_id"],
                    ),
                )

    def _conversation_location(self, thread_id: str) -> Optional[str]:
        row = self.connection.execute(
            "SELECT rollout_path FROM conversations WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
        if row:
            return row["rollout_path"]
        return None

    def _build_parent_child_links(self) -> List[ItemLink]:
        rows = self.connection.execute(
            """
            SELECT child.item_id AS child_item_id, child.parent_id AS parent_item_id
            FROM items AS child
            JOIN items AS parent ON parent.item_id = child.parent_id
            WHERE child.parent_id IS NOT NULL
              AND coalesce(json_extract(child.metadata_json, '$.status'), 'active') != 'deleted'
              AND coalesce(json_extract(parent.metadata_json, '$.status'), 'active') != 'deleted'
            """
        ).fetchall()
        links: List[ItemLink] = []
        for row in rows:
            parent_item_id = row["parent_item_id"]
            child_item_id = row["child_item_id"]
            links.append(
                ItemLink(
                    source_item_id=parent_item_id,
                    target_item_id=child_item_id,
                    relation_type="has_part",
                    relation_value=None,
                    score=1.0,
                    metadata={},
                )
            )
            links.append(
                ItemLink(
                    source_item_id=child_item_id,
                    target_item_id=parent_item_id,
                    relation_type="part_of",
                    relation_value=None,
                    score=1.0,
                    metadata={},
                )
            )
        return links

    def _build_shared_tag_links(self) -> List[ItemLink]:
        generic_tags = {
            "active",
            "android",
            "assistant",
            "blog",
            "bookmark",
            "capture",
            "cloud",
            "codex",
            "commentary",
            "conversation",
            "final_answer",
            "gemini",
            "generated_image",
            "has_attachment",
            "has_canvas",
            "journal",
            "message",
            "mobile",
            "quick_capture",
            "session",
            "takeout_html",
            "user",
            "voice",
        }
        placeholders = ", ".join("?" for _ in generic_tags)
        rows = self.connection.execute(
            f"""
            WITH eligible_tags AS (
                SELECT item_tags.tag
                FROM item_tags
                JOIN items ON items.id = item_tags.item_id
                WHERE item_tags.tag NOT IN ({placeholders})
                  AND length(item_tags.tag) >= 2
                  AND coalesce(json_extract(items.metadata_json, '$.status'), 'active') != 'deleted'
                GROUP BY item_tags.tag
                HAVING COUNT(DISTINCT items.item_id) BETWEEN 2 AND 12
            )
            SELECT
                source_items.item_id AS source_item_id,
                target_items.item_id AS target_item_id,
                source_items.source_type AS source_source_type,
                target_items.source_type AS target_source_type,
                source_items.item_type AS source_item_type,
                target_items.item_type AS target_item_type,
                source_tags.tag AS shared_tag
            FROM item_tags AS source_tags
            JOIN item_tags AS target_tags
              ON target_tags.tag = source_tags.tag
             AND target_tags.item_id > source_tags.item_id
            JOIN items AS source_items ON source_items.id = source_tags.item_id
            JOIN items AS target_items ON target_items.id = target_tags.item_id
            JOIN eligible_tags ON eligible_tags.tag = source_tags.tag
            WHERE coalesce(json_extract(source_items.metadata_json, '$.status'), 'active') != 'deleted'
              AND coalesce(json_extract(target_items.metadata_json, '$.status'), 'active') != 'deleted'
            ORDER BY source_tags.tag, source_items.created_at DESC, target_items.created_at DESC
            """,
            sorted(generic_tags),
        ).fetchall()
        links: List[ItemLink] = []
        for row in rows:
            if row["source_source_type"] == row["target_source_type"]:
                continue
            shared_tag = row["shared_tag"]
            for source_item_id, target_item_id in (
                (row["source_item_id"], row["target_item_id"]),
                (row["target_item_id"], row["source_item_id"]),
            ):
                links.append(
                    ItemLink(
                        source_item_id=source_item_id,
                        target_item_id=target_item_id,
                        relation_type="shares_tag",
                        relation_value=shared_tag,
                        score=0.35,
                        metadata={"tag": shared_tag},
                    )
                )
        return links

    def _insert_item_link(self, link: ItemLink) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO item_links (
                source_item_id,
                target_item_id,
                relation_type,
                relation_value,
                score,
                metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                link.source_item_id,
                link.target_item_id,
                link.relation_type,
                link.relation_value,
                link.score,
                json.dumps(link.metadata, ensure_ascii=True, sort_keys=True),
            ),
        )

    def _build_checksum(self, *parts: Optional[str]) -> str:
        import hashlib

        normalized = "||".join("" if part is None else str(part) for part in parts)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _build_capture_title(self, title: Optional[str], body: str) -> str:
        if title and title.strip():
            return title.strip()[:120]
        first_line = next((line.strip() for line in body.splitlines() if line.strip()), body)
        if len(first_line) <= 80:
            return first_line
        return f"{first_line[:77].rstrip()}..."

    def _build_item_id(self, prefix: str) -> str:
        import uuid

        return f"{prefix}_{uuid.uuid4().hex}"

    def _normalize_tags(self, tags: Optional[Iterable[str]]) -> List[str]:
        if not tags:
            return ["capture", "mobile"]
        normalized: List[str] = []
        seen = set()
        for tag in tags:
            cleaned = str(tag).strip().lower()
            if not cleaned or cleaned in seen:
                continue
            normalized.append(cleaned)
            seen.add(cleaned)
        if "capture" not in seen:
            normalized.insert(0, "capture")
        if "mobile" not in set(normalized):
            normalized.append("mobile")
        return normalized

    def _normalize_item_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        core_keys = {"metadata_schema_version", "status", "deleted_at", "domain", "source_details"}
        normalized: Dict[str, Any] = {
            "metadata_schema_version": 1,
            "status": str(metadata.get("status") or "active"),
            "deleted_at": metadata.get("deleted_at"),
            "domain": metadata.get("domain"),
        }
        source_details = metadata.get("source_details")
        if not isinstance(source_details, dict):
            source_details = {}
        merged_source_details = dict(source_details)
        for key, value in metadata.items():
            if key in core_keys:
                continue
            merged_source_details[key] = value
        normalized["source_details"] = {
            key: value
            for key, value in merged_source_details.items()
            if value is not None
        }
        return normalized

    def _decode_metadata(self, metadata_json: Optional[str]) -> Dict[str, Any]:
        return self._normalize_item_metadata(self._decode_raw_metadata(metadata_json))

    def _decode_raw_metadata(self, metadata_json: Optional[str]) -> Dict[str, Any]:
        if not metadata_json:
            return {}
        try:
            value = json.loads(metadata_json)
        except json.JSONDecodeError:
            return {}
        if isinstance(value, dict):
            return value
        return {}

    def _decode_string_list(self, payload_json: Optional[str]) -> List[str]:
        if not payload_json:
            return []
        try:
            value = json.loads(payload_json)
        except json.JSONDecodeError:
            return []
        if not isinstance(value, list):
            return []
        return [str(entry) for entry in value if str(entry).strip()]

    def _extract_domain(self, url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        parsed = urlparse(url)
        domain = parsed.netloc.strip().lower()
        return domain or None
