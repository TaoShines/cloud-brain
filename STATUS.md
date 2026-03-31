# Current Status

This file is a short handoff note for resuming work in a new thread or window.

## What Was Done Today

### 1. Cloud capture auto-sync was finished

- added a dedicated cloud-only sync command:
  `python3 -m personal_brain sync-cloud-capture`
- factored sync logic into:
  [`personal_brain/sync.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/sync.py)
- local API startup now triggers cloud-capture sync automatically
- `/health` now reports cloud auto-sync status
- installed a macOS `launchd` job on this machine for daily cloud-capture sync
- current installed LaunchAgent:
  [`/Users/taoxuan/Library/LaunchAgents/com.taoxuan.cloud-brain-sync.plist`](/Users/taoxuan/Library/LaunchAgents/com.taoxuan.cloud-brain-sync.plist)
- repo copy of the LaunchAgent:
  [`launchd/com.taoxuan.cloud-brain-sync.plist`](/Users/taoxuan/Desktop/cloud-brain/launchd/com.taoxuan.cloud-brain-sync.plist)

### 2. Gemini import support was added

- added a new importer for Gemini exports:
  [`personal_brain/importers/gemini.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/importers/gemini.py)
- added `gemini_export_path` config support in:
  [`personal_brain/config.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/config.py)
- wired Gemini into the importer registry:
  [`personal_brain/importers/__init__.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/importers/__init__.py)
- `timeline --source gemini` now works
- current behavior:
  Gemini Google Takeout activity HTML is parsed into canonical session-style
  `conversation` items
- real Gemini data has now been imported from:
  `/Users/taoxuan/Desktop/cloud-brain/data/gemini_exports/Gemini Apps/我的活动记录.html`
- current local database result:
  614 Gemini session items
- important transition rule:
  while Gemini import format is still being refined, `gemini_exports` is
  hard-replaced during sync so the database does not keep duplicate old Gemini
  import formats

### 3. Deletion safety for the personal database was improved

- confirmed bookmarks already behaved as historical records:
  removed bookmarks become `status=deleted` with `deleted_at`
- fixed the main `items` sync path so missing source items are no longer
  physically deleted during normal sync
- missing items are now marked as:
  - `metadata.status = "deleted"`
  - `metadata.deleted_at = ...`
- `items` and `records` are now upserted instead of delete-and-rebuild for
  source-scoped sync
- main implementation is in:
  [`personal_brain/database.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/database.py)

### 4. Blog template posts were removed from the database

- discovered that the blog importer was pulling AstroPaper template documents
- added exclusion rules for template posts and example docs
- current default exclusions are configured through:
  `blog_exclude_globs`
- implementation is in:
  [`personal_brain/importers/blog.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/importers/blog.py)
- config support is in:
  [`personal_brain/config.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/config.py)
- example config was updated in:
  [`config.local.example.json`](/Users/taoxuan/Desktop/cloud-brain/config.local.example.json)
- confirmed blog import is now down to 7 real documents
- kept `my-first-post.md` because the user explicitly confirmed it is their own post

### 5. README was updated

- added Gemini import instructions
- refreshed outdated sync notes
- current README:
  [`README.md`](/Users/taoxuan/Desktop/cloud-brain/README.md)

### 6. Schema migrations and sync run metadata were added

- database initialization now applies tracked schema migrations through:
  [`personal_brain/database.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/database.py)
- applied migrations are stored in:
  `schema_migrations`
- sync execution metadata is now stored in:
  `sync_runs`
- each top-level sync now records:
  - start and finish time
  - success or failure status
  - per-source child runs
  - per-run counts and error messages
- CLI inspection commands now exist:
  - `python3 -m personal_brain migrations`
  - `python3 -m personal_brain sync-runs --limit 10`
- API inspection endpoints now exist:
  - `GET /migrations`
  - `GET /sync-runs`

## Current Behavior

### Cloud capture

- phone/public capture goes into Cloudflare D1
- local SQLite syncs cloud capture back through:
  `python3 -m personal_brain sync-cloud-capture`
- local API auto-syncs cloud capture on startup and then on a daily interval
- `launchd` also runs the cloud-capture sync daily at 02:00

### Blog / Codex / cloud capture items

- these sources now preserve historical items in the local memory database
- if a source item disappears later, the local memory item is kept and marked
  `deleted` instead of being physically removed

### Schema and sync metadata

- schema upgrades are now tracked in `schema_migrations`
- sync history is now queryable in `sync_runs`
- `sync_configured_sources` writes one root run and one child run per source
- `sync_cloud_capture_to_local` writes its own sync run entry

### Gemini

- Gemini is currently a special case during importer iteration
- the database keeps one canonical Gemini import format at a time
- old Gemini import shapes are not preserved side-by-side
- this avoids duplicate Gemini records while the importer is still evolving

### Bookmarks

- bookmarks already preserve interest history
- removed bookmarks remain in the database with `status=deleted` and `deleted_at`

## Important Files

- sync core:
  [`personal_brain/sync.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/sync.py)
- local API:
  [`personal_brain/api.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/api.py)
- database behavior:
  [`personal_brain/database.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/database.py)
- sync orchestration:
  [`personal_brain/sync.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/sync.py)
- importer registry:
  [`personal_brain/importers/__init__.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/importers/__init__.py)
- blog importer:
  [`personal_brain/importers/blog.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/importers/blog.py)
- Gemini importer:
  [`personal_brain/importers/gemini.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/importers/gemini.py)
- config:
  [`personal_brain/config.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/config.py)
- example local config:
  [`config.local.example.json`](/Users/taoxuan/Desktop/cloud-brain/config.local.example.json)

## Git Status

These changes were already committed and pushed to GitHub on branch:

- `codex-cloud-capture-auto-sync`

Recent commits:

- `53bd38e` Preserve deleted items and filter template blog posts
- `2c0054d` Add Gemini import support and refresh README
- `2fcefa2` Add automatic cloud capture sync

## What Is Not Done Yet

- Gemini importer still does not recover true Gemini-native thread ids from
  Google activity export
- Gemini session grouping is heuristic rather than based on an official thread
  identifier
- there is still no long-term cloud main database
- the architecture is still transitional:
  cloud capture in D1, everything else centered on local SQLite

## Best Next Step

Continue strengthening infrastructure instead of adding opinionated topic logic.

Recommended next action:

1. inspect migration and sync metadata locally
2. keep the canonical item schema stable
3. if needed next, add more operational metadata such as:
   - sync duration
   - source-level warnings
   - source checksums or import snapshots
4. only after the database contract feels stable, consider higher-level AI
   retrieval layers

## Longer-Term Direction

The user has now clarified a stronger product goal:

- this should be a true personal database that tends to grow over time
- deleting source files later should not erase historical meaning from the database
- eventually the main database should move to the cloud rather than stay local-only

Detailed architecture context still lives in:

- [`ARCHITECTURE.md`](/Users/taoxuan/Desktop/cloud-brain/ARCHITECTURE.md)
- [`CLOUD_ARCHITECTURE.md`](/Users/taoxuan/Desktop/cloud-brain/CLOUD_ARCHITECTURE.md)

## Recommended Next Prompt

In the next window, start with:

`Read STATUS.md, CLOUD_ARCHITECTURE.md, and ARCHITECTURE.md, then continue from the current handoff. First check whether the Google Gemini export has arrived, then wire real Gemini export files into the database.`

## Useful Local Commands

Check cloud capture:

```bash
launchctl list com.taoxuan.cloud-brain-sync
python3 -m personal_brain sync-cloud-capture
python3 -m personal_brain timeline --limit 10 --type capture
```

Check blog content:

```bash
python3 -m personal_brain timeline --source blog --limit 20
python3 -m personal_brain search "Cloud Brain" --kind blog --show-full
```

Check Gemini imports:

```bash
python3 -m personal_brain sync
python3 -m personal_brain timeline --source gemini --limit 10
python3 -m personal_brain search "公式图片" --kind conversation --limit 5
sqlite3 data/personal_brain.db "select count(*) from items where source_key='gemini_exports';"
```

Check schema and sync infrastructure:

```bash
python3 -m personal_brain migrations
python3 -m personal_brain sync-runs --limit 10
sqlite3 data/personal_brain.db "select id, sync_type, source_key, status, started_at, finished_at from sync_runs order by id desc limit 10;"
```
