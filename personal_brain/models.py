from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


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
