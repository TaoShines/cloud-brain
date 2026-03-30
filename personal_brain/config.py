from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AppConfig:
    database_path: Path
    blog_repo_path: Path
    blog_glob: str
    codex_state_db_path: Path
    include_assistant_commentary: bool = True
    include_assistant_final_answers: bool = True


def load_config(config_path: Path) -> AppConfig:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return AppConfig(
        database_path=Path(payload["database_path"]).expanduser(),
        blog_repo_path=Path(payload["blog_repo_path"]).expanduser(),
        blog_glob=payload["blog_glob"],
        codex_state_db_path=Path(payload["codex_state_db_path"]).expanduser(),
        include_assistant_commentary=payload.get("include_assistant_commentary", True),
        include_assistant_final_answers=payload.get(
            "include_assistant_final_answers", True
        ),
    )
