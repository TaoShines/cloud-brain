from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Optional, Tuple


def normalize_created_range(
    created_after: Optional[str],
    created_before: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    normalized_after = normalize_created_boundary(created_after, is_end=False)
    normalized_before = normalize_created_boundary(created_before, is_end=True)
    if normalized_after and normalized_before and normalized_after > normalized_before:
        raise ValueError("created_after must be earlier than or equal to created_before")
    return normalized_after, normalized_before


def normalize_created_boundary(value: Optional[str], *, is_end: bool) -> Optional[str]:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None

    try:
        if _looks_like_date_only(text):
            parsed_date = date.fromisoformat(text)
            parsed_datetime = datetime.combine(
                parsed_date,
                time.max if is_end else time.min,
                tzinfo=timezone.utc,
            )
        else:
            parsed_datetime = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed_datetime.tzinfo is None:
                parsed_datetime = parsed_datetime.replace(tzinfo=timezone.utc)
            else:
                parsed_datetime = parsed_datetime.astimezone(timezone.utc)
    except ValueError as exc:
        raise ValueError(
            "Invalid time filter. Use YYYY-MM-DD or an ISO-8601 timestamp."
        ) from exc

    return parsed_datetime.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _looks_like_date_only(value: str) -> bool:
    return len(value) == 10 and value[4] == "-" and value[7] == "-"
