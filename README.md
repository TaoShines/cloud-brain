# Personal Brain

A local-first personal database that now has a simple 2.0 foundation.

For the longer-term direction of the project as a real "Cloud Brain" system,
see [`ARCHITECTURE.md`](/Users/taoxuan/Desktop/cloud-brain/ARCHITECTURE.md).

## Current Direction

This project is becoming a personal memory backend for long-term AI use.

## Recent Infrastructure Updates

The most recent work focused on infrastructure instead of topic modeling.

What changed:

- Gemini import now lands in one canonical session-style item format
- CLI and API time filters now support both ISO timestamps and `YYYY-MM-DD`
- `item_links` now stores lightweight structural relationships such as
  `conversation -> message`
- database initialization now applies tracked schema migrations through
  `schema_migrations`
- sync execution metadata is now stored in `sync_runs`
- each full sync records:
  - one root run for the overall sync
  - one child run per source
  - start time, finish time, status, counts, and error message when present

Why this matters:

- the database contract is becoming safer to evolve
- future AI clients can inspect sync freshness and sync health directly
- new schema changes can be introduced without relying on one giant init script
- the system is moving closer to a durable personal data infrastructure instead
  of a one-off importer bundle

Recommended next infrastructure steps:

- record sync duration and source-level warnings
- expose a clearer source health view through the API
- keep stabilizing canonical item fields before adding higher-level AI layers

The working direction is:

- keep your source data in its original tools and folders
- sync it into one durable SQLite memory database
- normalize everything into a canonical `items` layer
- expose the memory layer through a local API
- improve retrieval so future AI clients can query memory precisely instead of
  reading everything at once
- add a low-friction capture path so new thoughts can enter the database at the
  moment they happen

At this stage, the project is optimized more for "AI can reliably read this
memory system later" than for "humans browse it manually every day".

The newest product direction is to add an active input path from mobile, so the
system can capture in-the-moment thoughts instead of only importing material
after the fact.

It starts with three sources:

- your blog/journal Markdown files
- your Gemini conversations exported from Google Docs
- your Codex conversation history
- your Chrome bookmarks metadata

The project stores everything in SQLite, creates full-text indexes, and also
builds a unified timeline so you can answer questions like:

- "When did I write about Codex?"
- "When did I ask about my personal database?"
- "Show me all diary entries tagged with AI"
- "What was I thinking around the end of March?"
- "Show me one exact record and where it came from"

## Why this structure

- Source files stay in their original locations.
- SQLite gives you a durable personal data layer.
- FTS keeps search fast as your archive grows.
- New sources can be added later without changing the foundation.

## Project layout

```text
personal_brain/
  brain/
    __main__.py
    cli.py
    config.py
    database.py
    models.py
    importers/
      blog.py
      codex.py
  data/
    personal_brain.db
  config.json
```

## Quick start

Optional but recommended: create your private local config override first.

```bash
cp config.local.example.json config.local.json
```

Then update `config.local.json` with your own local source paths.

Initialize the database:

```bash
python3 -m personal_brain init
```

Sync configured sources:

```bash
python3 -m personal_brain sync
```

Sync only cloud capture into local SQLite:

```bash
python3 -m personal_brain sync-cloud-capture
```

View basic stats:

```bash
python3 -m personal_brain stats
python3 -m personal_brain migrations
python3 -m personal_brain sync-runs --limit 10
```

Start the local read-only API:

```bash
python3 -m personal_brain serve
```

Search across blog entries, thread titles, user questions, and assistant replies:

```bash
python3 -m personal_brain search "数据库"
python3 -m personal_brain search "Codex" --kind message
python3 -m personal_brain search "佛教" --context 120
python3 -m personal_brain search "公式图片" --source gemini --after 2026-03-01 --before 2026-03-31
```

Show one combined timeline across blog, Codex, and bookmarks:

```bash
python3 -m personal_brain timeline --limit 20
python3 -m personal_brain timeline --source blog
python3 -m personal_brain timeline --source gemini
python3 -m personal_brain timeline --type message
python3 -m personal_brain timeline --source capture --after 2026-03-31
```

Show one record in full:

```bash
python3 -m personal_brain show "blog:src/data/blog/_2026-03-30.md"
python3 -m personal_brain show "019d403f-5817-7320-b960-4d738388d8f2:48"
```

Show related canonical items:

```bash
python3 -m personal_brain related "capture:your-item-id"
python3 -m personal_brain related "019d403f-5817-7320-b960-4d738388d8f2:48" --relation part_of
```

Query the local API from another AI tool or script:

```bash
curl http://127.0.0.1:8765/health
curl "http://127.0.0.1:8765/stats"
curl "http://127.0.0.1:8765/timeline?limit=5&source_type=codex"
curl "http://127.0.0.1:8765/search?q=%E6%95%B0%E6%8D%AE%E5%BA%93&limit=5"
curl "http://127.0.0.1:8765/items/019d403f-5817-7320-b960-4d738388d8f2:55"
```

Run the local daily sync script manually:

```bash
./scripts/daily_sync.sh
```

## Current Capture Status

The project now has two working capture paths:

1. local capture into the repo SQLite database
2. cloud capture into Cloudflare Workers + D1

Current behavior:

- local browser or local API capture writes into `data/personal_brain.db`
- local capture items are stored as canonical `items` with `item_type=capture`
- sync no longer wipes manually created local capture items when blog, Codex,
  or bookmark sources refresh
- cloud capture is deployed separately in [`cloudflare-capture`](/Users/taoxuan/Desktop/cloud-brain/cloudflare-capture)
- cloud capture writes into Cloudflare D1 first, then syncs into local SQLite
  through `python3 -m personal_brain sync-cloud-capture`
- when the local API server runs, it now performs cloud-capture sync once at
  startup and then again on a timer
- the included launchd job now runs cloud-capture sync at login and then once
  per day at 02:00

Important current limitation:

- cloud capture is still not written directly into local SQLite at submission
  time
- it becomes automatic through background sync rather than write-through

## Local Checks

To check whether a locally captured thought has been saved into the local brain
database, use the CLI first.

Search local capture items by keyword:

```bash
python3 -m personal_brain search "震惊" --kind capture --show-full
python3 -m personal_brain search "关键词" --kind capture
```

Show the latest local capture records:

```bash
python3 -m personal_brain timeline --limit 10 --type capture
python3 -m personal_brain timeline --limit 20 --source capture
```

Show one local capture item in full after you know the `item_id`:

```bash
python3 -m personal_brain show "capture:your-item-id"
```

If the local API is running, you can also inspect local capture data through
HTTP:

```bash
python3 -m personal_brain serve --host 127.0.0.1 --port 8765
curl "http://127.0.0.1:8765/items?item_type=capture&limit=10"
curl "http://127.0.0.1:8765/search?q=关键词&item_type=capture&limit=5"
```

## Cloud Capture Checks

The cloud capture service is a separate deployment under
[`cloudflare-capture`](/Users/taoxuan/Desktop/cloud-brain/cloudflare-capture).

To inspect cloud-side captures from this Mac:

```bash
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"
cd /Users/taoxuan/Desktop/cloud-brain/cloudflare-capture
npx wrangler d1 execute cloud-brain-capture --remote --command "SELECT item_id, created_at, title FROM captures ORDER BY created_at DESC LIMIT 10"
```

To count cloud capture rows:

```bash
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"
cd /Users/taoxuan/Desktop/cloud-brain/cloudflare-capture
npx wrangler d1 execute cloud-brain-capture --remote --command "SELECT COUNT(*) AS capture_count FROM captures"
```

To pull cloud captures back into local SQLite:

```bash
python3 -m personal_brain sync-cloud-capture
python3 -m personal_brain search "公网上" --kind capture --show-full
```

To install the included launchd job for automatic local replica sync:

```bash
mkdir -p ~/Library/LaunchAgents
cp /Users/taoxuan/Desktop/cloud-brain/launchd/com.taoxuan.cloud-brain-sync.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.taoxuan.cloud-brain-sync.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.taoxuan.cloud-brain-sync.plist
```

## Configuration

The project now separates shared defaults from machine-specific paths:

- [`config.json`](/Users/taoxuan/Desktop/cloud-brain/config.json) is the tracked project config
- `config.local.json` is your private local override and is ignored by git
- [`config.local.example.json`](/Users/taoxuan/Desktop/cloud-brain/config.local.example.json) shows the expected local fields

By default:

- the SQLite database lives inside this repo at `data/personal_brain.db`
- blog, Codex, and Chrome bookmark source paths can be supplied in `config.local.json`
- Gemini exports from Google Docs can be supplied with `gemini_export_path`
- cloud-capture background sync is enabled by default every 86400 seconds
  when `python3 -m personal_brain serve` is running
- you can override that behavior with
  `cloud_capture_auto_sync_enabled` and
  `cloud_capture_auto_sync_interval_seconds`
- detailed message content is still read from the `rollout_path` recorded in Codex thread history

This makes the repo portable while keeping your private filesystem paths out of the shared project config.

## Gemini Import

Recommended workflow:

1. Export your Gemini data with Google Takeout or place exported Gemini HTML
   files into one local folder, for example:
   `/Users/taoxuan/Desktop/cloud-brain/data/gemini_exports`
2. Set `gemini_export_path` in `config.local.json`.
3. Run:

```bash
python3 -m personal_brain sync
python3 -m personal_brain timeline --source gemini --limit 10
python3 -m personal_brain search "公式图片" --kind conversation --limit 5
```

Current behavior:

- if a Google My Activity export file such as `我的活动记录.html` is present,
  the importer parses the activity log directly
- nearby Gemini activities are grouped into one canonical `conversation` item
  using a session-style import
- generated-image steps and attached files are kept together in the same
  conversation body and metadata
- while the Gemini import format is still being refined, sync does a hard
  replacement for `gemini_exports` so the database keeps one canonical Gemini
  representation instead of preserving duplicate old import formats
- fallback support for standalone `.txt`, `.md`, `.html`, and `.htm` exports
  still remains when no activity-log HTML is present

## What changed in 2.0

Compared with the first version, the main difference is that your data is no
longer only stored as separate technical tables. It is also projected into one
unified memory layer.

That means:

- blog posts and diary entries become memory items
- Codex conversations become memory items
- individual user and assistant messages become memory items
- everything can now be viewed in a single timeline
- each record keeps its source location so you can trace it back
- each item also keeps a stable source key, external id, checksum, and import timestamp

This is the first step toward a larger personal system where more sources can be
added later without changing how you use it.

## Data model

### `documents`

Blog or diary records, including title, content, slug, timestamps, tags, and
source path.

### `conversations`

Codex threads, including thread id, title, working directory, timestamps, and
rollout file path.

### `messages`

User and assistant messages extracted from Codex rollout JSONL files. Assistant
commentary and final answers are stored with their phase so you can filter or
analyze them later.

### `bookmarks`

Chrome bookmark metadata, including:

- title
- url
- folder path
- added time
- deleted time when a later sync sees that the bookmark disappeared
- lifecycle status such as `active` or `deleted`

### `items`

The canonical memory layer for long-term growth.

Each item keeps:

- a stable item id
- a source key and external source id
- a type
- timestamps
- the original location
- the original content
- a checksum
- an import timestamp
- metadata for future extensions

For bookmarks, metadata is intentionally lightweight. The system stores bookmark
metadata as evidence of interest and attention over time, not as a copy of the
full web page.

### `records`

A compatibility projection that keeps the current cross-source timeline and show
commands simple while the canonical `items` layer becomes the real foundation.

Each record keeps:

- a stable key
- a type
- timestamps
- the original location
- the original content

### `search_index`

An FTS5 index that unifies your searchable content for fast keyword search.

## Local API

The project now exposes a minimal local HTTP API for scripts and AI tools.

Current endpoints:

- `GET /health`
- `GET /stats`
- `GET /migrations`
- `GET /sync-runs`
- `GET /timeline`
- `GET /items`
- `GET /items/{item_id}`
- `GET /items/{item_id}/related`
- `GET /search?q=...`
- `GET /capture`
- `POST /captures`

Supported filters today:

- `limit`
- `offset`
- `source_type`
- `item_type`
- `tag`
- `status`
- `domain`
- `created_after`
- `created_before`

Time filters accept either:

- full ISO-8601 timestamps such as `2026-03-31T00:00:00Z`
- date-only values such as `2026-03-31`

Date-only filters are interpreted in UTC. `created_after=2026-03-31` means the
start of that UTC day, while `created_before=2026-03-31` means the end of that
UTC day.

Bookmark items are also available through the same `items`, `timeline`, and
`search` endpoints once they have been synced.

Examples for AI-oriented retrieval:

```bash
curl "http://127.0.0.1:8765/items?item_type=bookmark&status=active&limit=20"
curl "http://127.0.0.1:8765/items?item_type=bookmark&domain=www.youtube.com"
curl "http://127.0.0.1:8765/timeline?source_type=bookmark&created_after=2026-03-01T00:00:00+00:00"
curl "http://127.0.0.1:8765/search?q=AI&item_type=bookmark&status=active&limit=10"
curl "http://127.0.0.1:8765/items/capture:your-item-id/related?limit=10"
curl "http://127.0.0.1:8765/migrations"
curl "http://127.0.0.1:8765/sync-runs?limit=10"
```

Current relationship types:

- `has_part` and `part_of` for explicit parent-child item structure
- `shares_tag` for cross-item links built from small, non-generic shared tags

## Schema And Sync Metadata

The database now keeps two pieces of infrastructure metadata:

- `schema_migrations` records which schema upgrades have been applied
- `sync_runs` records when sync jobs started, finished, succeeded, or failed

This makes the database safer to evolve over time and gives future AI tools a
way to inspect import health instead of assuming the local replica is always
fresh.

Mobile capture write example:

```bash
curl -X POST http://127.0.0.1:8765/captures \
  -H "Content-Type: application/json" \
  -d '{
    "body": "在路上突然想到：把每日复盘和 mobile capture 自动串起来。",
    "device": "iphone",
    "input_type": "voice",
    "source_label": "typeless_ai",
    "tags": ["idea", "workflow"]
  }'
```

`POST /captures` accepts:

- required `body`
- optional `title`
- optional `created_at`
- optional `device`
- optional `input_type`
- optional `source_label`
- optional `tags`

New capture items are stored as canonical `items` with `source_type=capture`
and `item_type=capture`, so they remain available through the existing
`/items`, `/timeline`, and `/search` endpoints after future sync runs.

If you want to expose capture on the public internet, set `capture_token` in
`config.local.json` first and open the page as:

```text
https://your-public-url.example/capture?token=your-secret-token
```

For Android, the intended first-run flow is:

1. open `http://<your-mac-ip>:8765/capture` in the phone browser
2. use Typeless AI as the keyboard or voice input method
3. tap save once to send the transcribed text into Cloud Brain
4. optionally add the page to the Android home screen for an app-like shortcut

For a long-lived public deployment, use the Cloudflare Workers version in
[`cloudflare-capture`](/Users/taoxuan/Desktop/cloud-brain/cloudflare-capture)
instead of relying on the local Mac to stay online.

## Importer Standard

The importer layer is now designed around one shared contract so future sources
can plug into the same sync pipeline.

Each importer now returns one standardized payload that includes:

- source identity: `source_key`, `source_type`, `location`
- canonical memory output: `memory_items`
- optional source-specific rows: `documents`, `conversations`, `messages`
- source tags: `tags_by_source_id`

This matters because a new source should only need to solve one local problem:
how to parse its own raw data and map it into canonical `MemoryItem` rows.

The rest of the system should stay the same:

- sync orchestration
- storage in SQLite
- timeline and show commands
- search index
- local read API

### Importer Flow

When adding a new source later, the expected steps are:

1. Read the raw source files or export data.
2. Parse source-specific fields.
3. Map each record into one or more canonical `MemoryItem` values.
4. Add source-specific metadata into `metadata`.
5. Return one importer payload and register it in the importer loader.

### Why This Helps Future Sources

This is especially important for larger future sources like WeChat history.

Without a standard importer contract, each new source would force ad hoc changes
throughout the CLI, sync logic, and database layer. With the current design, a
future WeChat importer should mostly focus on:

- parsing exported chat data
- mapping chats and messages into `MemoryItem` rows
- attaching metadata like sender, group, and message type

Once that payload is returned, the existing sync, search, timeline, and API
layers can reuse it directly.

## Bookmark Notes

Chrome bookmarks are treated as an interest-tracking source, not a full web
archive.

That means the database stores:

- when a bookmark was added
- which url it points to
- which folder it belonged to
- whether it is still active
- when it was first observed as deleted in a later sync

The database does not currently fetch or store the full contents of bookmarked
pages. This keeps the source lightweight while still preserving evidence of
your changing interests and attention over time.

## What Exists Today

The current system already includes:

- blog and diary import from your blog repository
- Codex conversation and message import
- Chrome bookmark import with `added_at`, `status`, and future `deleted_at`
  tracking
- canonical `items` storage
- compatibility `records` projection for timeline and show commands
- full-text search
- a local read-only API for AI tools and scripts
- daily local sync on your Mac via `launchd`

This means the core foundation is already in place. The main work ahead is
continuing to strengthen retrieval, source expansion, and AI calling patterns
on top of the existing memory backend.

What is still missing is a native capture path for new thoughts. Right now the
system is very good at importing existing data, but it still needs a fast way
to accept fresh input from your phone while you are on the move.

## New Input Direction

The latest agreed direction is to add a mobile capture flow for active input.

Target flow:

1. open a simple mobile-friendly app or web page
2. speak a thought using your existing Typeless AI voice input
3. submit the transcribed text into the Cloud Brain database

Important product decision:

- the first version does not need to be a custom keyboard or input method
- the first version should focus on a data capture endpoint
- the first version can be a lightweight mobile web app instead of a full
  native app

Why this matters:

- blog posts, Codex logs, and bookmarks are all after-the-fact records
- a capture endpoint lets the database receive thoughts at the moment they are
  produced
- this turns the project from a passive archive into an active external memory
  system

## Planned Capture Architecture

The current planned implementation order is:

1. add a write API for new memory capture
2. define a new canonical item type such as `capture` or `voice_note`
3. build a very small mobile-first input surface
4. send captured text into the same SQLite-backed memory system

The first version should stay intentionally small:

- one input field
- one submit action
- optional title later if needed
- automatic timestamp
- minimal metadata such as device or source type

The goal is not to build a complex note-taking app first. The goal is to make
"I had a thought on the road and saved it in seconds" actually work.

## Local Daily Sync

The project now includes a local macOS scheduled sync setup.

Files:

- [`scripts/daily_sync.sh`](/Users/taoxuan/Desktop/cloud-brain/scripts/daily_sync.sh) runs `sync` and `stats`
- [`launchd/com.taoxuan.cloud-brain-sync.plist`](/Users/taoxuan/Desktop/cloud-brain/launchd/com.taoxuan.cloud-brain-sync.plist) is the LaunchAgent definition

Current schedule:

- every day at `02:00` local time

Logs:

- `logs/daily_sync.log`
- `logs/launchd.stdout.log`
- `logs/launchd.stderr.log`

This scheduled sync matters for bookmark deletion tracking. The recorded
`deleted_at` time is the first sync when the system notices a bookmark is gone,
so running sync daily keeps that timestamp much closer to the real change.

### Practical Note

When testing sync manually, run `sync` first and then run `stats` or `timeline`
after it finishes. Running them in parallel can show stale counts during a sync.

## Near-Term Priorities

- keep README and architecture docs current so new threads can resume quickly
- continue improving AI-oriented retrieval filters and response stability
- preserve importer standardization so new sources do not create ad hoc logic
- add the first write path for mobile capture input
- defer heavy UI work until the memory backend is more mature

## Next Expansions

- add future sources such as WeChat history, screenshots, and reading notes
- add mobile capture input for fresh thoughts
- attach embeddings for semantic retrieval when exact filters are no longer enough
- define a more explicit AI query protocol on top of the current API
- generate periodic summaries from your own archive
