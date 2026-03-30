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
