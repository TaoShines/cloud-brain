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

## Next Step

No urgent Gemini cleanup is required right now.

Best next move:

1. leave the current Gemini session import as-is unless real usage shows a
   specific pain point
2. if Gemini titles become annoying later, improve session title selection in:
   [`personal_brain/importers/gemini.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/importers/gemini.py)
3. otherwise continue with the broader Cloud Brain roadmap rather than spending
   more time on Gemini grouping heuristics

## Useful Commands

```bash
cd /Users/taoxuan/Desktop/cloud-brain

python3 -m personal_brain timeline --source gemini --limit 8
python3 -m personal_brain search "公式图片" --kind conversation --limit 5

sqlite3 data/personal_brain.db "
select count(*) as items from items where source_key='gemini_exports';
select count(*) as activity_items from items where source_key='gemini_exports' and item_id like 'gemini:activity:%';
select count(*) as session_items from items where source_key='gemini_exports' and item_id like 'gemini:session:%';
select count(*) as records from records where source_type='gemini';
"
```

## Git State

- branch:
  `codex-cloud-capture-auto-sync`
- latest commit for this work:
  `f6326ed` `Refine Gemini import into canonical sessions`
