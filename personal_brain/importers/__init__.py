from __future__ import annotations

from typing import List

from ..config import AppConfig
from ..models import ImporterPayload
from .blog import import_blog_source
from .bookmarks import import_chrome_bookmarks_source
from .cloud_capture import import_cloud_capture_source
from .codex import import_codex_source


def load_importer_payloads(config: AppConfig) -> List[ImporterPayload]:
    payloads: List[ImporterPayload] = []
    if config.blog_repo_path:
        payloads.append(import_blog_source(config.blog_repo_path, config.blog_glob))
    if config.codex_state_db_path:
        payloads.append(import_codex_source(config.codex_state_db_path, config))
    if config.chrome_bookmarks_path:
        payloads.append(import_chrome_bookmarks_source(config.chrome_bookmarks_path))
    if config.cloud_capture_project_path:
        payloads.append(import_cloud_capture_source(config))
    return payloads
