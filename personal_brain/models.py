from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class DocumentRecord:
    source_id: str
    doc_type: str
    title: str
    slug: Optional[str]
    summary: Optional[str]
    content: str
    source_path: str
    created_at: Optional[str]
    updated_at: Optional[str]


@dataclass
class ConversationRecord:
    thread_id: str
    title: str
    cwd: str
    source: str
    model: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    rollout_path: str


@dataclass
class MessageRecord:
    thread_id: str
    message_index: int
    role: str
    phase: Optional[str]
    content: str
    created_at: Optional[str]


@dataclass
class BookmarkRecord:
    bookmark_id: str
    title: str
    url: str
    folder_path: str
    added_at: Optional[str]
    source_path: str
    status: str = "active"
    deleted_at: Optional[str] = None


@dataclass
class UnifiedRecord:
    record_key: str
    record_type: str
    source_type: str
    title: str
    body: str
    created_at: Optional[str]
    updated_at: Optional[str]
    location: Optional[str]
    parent_key: Optional[str]
    tags: List[str]


@dataclass
class MemoryItem:
    item_id: str
    source_key: str
    source_type: str
    external_id: str
    item_type: str
    title: str
    body: str
    created_at: Optional[str]
    updated_at: Optional[str]
    imported_at: Optional[str]
    checksum: str
    location: Optional[str]
    parent_id: Optional[str]
    metadata: Dict[str, object]
    tags: List[str]


@dataclass
class ItemLink:
    source_item_id: str
    target_item_id: str
    relation_type: str
    relation_value: Optional[str]
    score: float
    metadata: Dict[str, object]


@dataclass
class ImporterPayload:
    source_key: str
    source_type: str
    location: str
    memory_items: List[MemoryItem]
    documents: List[DocumentRecord]
    conversations: List[ConversationRecord]
    messages: List[MessageRecord]
    bookmarks: List[BookmarkRecord]
    tags_by_source_id: Dict[str, List[str]]
