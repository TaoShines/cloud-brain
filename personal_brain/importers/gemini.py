from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional

from ..models import ImporterPayload, MemoryItem

SUPPORTED_SUFFIXES = {".txt", ".md", ".html", ".htm"}


def import_gemini_source(export_path: Path) -> ImporterPayload:
    files = list_gemini_export_files(export_path)
    memory_items = build_gemini_memory_items(export_path, files)
    return ImporterPayload(
        source_key="gemini_exports",
        source_type="gemini",
        location=str(export_path),
        memory_items=memory_items,
        documents=[],
        conversations=[],
        messages=[],
        bookmarks=[],
        tags_by_source_id={},
    )


def list_gemini_export_files(export_path: Path) -> List[Path]:
    if not export_path.exists():
        return []
    return sorted(
        path
        for path in export_path.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def build_gemini_memory_items(export_root: Path, files: List[Path]) -> List[MemoryItem]:
    items: List[MemoryItem] = []
    for file_path in files:
        raw_text = read_export_text(file_path)
        content = normalize_content(raw_text)
        if not content:
            continue
        relative_path = file_path.relative_to(export_root)
        item_id = f"gemini:{relative_path.as_posix()}"
        title = build_title(file_path, content)
        created_at = normalize_timestamp(file_path.stat().st_mtime)
        tags = ["gemini", "conversation", file_path.suffix.lower().lstrip(".")]
        items.append(
            MemoryItem(
                item_id=item_id,
                source_key="gemini_exports",
                source_type="gemini",
                external_id=item_id,
                item_type="conversation",
                title=title,
                body=content,
                created_at=created_at,
                updated_at=created_at,
                imported_at=None,
                checksum=build_checksum(item_id, title, content, created_at),
                location=str(file_path),
                parent_id=None,
                metadata={
                    "export_format": file_path.suffix.lower().lstrip("."),
                    "source_path": str(file_path),
                    "relative_path": relative_path.as_posix(),
                    "source": "google_docs_export",
                },
                tags=tags,
            )
        )
    return items


def read_export_text(file_path: Path) -> str:
    text = file_path.read_text(encoding="utf-8")
    if file_path.suffix.lower() in {".html", ".htm"}:
        parser = _HTMLTextExtractor()
        parser.feed(text)
        return parser.get_text()
    return text


def normalize_content(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    cleaned: List[str] = []
    previous_blank = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if previous_blank:
                continue
            cleaned.append("")
            previous_blank = True
            continue
        cleaned.append(stripped)
        previous_blank = False
    return "\n".join(cleaned).strip()


def build_title(file_path: Path, content: str) -> str:
    first_line = next((line.strip() for line in content.splitlines() if line.strip()), "")
    if first_line:
        return first_line[:120]
    return file_path.stem[:120]


def normalize_timestamp(timestamp: float) -> Optional[str]:
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def build_checksum(*parts: Optional[str]) -> str:
    normalized = "||".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        if tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if data:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self._chunks.append("\n")

    def get_text(self) -> str:
        return "".join(self._chunks)
