# Next Window README

This file is a short handoff for continuing work in a new window.

## What Was Done

### 1. Gemini import now uses one canonical database format

- real Gemini data was imported from:
  `/Users/taoxuan/Desktop/cloud-brain/data/gemini_exports/Gemini Apps/我的活动记录.html`
- the Gemini importer was upgraded in:
  [`personal_brain/importers/gemini.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/importers/gemini.py)
- it now parses the Google My Activity export directly
- it groups nearby Gemini activities into canonical session-style
  `conversation` items
- generated-image steps and attached files are preserved in the session body
  and metadata

### 2. Duplicate Gemini formats are no longer kept in the database

- during Gemini importer iteration, `gemini_exports` is treated as a
  hard-replace source
- old Gemini import shapes are purged before writing the new one
- this behavior is wired in:
  [`personal_brain/sync.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/sync.py)
- source-specific purge support was added in:
  [`personal_brain/database.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/database.py)

### 3. Timeline and search now show the current canonical items

- `timeline` now reads from canonical `items` instead of the legacy `records`
  view
- `timeline`, `list_items`, and `search_items` now default to excluding
  `metadata.status = "deleted"`
- implementation is in:
  [`personal_brain/database.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/database.py)

### 4. Documentation was updated

- README now reflects the current Gemini import behavior:
  [`README.md`](/Users/taoxuan/Desktop/cloud-brain/README.md)
- status handoff was refreshed:
  [`STATUS.md`](/Users/taoxuan/Desktop/cloud-brain/STATUS.md)

### 5. Schema evolution and sync execution are now tracked

- database init now applies tracked migrations through:
  [`personal_brain/database.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/database.py)
- applied migrations are stored in:
  `schema_migrations`
- sync execution metadata is stored in:
  `sync_runs`
- `sync_configured_sources` now writes:
  - one root run for the whole sync
  - one child run per source
- `sync_cloud_capture_to_local` writes its own run entry too
- CLI inspection commands:
  - `python3 -m personal_brain migrations`
  - `python3 -m personal_brain sync-runs --limit 10`
- API endpoints:
  - `GET /migrations`
  - `GET /sync-runs`

### 6. Canonical item metadata is now normalized

- item metadata now follows one shared shape
- stable top-level metadata keys are:
  - `metadata_schema_version`
  - `status`
  - `deleted_at`
  - `domain`
  - `source_details`
- source-specific details are nested under `source_details`
- normalization is applied during database init in:
  [`personal_brain/database.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/database.py)
- README now documents this contract:
  [`README.md`](/Users/taoxuan/Desktop/cloud-brain/README.md)

### 7. Source health view now exists

- sync runs now expose duration and warnings fields
- CLI command:
  `python3 -m personal_brain source-health`
- API endpoint:
  `GET /source-health`
- current source health view is based on:
  - latest source-level sync run
  - latest successful sync time
  - latest error message
  - latest per-source counts

## Current Verified State

Local verification completed:

- `python3 -m personal_brain timeline --source gemini --limit 8`
  returns only `gemini:session:...` items
- `python3 -m personal_brain search "公式图片" --kind conversation --limit 5`
  finds the expected Gemini session
- SQLite counts are now:
  - `items where source_key='gemini_exports'`: `614`
  - `items where item_id like 'gemini:activity:%'`: `0`
  - `items where item_id like 'gemini:session:%'`: `614`
  - `records where source_type='gemini'`: `614`
  - `schema_migrations`: `2`
  - `sync_runs` after one full sync: `6`

## Next Step

No urgent Gemini cleanup is required right now.

Best next move:

1. keep focusing on infrastructure rather than topic modeling
2. use `schema_migrations` and `sync_runs` as the base for future evolution
3. if continuing infrastructure work, likely next improvements are:
   - sync duration and warning fields
   - source-level health views
   - stronger migration ergonomics

## Useful Commands

```bash
cd /Users/taoxuan/Desktop/cloud-brain

python3 -m personal_brain timeline --source gemini --limit 8
python3 -m personal_brain search "公式图片" --kind conversation --limit 5
python3 -m personal_brain migrations
python3 -m personal_brain sync-runs --limit 10

sqlite3 data/personal_brain.db "
select count(*) as items from items where source_key='gemini_exports';
select count(*) as activity_items from items where source_key='gemini_exports' and item_id like 'gemini:activity:%';
select count(*) as session_items from items where source_key='gemini_exports' and item_id like 'gemini:session:%';
select count(*) as records from records where source_type='gemini';
select count(*) as migrations from schema_migrations;
select count(*) as sync_runs from sync_runs;
"
```

## Git State

- branch:
  `codex-cloud-capture-auto-sync`
- latest commit for this work:
  working tree has uncommitted infrastructure updates for migrations and
  sync run tracking
