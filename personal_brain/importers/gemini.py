from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from ..models import ImporterPayload, MemoryItem

SUPPORTED_SUFFIXES = {".txt", ".md", ".html", ".htm"}
ACTIVITY_HTML_NAMES = {"我的活动记录.html", "My Activity.html"}
BERLIN_TZ = ZoneInfo("Europe/Berlin")
UTC_TZ = ZoneInfo("UTC")
SESSION_GAP_MINUTES = 30


@dataclass
class GeminiActivity:
    activity_index: int
    title: str
    prompt_text: str
    response_text: str
    created_at: Optional[str]
    timestamp_text: str
    event_type: str
    attachment_names: List[str]
    attachment_paths: List[str]
    generated_image_count: int
    image_sources: List[str]
    link_targets: List[str]
    source_path: str
    relative_path: str


def import_gemini_source(export_path: Path) -> ImporterPayload:
    memory_items = build_gemini_memory_items(export_path)
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


def build_gemini_memory_items(export_root: Path) -> List[MemoryItem]:
    activity_html = find_activity_html(export_root)
    if activity_html:
        return parse_activity_html(export_root, activity_html)

    files = list_gemini_export_files(export_root)
    return build_fallback_memory_items(export_root, files)


def find_activity_html(export_root: Path) -> Optional[Path]:
    for path in sorted(export_root.rglob("*.html")):
        if path.name in ACTIVITY_HTML_NAMES:
            return path
    return None


def parse_activity_html(export_root: Path, activity_html: Path) -> List[MemoryItem]:
    html = activity_html.read_text(encoding="utf-8")
    parts = html.split('<div class="outer-cell ')
    activities: List[GeminiActivity] = []

    for index, chunk in enumerate(parts[1:]):
        block_html = '<div class="outer-cell ' + chunk
        activity = parse_activity_block(export_root, activity_html, block_html, index)
        if activity:
            activities.append(activity)

    return build_session_memory_items(activities)


def parse_activity_block(
    export_root: Path, activity_html: Path, block_html: str, index: int
) -> Optional[GeminiActivity]:
    content_html = extract_primary_content_html(block_html)
    if not content_html:
        return None

    parsed = _ActivityContentParser()
    parsed.feed(content_html)
    parsed.close()

    text = normalize_content(parsed.get_text())
    if not text:
        return None

    lines = text.splitlines()
    timestamp_index = find_timestamp_index(lines)
    if timestamp_index is None:
        return None

    timestamp_text = lines[timestamp_index].strip()
    created_at = normalize_activity_timestamp(timestamp_text)
    prefix_lines = [line.strip() for line in lines[:timestamp_index] if line.strip()]
    suffix_lines = [line.strip() for line in lines[timestamp_index + 1 :] if line.strip()]

    attachment_names = extract_attachment_names(parsed.link_targets, activity_html.parent)
    attachment_paths = [
        str((activity_html.parent / name).resolve())
        for name in attachment_names
        if (activity_html.parent / name).exists()
    ]
    generated_image_count = extract_generated_image_count(prefix_lines)

    event_type = "prompt"
    prompt_text = ""
    if prefix_lines and prefix_lines[0].startswith("Prompted"):
        event_type = "prompt"
        prompt_text = extract_prompt_text(prefix_lines)
    elif prefix_lines and prefix_lines[0].startswith("Created Gemini Canvas titled"):
        event_type = "canvas"
        prompt_text = prefix_lines[0]
    else:
        event_type = "activity"
        prompt_text = "\n".join(
            line
            for line in prefix_lines
            if not is_attachment_line(line) and not is_generated_image_line(line)
        ).strip()

    response_text = "\n".join(suffix_lines).strip()
    if not prompt_text and not response_text and not attachment_names and not generated_image_count:
        return None

    title = build_activity_title(prompt_text, response_text, event_type)
    relative_path = activity_html.relative_to(export_root).as_posix()
    return GeminiActivity(
        activity_index=index,
        title=title,
        prompt_text=prompt_text,
        response_text=response_text,
        created_at=created_at,
        timestamp_text=timestamp_text,
        event_type=event_type,
        attachment_names=attachment_names,
        attachment_paths=attachment_paths,
        generated_image_count=generated_image_count,
        image_sources=parsed.image_sources,
        link_targets=parsed.link_targets,
        source_path=str(activity_html),
        relative_path=relative_path,
    )


def build_session_memory_items(activities: List[GeminiActivity]) -> List[MemoryItem]:
    grouped_sessions = group_activities_into_sessions(activities)
    items: List[MemoryItem] = []

    for session in grouped_sessions:
        session_start = session[0]
        session_end = session[-1]
        body = build_session_body(session)
        title = build_session_title(session)
        external_id = build_session_external_id(session)
        item_id = f"gemini:{external_id}"
        attachment_names = collect_unique_strings(
            activity.attachment_names for activity in session
        )
        attachment_paths = collect_unique_strings(
            activity.attachment_paths for activity in session
        )
        image_sources = collect_unique_strings(activity.image_sources for activity in session)
        link_targets = collect_unique_strings(activity.link_targets for activity in session)
        generated_image_count = sum(activity.generated_image_count for activity in session)
        event_types = collect_unique_strings([[activity.event_type] for activity in session])

        tags = ["gemini", "conversation", "takeout_html", "session"]
        if any(activity.event_type == "canvas" for activity in session):
            tags.append("has_canvas")
        if attachment_names:
            tags.append("has_attachment")
        if generated_image_count:
            tags.append("generated_image")

        metadata: Dict[str, object] = {
            "source": "google_my_activity_export",
            "export_format": "html",
            "source_path": session_start.source_path,
            "relative_path": session_start.relative_path,
            "session_gap_minutes": SESSION_GAP_MINUTES,
            "session_start_at": session_start.created_at,
            "session_end_at": session_end.created_at,
            "session_start_timestamp_text": session_start.timestamp_text,
            "session_end_timestamp_text": session_end.timestamp_text,
            "activity_count": len(session),
            "activity_indices": [activity.activity_index for activity in session],
            "event_types": event_types,
            "attachment_names": attachment_names,
            "attachment_paths": attachment_paths,
            "generated_image_count": generated_image_count,
            "image_sources": image_sources,
            "link_targets": link_targets,
        }

        items.append(
            MemoryItem(
                item_id=item_id,
                source_key="gemini_exports",
                source_type="gemini",
                external_id=external_id,
                item_type="conversation",
                title=title,
                body=body,
                created_at=session_end.created_at,
                updated_at=session_end.created_at,
                imported_at=None,
                checksum=build_checksum(
                    item_id,
                    title,
                    body,
                    session_start.created_at,
                    session_end.created_at,
                    str(len(session)),
                ),
                location=session_start.source_path,
                parent_id=None,
                metadata=metadata,
                tags=tags,
            )
        )

    return sorted(
        items,
        key=lambda item: (item.created_at is None, item.created_at or "", item.item_id),
        reverse=True,
    )


def extract_primary_content_html(block_html: str) -> str:
    marker = '<div class="content-cell mdl-cell mdl-cell--6-col mdl-typography--body-1">'
    start = block_html.find(marker)
    if start < 0:
        return ""
    start += len(marker)
    end_marker = (
        '</div><div class="content-cell mdl-cell mdl-cell--6-col '
        'mdl-typography--body-1 mdl-typography--text-right">'
    )
    end = block_html.find(end_marker, start)
    if end < 0:
        return ""
    return block_html[start:end]


def find_timestamp_index(lines: List[str]) -> Optional[int]:
    for index, line in enumerate(lines):
        if is_activity_timestamp(line.strip()):
            return index
    return None


def is_activity_timestamp(value: str) -> bool:
    if re.fullmatch(r"\d{4}年\d{1,2}月\d{1,2}日 \d{2}:\d{2}:\d{2}(?: [A-Z]{3,4})?", value):
        return True
    if re.fullmatch(r"\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}(?::\d{2})?", value):
        return True
    return False


def normalize_activity_timestamp(value: str) -> Optional[str]:
    cleaned = value.strip()
    for timezone_suffix in (" CEST", " CET"):
        if cleaned.endswith(timezone_suffix):
            cleaned = cleaned[: -len(timezone_suffix)].strip()
            break
    for fmt in ("%Y年%m月%d日 %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S"):
        try:
            return datetime.strptime(cleaned, fmt).replace(tzinfo=BERLIN_TZ).astimezone(
                ZoneInfo("UTC")
            ).isoformat()
        except ValueError:
            continue
    return None


def extract_prompt_text(prefix_lines: List[str]) -> str:
    prompt_lines: List[str] = []
    for index, line in enumerate(prefix_lines):
        if index == 0:
            line = line.replace("Prompted", "", 1).strip()
        if not line or is_attachment_line(line) or is_generated_image_line(line):
            continue
        prompt_lines.append(line)
    return "\n".join(prompt_lines).strip()


def extract_attachment_names(link_targets: List[str], base_dir: Path) -> List[str]:
    names: List[str] = []
    for href in link_targets:
        stripped = href.strip()
        if not stripped or "://" in stripped or stripped.startswith("mailto:"):
            continue
        candidate = Path(unescape(stripped))
        if candidate.is_absolute():
            continue
        resolved = (base_dir / candidate).resolve()
        if not resolved.exists() or not resolved.is_file():
            continue
        name = candidate.name
        if name not in names:
            names.append(name)
    return names


def extract_generated_image_count(lines: List[str]) -> int:
    for line in lines:
        match = re.fullmatch(r"(\d+) generated image(?:s)?\.", line)
        if match:
            return int(match.group(1))
    return 0


def is_attachment_line(line: str) -> bool:
    return (
        line.startswith("Attached ")
        or is_generated_image_line(line)
    )


def is_generated_image_line(line: str) -> bool:
    return bool(re.fullmatch(r"\d+ generated image(?:s)?\.", line.strip()))


def build_activity_body(
    prompt_text: str,
    response_text: str,
    attachment_names: List[str],
    generated_image_count: int,
) -> str:
    parts: List[str] = []
    if prompt_text:
        parts.append(f"Prompt:\n{prompt_text}")
    if response_text:
        parts.append(f"Response:\n{response_text}")
    if attachment_names:
        parts.append("Attachments:\n" + "\n".join(f"- {name}" for name in attachment_names))
    if generated_image_count:
        parts.append(f"Generated images: {generated_image_count}")
    return "\n\n".join(part for part in parts if part).strip()


def build_activity_title(prompt_text: str, response_text: str, event_type: str) -> str:
    if prompt_text:
        return first_non_empty_line(prompt_text)[:120]
    if response_text:
        return first_non_empty_line(response_text)[:120]
    return f"Gemini {event_type}".strip()[:120]


def build_activity_external_id(
    index: int, timestamp_text: str, prompt_text: str, response_text: str
) -> str:
    digest = hashlib.sha256(
        f"{timestamp_text}||{prompt_text}||{response_text}".encode("utf-8")
    ).hexdigest()[:16]
    return f"activity:{index:05d}:{digest}"


def group_activities_into_sessions(
    activities: List[GeminiActivity],
) -> List[List[GeminiActivity]]:
    sortable = sorted(
        activities,
        key=lambda activity: (
            activity.created_at is None,
            activity.created_at or "",
            activity.activity_index,
        ),
    )
    sessions: List[List[GeminiActivity]] = []
    current: List[GeminiActivity] = []

    for activity in sortable:
        if not current:
            current = [activity]
            continue

        previous = current[-1]
        if should_split_session(previous, activity):
            sessions.append(current)
            current = [activity]
            continue

        current.append(activity)

    if current:
        sessions.append(current)

    return sessions


def should_split_session(previous: GeminiActivity, current: GeminiActivity) -> bool:
    previous_dt = parse_iso_timestamp(previous.created_at)
    current_dt = parse_iso_timestamp(current.created_at)
    if previous_dt is None or current_dt is None:
        return True
    gap_minutes = (current_dt - previous_dt).total_seconds() / 60
    return gap_minutes > SESSION_GAP_MINUTES


def parse_iso_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC_TZ)
    except ValueError:
        return None


def build_session_body(session: List[GeminiActivity]) -> str:
    parts: List[str] = []
    for index, activity in enumerate(session, start=1):
        content = build_activity_body(
            activity.prompt_text,
            activity.response_text,
            activity.attachment_names,
            activity.generated_image_count,
        )
        header = f"Activity {index} | {activity.timestamp_text}"
        if activity.event_type != "prompt":
            header += f" | {activity.event_type}"
        parts.append(f"{header}\n{content}".strip())
    return "\n\n---\n\n".join(part for part in parts if part).strip()


def build_session_title(session: List[GeminiActivity]) -> str:
    for activity in session:
        candidate = activity.title.strip()
        if is_useful_session_title(candidate):
            return candidate[:120]
    return session[-1].title[:120]


def is_useful_session_title(title: str) -> bool:
    stripped = title.strip()
    if not stripped:
        return False
    if stripped.startswith("-"):
        return False
    if stripped == "'s Profilbild":
        return False
    if re.fullmatch(r".+\.(png|jpg|jpeg|gif|webp|pdf|docx|pptx|wav|mp3|txt|csv)", stripped, re.I):
        return False
    return True


def build_session_external_id(session: List[GeminiActivity]) -> str:
    first = session[0]
    last = session[-1]
    digest = hashlib.sha256(
        "||".join(
            [
                first.created_at or "",
                last.created_at or "",
                first.title,
                last.title,
                str(len(session)),
            ]
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"session:{digest}"


def collect_unique_strings(groups: List[List[str]]) -> List[str]:
    seen: List[str] = []
    for group in groups:
        for value in group:
            if value and value not in seen:
                seen.append(value)
    return seen


def list_gemini_export_files(export_path: Path) -> List[Path]:
    if not export_path.exists():
        return []
    return sorted(
        path
        for path in export_path.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_SUFFIXES
        and path.name not in ACTIVITY_HTML_NAMES
    )


def build_fallback_memory_items(export_root: Path, files: List[Path]) -> List[MemoryItem]:
    items: List[MemoryItem] = []
    for file_path in files:
        raw_text = read_export_text(file_path)
        content = normalize_content(raw_text)
        if not content:
            continue
        relative_path = file_path.relative_to(export_root)
        item_id = f"gemini:{relative_path.as_posix()}"
        title = build_file_title(file_path, content)
        created_at = normalize_file_timestamp(file_path.stat().st_mtime)
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
        parser = _GenericHTMLTextExtractor()
        parser.feed(text)
        parser.close()
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


def build_file_title(file_path: Path, content: str) -> str:
    first_line = first_non_empty_line(content)
    if first_line:
        return first_line[:120]
    return file_path.stem[:120]


def first_non_empty_line(content: str) -> str:
    return next((line.strip() for line in content.splitlines() if line.strip()), "")


def normalize_file_timestamp(timestamp: float) -> Optional[str]:
    try:
        return datetime.fromtimestamp(timestamp, tz=ZoneInfo("UTC")).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def build_checksum(*parts: Optional[str]) -> str:
    normalized = "||".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class _ActivityContentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: List[str] = []
        self._current_href: Optional[str] = None
        self.link_targets: List[str] = []
        self.image_sources: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        attrs_dict = dict(attrs)
        if tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "hr", "blockquote"}:
            self._chunks.append("\n")
        if tag == "a":
            self._current_href = attrs_dict.get("href")
        if tag == "img":
            src = attrs_dict.get("src")
            if src:
                self.image_sources.append(src)

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "blockquote"}:
            self._chunks.append("\n")
        if tag == "a":
            if self._current_href:
                self.link_targets.append(self._current_href)
            self._current_href = None

    def handle_data(self, data: str) -> None:
        if data:
            self._chunks.append(unescape(data))

    def get_text(self) -> str:
        return "".join(self._chunks)


class _GenericHTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        if tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if data:
            self._chunks.append(unescape(data))

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self._chunks.append("\n")

    def get_text(self) -> str:
        return "".join(self._chunks)
