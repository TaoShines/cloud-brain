from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class AppConfig:
    database_path: Path
    blog_repo_path: Optional[Path]
    blog_glob: str
    codex_state_db_path: Optional[Path]
    chrome_bookmarks_path: Optional[Path]
    capture_token: Optional[str]
    cloud_capture_project_path: Optional[Path]
    cloud_capture_database_name: Optional[str]
    cloud_capture_auto_sync_enabled: bool = True
    cloud_capture_auto_sync_interval_seconds: int = 86400
    include_assistant_commentary: bool = True
    include_assistant_final_answers: bool = True


def load_config(config_path: Path) -> AppConfig:
    payload = _load_payload(config_path)
    config_dir = config_path.parent
    return AppConfig(
        database_path=_resolve_path(payload.get("database_path"), config_dir)
        or config_dir / "data" / "personal_brain.db",
        blog_repo_path=_resolve_path(payload.get("blog_repo_path"), config_dir),
        blog_glob=payload.get("blog_glob", "src/data/blog/**/*.md"),
        codex_state_db_path=_resolve_path(payload.get("codex_state_db_path"), config_dir),
        chrome_bookmarks_path=_resolve_path(
            payload.get("chrome_bookmarks_path"), config_dir
        ),
        capture_token=_optional_string(payload.get("capture_token")),
        cloud_capture_project_path=_resolve_cloud_capture_project_path(payload, config_dir),
        cloud_capture_database_name=_optional_string(payload.get("cloud_capture_database_name"))
        or "cloud-brain-capture",
        cloud_capture_auto_sync_enabled=_optional_bool(
            payload.get("cloud_capture_auto_sync_enabled"), True
        ),
        cloud_capture_auto_sync_interval_seconds=_optional_int(
            payload.get("cloud_capture_auto_sync_interval_seconds"), 86400, minimum=60
        ),
        include_assistant_commentary=payload.get("include_assistant_commentary", True),
        include_assistant_final_answers=payload.get(
            "include_assistant_final_answers", True
        ),
    )


def _load_payload(config_path: Path) -> Dict[str, Any]:
    payload = _read_json(config_path)
    local_config_path = config_path.with_name(f"{config_path.stem}.local{config_path.suffix}")
    if local_config_path.exists():
        payload.update(_read_json(local_config_path))
    return payload


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_path(value: object, config_dir: Path) -> Optional[Path]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = (config_dir / path).resolve()
    return path


def _optional_string(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _optional_int(value: object, default: int, minimum: int = 0) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


def _resolve_cloud_capture_project_path(
    payload: Dict[str, Any], config_dir: Path
) -> Optional[Path]:
    explicit = _resolve_path(payload.get("cloud_capture_project_path"), config_dir)
    if explicit:
        return explicit
    default_path = (config_dir / "cloudflare-capture").resolve()
    if default_path.exists():
        return default_path
    return None
