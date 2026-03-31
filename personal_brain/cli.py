from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from .api import run_api_server
from .config import load_config
from .database import Database
from .sync import sync_cloud_capture_to_local, sync_configured_sources


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
        choices=["blog", "codex", "bookmark", "capture"],
        help="Optional source filter",
    )
    timeline_parser.add_argument(
        "--type",
        choices=["blog", "diary", "conversation", "message", "bookmark", "capture"],
        help="Optional record type filter",
    )

    show_parser = subparsers.add_parser("show", help="Show one record in full")
    show_parser.add_argument("record_key", help="Record key from search or timeline")

    search_parser = subparsers.add_parser("search", help="Full-text search")
    search_parser.add_argument("query", help="FTS query string")
    search_parser.add_argument(
        "--kind",
        choices=["blog", "diary", "conversation", "message", "bookmark", "capture"],
        help="Optional item type filter",
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
            print(f"documents: {stats['document_count']}")
            print(f"document_tags: {stats['document_tag_count']}")
            print(f"item_tags: {stats['item_tag_count']}")
            print(f"conversations: {stats['conversation_count']}")
            print(f"messages: {stats['message_count']}")
            print(f"bookmarks: {stats['bookmark_count']}")
            print(f"search_index: {stats['search_index_count']}")
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
            rows = database.timeline(
                limit=args.limit,
                source_type=args.source,
                record_type=args.type,
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

        if args.command == "search":
            rows = database.search_items(args.query, item_type=args.kind, limit=args.limit)
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
