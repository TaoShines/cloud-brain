from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .models import ConversationRecord, DocumentRecord, MessageRecord, UnifiedRecord


SCHEMA = """
PRAGMA foreign_keys = ON;

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

CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    entity_type,
    entity_key,
    title,
    body,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(db_path)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def init(self) -> None:
        self.connection.executescript(SCHEMA)
        self.connection.commit()

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
                (SELECT COUNT(*) FROM documents) AS document_count,
                (SELECT COUNT(*) FROM document_tags) AS document_tag_count,
                (SELECT COUNT(*) FROM conversations) AS conversation_count,
                (SELECT COUNT(*) FROM messages) AS message_count,
                (SELECT COUNT(*) FROM search_index) AS search_index_count
            """
        ).fetchone()

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
        document_rows = list(documents)
        conversation_rows = list(conversations)
        message_rows = list(messages)

        self.connection.execute("DELETE FROM record_tags")
        self.connection.execute("DELETE FROM records")

        total = 0
        for document in document_rows:
            total += self._insert_record(
                UnifiedRecord(
                    record_key=document.source_id,
                    record_type=document.doc_type,
                    source_type="blog",
                    title=document.title,
                    body=document.content,
                    created_at=document.created_at,
                    updated_at=document.updated_at,
                    location=document.source_path,
                    parent_key=None,
                    tags=tags_by_source_id.get(document.source_id, []),
                )
            )

        for conversation in conversation_rows:
            total += self._insert_record(
                UnifiedRecord(
                    record_key=conversation.thread_id,
                    record_type="conversation",
                    source_type="codex",
                    title=conversation.title,
                    body=conversation.title,
                    created_at=conversation.created_at,
                    updated_at=conversation.updated_at,
                    location=conversation.rollout_path,
                    parent_key=None,
                    tags=["codex", "conversation"],
                )
            )

        for message in message_rows:
            role_title = message.role if not message.phase else f"{message.role} {message.phase}"
            total += self._insert_record(
                UnifiedRecord(
                    record_key=f"{message.thread_id}:{message.message_index}",
                    record_type="message",
                    source_type="codex",
                    title=role_title,
                    body=message.content,
                    created_at=message.created_at,
                    updated_at=message.created_at,
                    location=self._conversation_location(message.thread_id),
                    parent_key=message.thread_id,
                    tags=["codex", message.role] + ([message.phase] if message.phase else []),
                )
            )

        self.connection.commit()
        return total

    def timeline(
        self,
        limit: int = 20,
        source_type: Optional[str] = None,
        record_type: Optional[str] = None,
    ) -> List[sqlite3.Row]:
        sql = """
            SELECT
                record_key,
                record_type,
                source_type,
                title,
                created_at,
                location,
                substr(body, 1, 220) AS preview
            FROM records
            WHERE 1 = 1
        """
        parameters: List[object] = []
        if source_type:
            sql += " AND source_type = ?"
            parameters.append(source_type)
        if record_type:
            sql += " AND record_type = ?"
            parameters.append(record_type)
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
                parent_key
            FROM records
            WHERE record_key = ?
            """,
            (record_key,),
        ).fetchone()

    def _insert_record(self, record: UnifiedRecord) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO records (
                record_key, record_type, source_type, title, body, created_at,
                updated_at, location, parent_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        record_id = cursor.lastrowid
        for tag in record.tags:
            self.connection.execute(
                "INSERT OR IGNORE INTO record_tags (record_id, tag) VALUES (?, ?)",
                (record_id, tag),
            )
        return 1

    def _conversation_location(self, thread_id: str) -> Optional[str]:
        row = self.connection.execute(
            "SELECT rollout_path FROM conversations WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
        if row:
            return row["rollout_path"]
        return None
