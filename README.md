# Personal Brain

A local-first personal database that now has a simple 2.0 foundation.

It starts with two sources:

- your blog/journal Markdown files
- your Codex conversation history

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

Initialize the database:

```bash
python3 -m personal_brain init
```

Sync blog entries and Codex history:

```bash
python3 -m personal_brain sync
```

View basic stats:

```bash
python3 -m personal_brain stats
```

Search across blog entries, thread titles, user questions, and assistant replies:

```bash
python3 -m personal_brain search "数据库"
python3 -m personal_brain search "Codex" --kind message
python3 -m personal_brain search "佛教" --context 120
```

Show one combined timeline across blog and Codex:

```bash
python3 -m personal_brain timeline --limit 20
python3 -m personal_brain timeline --source blog
python3 -m personal_brain timeline --type message
```

Show one record in full:

```bash
python3 -m personal_brain show "blog:src/data/blog/_2026-03-30.md"
python3 -m personal_brain show "019d403f-5817-7320-b960-4d738388d8f2:48"
```

## Current assumptions

- Blog content is imported from `/Users/taoxuan/Desktop/my-clean-blog`
- Codex history is imported from `/Users/taoxuan/.codex/state_5.sqlite`
- Detailed message content is read from the `rollout_path` recorded in Codex
  thread history

Edit [`config.json`](/Users/taoxuan/Documents/Playground/config.json) if those
paths change.

## What changed in 2.0

Compared with the first version, the main difference is that your data is no
longer only stored as separate technical tables. It is also projected into one
unified `records` layer.

That means:

- blog posts and diary entries become records
- Codex conversations become records
- individual user and assistant messages become records
- everything can now be viewed in a single timeline
- each record keeps its source location so you can trace it back

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

### `records`

A unified cross-source layer that lets you treat diaries, blog posts,
conversations, and messages as one timeline of personal data.

Each record keeps:

- a stable key
- a type
- timestamps
- the original location
- the original content

### `search_index`

An FTS5 index that unifies your searchable content for fast keyword search.

## Next expansions

- add bookmarks, screenshots, and reading notes
- attach embeddings for semantic retrieval
- generate periodic summaries from your own archive
- build a small local UI on top of the same SQLite database
