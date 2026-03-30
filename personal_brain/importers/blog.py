from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..models import DocumentRecord


def import_blog(
    blog_repo_path: Path, blog_glob: str
) -> Tuple[List[DocumentRecord], Dict[str, List[str]]]:
    documents: List[DocumentRecord] = []
    tags_by_source_id: Dict[str, List[str]] = {}

    for file_path in sorted(blog_repo_path.glob(blog_glob)):
        text = file_path.read_text(encoding="utf-8")
        frontmatter, content = split_frontmatter(text)
        metadata = parse_frontmatter(frontmatter)

        source_id = f"blog:{file_path.relative_to(blog_repo_path)}"
        title = as_optional_text(metadata.get("title")) or file_path.stem
        tags = [str(tag) for tag in metadata.get("tags", []) if str(tag).strip()]
        doc_type = "diary" if metadata.get("isDiary") else "blog"
        created_at = normalize_datetime(metadata.get("pubDatetime"))
        updated_at = normalize_datetime(metadata.get("modDatetime"))

        documents.append(
            DocumentRecord(
                source_id=source_id,
                doc_type=doc_type,
                title=title,
                slug=as_optional_text(metadata.get("slug")),
                summary=as_optional_text(metadata.get("description")),
                content=content.strip(),
                source_path=str(file_path),
                created_at=created_at,
                updated_at=updated_at,
            )
        )
        tags_by_source_id[source_id] = tags

    return documents, tags_by_source_id


def split_frontmatter(text: str) -> Tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return "", text
    return parts[0][4:], parts[1]


def parse_frontmatter(frontmatter: str) -> Dict[str, object]:
    result: Dict[str, object] = {}
    current_list_key: Optional[str] = None

    for raw_line in frontmatter.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and current_list_key:
            items = result.setdefault(current_list_key, [])
            if isinstance(items, list):
                items.append(clean_value(stripped[2:]))
            continue
        if ":" not in line:
            current_list_key = None
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            result[key] = []
            current_list_key = key
            continue
        current_list_key = None
        result[key] = clean_value(value)

    return result


def clean_value(value: str) -> object:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value == "true":
        return True
    if value == "false":
        return False
    return value


def as_optional_text(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        return None if not value else "\n".join(str(item) for item in value)
    text = str(value).strip()
    return text or None


def normalize_datetime(value: object) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    cleaned = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned).isoformat()
    except ValueError:
        return value
