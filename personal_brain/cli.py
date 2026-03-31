from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from .api import run_api_server
from .config import load_config
from .database import Database
from .sync import sync_cloud_capture_to_local, sync_configured_sources
from .time_filters import normalize_created_range


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Personal Brain CLI")
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to the Personal Brain config file",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="Initialize the SQLite database")
    subparsers.add_parser("sync", help="Import all configured data sources")
    subparsers.add_parser(
        "sync-cloud-capture",
        help="Import Cloudflare capture rows into the local SQLite database",
    )
    subparsers.add_parser("stats", help="Show record counts")
    migrations_parser = subparsers.add_parser(
        "migrations", help="Show applied schema migrations"
    )
    migrations_parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of migrations to show",
    )
    sync_runs_parser = subparsers.add_parser(
        "sync-runs", help="Show recent sync runs"
    )
    sync_runs_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of sync runs to show",
    )
    sync_runs_parser.add_argument(
        "--source-key",
        help="Optional source key filter",
    )
    sync_runs_parser.add_argument(
        "--status",
        help="Optional run status filter",
    )
    subparsers.add_parser(
        "source-health",
        help="Show source freshness and latest sync status",
    )
    serve_parser = subparsers.add_parser(
        "serve", help="Start the local HTTP API"
    )
    serve_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface for the API server",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for the API server",
    )

    timeline_parser = subparsers.add_parser(
        "timeline", help="Show a cross-source timeline of your records"
    )
    timeline_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of records to return",
    )
    timeline_parser.add_argument(
        "--source",
        choices=["blog", "gemini", "codex", "bookmark", "capture"],
        help="Optional source filter",
    )
    timeline_parser.add_argument(
        "--type",
        choices=["blog", "diary", "conversation", "message", "bookmark", "capture"],
        help="Optional record type filter",
    )
    timeline_parser.add_argument(
        "--tag",
        help="Optional tag filter",
    )
    timeline_parser.add_argument(
        "--status",
        help="Optional status filter",
    )
    timeline_parser.add_argument(
        "--domain",
        help="Optional domain filter for bookmark items",
    )
    timeline_parser.add_argument(
        "--after",
        dest="created_after",
        help="Inclusive lower time bound (YYYY-MM-DD or ISO-8601)",
    )
    timeline_parser.add_argument(
        "--before",
        dest="created_before",
        help="Inclusive upper time bound (YYYY-MM-DD or ISO-8601)",
    )

    show_parser = subparsers.add_parser("show", help="Show one record in full")
    show_parser.add_argument("record_key", help="Record key from search or timeline")

    related_parser = subparsers.add_parser(
        "related", help="Show items related to one canonical item"
    )
    related_parser.add_argument("item_id", help="Canonical item id")
    related_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of related items to return",
    )
    related_parser.add_argument(
        "--relation",
        help="Optional relation type filter",
    )

    search_parser = subparsers.add_parser("search", help="Full-text search")
    search_parser.add_argument("query", help="FTS query string")
    search_parser.add_argument(
        "--kind",
        choices=["blog", "diary", "conversation", "message", "bookmark", "capture"],
        help="Optional item type filter",
    )
    search_parser.add_argument(
        "--source",
        choices=["blog", "gemini", "codex", "bookmark", "capture"],
        help="Optional source filter",
    )
    search_parser.add_argument(
        "--tag",
        help="Optional tag filter",
    )
    search_parser.add_argument(
        "--status",
        help="Optional status filter",
    )
    search_parser.add_argument(
        "--domain",
        help="Optional domain filter for bookmark items",
    )
    search_parser.add_argument(
        "--after",
        dest="created_after",
        help="Inclusive lower time bound (YYYY-MM-DD or ISO-8601)",
    )
    search_parser.add_argument(
        "--before",
        dest="created_before",
        help="Inclusive upper time bound (YYYY-MM-DD or ISO-8601)",
    )
    search_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of matches to return",
    )
    search_parser.add_argument(
        "--context",
        type=int,
        default=80,
        help="Characters of context to show before and after a match",
    )
    search_parser.add_argument(
        "--show-full",
        action="store_true",
        help="Show the full content for each result",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(Path(args.config))
    database = Database(config.database_path)

    try:
        if args.command == "init":
            database.init()
            print(f"Initialized database at {config.database_path}")
            return 0

        database.init()

        if args.command == "sync":
            try:
                summary = sync_configured_sources(config)
            except ValueError as exc:
                print(str(exc))
                return 1
            print(
                "Synced "
                f"{summary.document_count} documents, "
                f"{summary.conversation_count} conversations, "
                f"{summary.message_count} messages, "
                f"{summary.bookmark_count} bookmarks, "
                f"{summary.record_count} unified records"
            )
            return 0

        if args.command == "sync-cloud-capture":
            try:
                summary = sync_cloud_capture_to_local(config)
            except ValueError as exc:
                print(str(exc))
                return 1
            print(
                "Synced "
                f"{summary.item_count} cloud capture items, "
                f"{summary.record_count} unified records"
            )
            return 0

        if args.command == "stats":
            stats = database.stats()
            print(f"records: {stats['record_count']}")
            print(f"items: {stats['item_count']}")
            print(f"item_links: {stats['item_link_count']}")
            print(f"schema_migrations: {stats['schema_migration_count']}")
            print(f"sync_runs: {stats['sync_run_count']}")
            print(f"documents: {stats['document_count']}")
            print(f"document_tags: {stats['document_tag_count']}")
            print(f"item_tags: {stats['item_tag_count']}")
            print(f"conversations: {stats['conversation_count']}")
            print(f"messages: {stats['message_count']}")
            print(f"bookmarks: {stats['bookmark_count']}")
            print(f"search_index: {stats['search_index_count']}")
            return 0

        if args.command == "migrations":
            rows = database.list_schema_migrations()[: max(0, args.limit)]
            for row in rows:
                print(f"{row['version']}  {row['applied_at']}")
            return 0

        if args.command == "sync-runs":
            rows = database.list_sync_runs(
                limit=args.limit,
                source_key=args.source_key,
                status=args.status,
            )
            for row in rows:
                payload = database.serialize_sync_run(row)
                scope = payload["source_key"] or "all_sources"
                print(f"[{payload['status']}] run:{payload['id']} {payload['sync_type']} {scope}")
                print(f"started_at: {payload['started_at']}")
                if payload["finished_at"]:
                    print(f"finished_at: {payload['finished_at']}")
                if payload["duration_seconds"] is not None:
                    print(f"duration_seconds: {payload['duration_seconds']}")
                if payload["source_type"]:
                    print(f"source_type: {payload['source_type']}")
                if payload["location"]:
                    print(f"location: {payload['location']}")
                if payload["parent_run_id"]:
                    print(f"parent_run_id: {payload['parent_run_id']}")
                if payload["stats"]:
                    print("stats:")
                    print(json.dumps(payload["stats"], ensure_ascii=False, indent=2, sort_keys=True))
                if payload["warnings"]:
                    print("warnings:")
                    print(json.dumps(payload["warnings"], ensure_ascii=False, indent=2))
                if payload["error_message"]:
                    print(f"error: {payload['error_message']}")
                print()
            return 0

        if args.command == "source-health":
            rows = database.list_source_health()
            for row in rows:
                payload = database.serialize_source_health(row)
                print(f"[{payload['last_run_status']}] {payload['source_key']}")
                print(f"source_type: {payload['source_type']}")
                if payload["last_synced_at"]:
                    print(f"last_synced_at: {payload['last_synced_at']}")
                if payload["last_success_at"]:
                    print(f"last_success_at: {payload['last_success_at']}")
                if payload["last_run_started_at"]:
                    print(f"last_run_started_at: {payload['last_run_started_at']}")
                if payload["last_run_finished_at"]:
                    print(f"last_run_finished_at: {payload['last_run_finished_at']}")
                if payload["location"]:
                    print(f"location: {payload['location']}")
                if payload["last_stats"]:
                    print("last_stats:")
                    print(json.dumps(payload["last_stats"], ensure_ascii=False, indent=2, sort_keys=True))
                if payload["last_warnings"]:
                    print("last_warnings:")
                    print(json.dumps(payload["last_warnings"], ensure_ascii=False, indent=2))
                if payload["last_error_message"]:
                    print(f"last_error: {payload['last_error_message']}")
                print()
            return 0

        if args.command == "serve":
            database.close()
            run_api_server(
                config,
                host=args.host,
                port=args.port,
            )
            return 0

        if args.command == "timeline":
            try:
                created_after, created_before = normalize_created_range(
                    args.created_after,
                    args.created_before,
                )
            except ValueError as exc:
                print(str(exc))
                return 1
            rows = database.timeline(
                limit=args.limit,
                source_type=args.source,
                record_type=args.type,
                tag=args.tag,
                status=args.status,
                domain=args.domain,
                created_after=created_after,
                created_before=created_before,
            )
            for row in rows:
                print(f"[{row['source_type']}/{row['record_type']}] {row['record_key']}")
                if row["created_at"]:
                    print(f"time: {row['created_at']}")
                print(f"title: {row['title']}")
                print(f"preview: {normalize_preview(row['preview'])}")
                if row["location"]:
                    print(f"location: {row['location']}")
                print()
            return 0

        if args.command == "show":
            row = database.get_record(args.record_key)
            if not row:
                print(f"Record not found: {args.record_key}")
                return 1
            print(f"[{row['source_type']}/{row['record_type']}] {row['record_key']}")
            if row["created_at"]:
                print(f"time: {row['created_at']}")
            print(f"title: {row['title']}")
            if row["location"]:
                print(f"location: {row['location']}")
            if row["parent_key"]:
                print(f"parent: {row['parent_key']}")
            if row["source_key"]:
                print(f"source_key: {row['source_key']}")
            if row["external_id"]:
                print(f"external_id: {row['external_id']}")
            if row["imported_at"]:
                print(f"imported_at: {row['imported_at']}")
            if row["checksum"]:
                print(f"checksum: {row['checksum']}")
            metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
            if metadata:
                print("metadata:")
                print(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))
            print("body:")
            print(row["body"])
            return 0

        if args.command == "related":
            rows = database.list_related_items(
                args.item_id,
                limit=args.limit,
                relation_type=args.relation,
            )
            if not rows:
                print(f"No related items found for: {args.item_id}")
                return 0
            for row in rows:
                relation_value = row["relation_value"]
                relation_label = row["relation_type"]
                if relation_value:
                    relation_label = f"{relation_label}:{relation_value}"
                print(f"[{relation_label}] {row['item_id']}")
                if row["created_at"]:
                    print(f"time: {row['created_at']}")
                print(f"title: {row['title']}")
                print(f"source: {row['source_type']}/{row['item_type']}")
                if row["location"]:
                    print(f"location: {row['location']}")
                print()
            return 0

        if args.command == "search":
            try:
                created_after, created_before = normalize_created_range(
                    args.created_after,
                    args.created_before,
                )
            except ValueError as exc:
                print(str(exc))
                return 1
            rows = database.search_items(
                args.query,
                item_type=args.kind,
                source_type=args.source,
                tag=args.tag,
                status=args.status,
                domain=args.domain,
                created_after=created_after,
                created_before=created_before,
                limit=args.limit,
            )
            for row in rows:
                print(f"[{row['item_type']}] {row['item_id']}")
                if row["created_at"]:
                    print(f"time: {row['created_at']}")
                print(f"title: {row['title']}")
                snippet = build_context_snippet(row["body"], args.query, args.context)
                if not snippet:
                    snippet = row["snippet"]
                print(f"match: {snippet}")
                if row["location"]:
                    print(f"location: {row['location']}")
                if args.show_full and row["body"]:
                    print("full:")
                    print(row["body"])
                print()
            return 0
    finally:
        database.close()

    parser.error(f"Unsupported command: {args.command}")
    return 1


def build_context_snippet(content: str, query: str, context_size: int) -> str:
    if not content:
        return ""
    index = content.lower().find(query.lower())
    if index < 0:
        index = content.find(query)
    if index < 0:
        return content[: context_size * 2].replace("\n", " ")

    start = max(0, index - context_size)
    end = min(len(content), index + len(query) + context_size)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(content) else ""
    snippet = content[start:end].replace("\n", " ")
    return f"{prefix}{snippet}{suffix}"


def build_location(
    entity_type: str, location: Optional[str], content: str, query: str
) -> Optional[str]:
    if not location:
        return None
    if entity_type != "document":
        return location

    path = Path(location)
    if not path.exists():
        return location

    line_number = find_line_number(path, query)
    if line_number is None:
        return location
    return f"{location}:{line_number}"


def find_line_number(path: Path, query: str) -> Optional[int]:
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if query in line:
            return line_number
    lowered_query = query.lower()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if lowered_query in line.lower():
            return line_number
    return None


def normalize_preview(text: str) -> str:
    return " ".join(text.split())
