# Cloud Brain Architecture

## Vision

Cloud Brain is not just a search tool or a diary importer.

It is a long-lived personal data layer: one place where your records can be
stored, synced, queried, and continuously refined so that both humans and AI
systems can understand you better over time.

The guiding idea is simple:

- your data should remain yours
- your memory system should outlive any single AI product
- new tools should read the same memory foundation instead of rebuilding context
- the system should get better as more life data is added

## Product Definition

Cloud Brain is a local-first memory system with three layers:

1. Source layer
   Raw information from blogs, diaries, Codex conversations, notes, bookmarks,
   reading highlights, screenshots, projects, and future sources.
2. Canonical memory layer
   A stable internal model that turns many source formats into one queryable
   memory system.
3. Access layer
   The interfaces that let humans and AI read or update the memory system:
   CLI first, then API, MCP, and UI.

## Current State

Today the project already has a working foundation:

- SQLite as the durable storage engine
- FTS5 for keyword search
- importers for blog content and Codex history
- a unified `records` layer
- CLI commands for sync, stats, search, timeline, and show

This means the system already proves the most important idea:
multiple personal data sources can be normalized into one durable personal
database.

## Core Principles

### 1. Local-first ownership

The database should remain understandable and portable without depending on a
hosted vendor service.

### 2. Stable source traceability

Every memory item should keep a path back to where it came from so you can
audit, re-import, and trust the system.

### 3. Canonical memory, not source silos

The system should not feel like a bag of disconnected importers. Source-specific
tables can exist, but the main way of reading the system should be through a
shared memory model.

### 4. Incremental evolution

The architecture should support adding new sources and new intelligence without
rewriting the foundation.

### 5. AI-readable by design

Any model should be able to retrieve relevant memory through a stable interface,
instead of relying on fragile prompt stitching.

## Target Data Model

The current `records` layer is the right first move. The next step is to evolve
it into a more explicit canonical memory model.

Recommended long-term entities:

- `sources`
  One row per connected data source or source instance.
- `items`
  The canonical unit of memory. Every imported thing becomes an item.
- `item_versions`
  Optional version history for content that changes over time.
- `item_links`
  Relationships such as "belongs to project", "mentions person", "reply to",
  "derived from", or "same topic as".
- `tags`
  Reusable classification labels.
- `search_index`
  Full-text projection for fast retrieval.
- `embeddings`
  Optional semantic vectors for similarity search later.

Recommended item fields:

- stable item id
- source type
- external source id
- item type
- title
- body
- created at
- updated at
- imported at
- checksum
- location
- parent id
- metadata json

This model gives the project three benefits:

- incremental sync becomes reliable
- deduplication becomes possible
- future AI tools can query a consistent shape regardless of original source

## Source Strategy

The system should grow by adding sources one at a time, but each new source
should map into the same memory model.

Current sources:

- blog and diary Markdown
- Codex thread metadata and message history

Recommended next sources:

- bookmarks and saved links
- reading notes and highlights
- project notes
- manually captured thoughts
- screenshots or image metadata

## Access Strategy

The project should expose one shared memory core through multiple interfaces.

### CLI

The CLI remains the fastest way to inspect and maintain the database locally.

### Read API

The next major interface should be a small local read API so that any AI or
tool can query the same database.

Recommended first endpoints:

- `GET /health`
- `GET /stats`
- `GET /timeline`
- `GET /items`
- `GET /items/{id}`
- `GET /search?q=...`

### MCP

After the read API exists, an MCP server becomes the cleanest way to let AI
clients access your memory system as a tool rather than as pasted context.

### UI

A lightweight browser UI can come later, but it should sit on top of the same
query layer instead of introducing a second data model.

## Sync Strategy

Right now sync is replace-all. That is acceptable for an early prototype but
not ideal for a long-lived memory system.

The target sync behavior should be:

- detect new items
- detect changed items
- preserve stable identifiers
- avoid unnecessary rewrites
- support partial resync per source
- record sync timestamps and import status

## Intelligence Strategy

AI features should be layered on top of the database, not mixed into the raw
storage design.

Recommended order:

1. exact retrieval
2. metadata and relationship enrichment
3. semantic retrieval with embeddings
4. periodic summaries and reviews
5. living topic pages and memory synthesis

That order matters because a memory system should become trustworthy before it
becomes "smart".

## Roadmap

### Phase 1: Stable Foundation

Goal: make the current system reliable as a reusable personal database core.

- separate shared config from local machine config
- standardize database location and boot behavior
- strengthen canonical item schema
- add sync metadata like checksum and imported timestamps
- reduce dependence on full rebuilds

### Phase 2: Shared Read Access

Goal: let any AI or script read the same brain.

- add a local read-only API
- return structured JSON for search and timeline results
- define stable ids and response shapes
- add basic filters by source, type, tag, and time range

Status:

- local read-only API now exists for `health`, `stats`, `timeline`, `items`,
  `items/{id}`, and `search`
- next improvement should focus on richer filters and API stability

### Phase 3: Richer Memory Graph

Goal: move from archive to connected memory.

- introduce entities and relationships
- link items to projects, people, and topics
- support derived summaries and synthetic notes
- add semantic retrieval

### Phase 4: Reflection Layer

Goal: turn memory into ongoing self-iteration.

- daily or weekly summaries
- topic digests
- project retrospectives
- "what changed in my thinking" style views

## What This Optimizes

Compared with the current state, this architecture improves:

- portability
  The project becomes easier to move across folders, machines, and tools.
- durability
  Your personal data model becomes less tied to one importer or workflow.
- interoperability
  Different AIs can read from one system instead of each keeping separate memory.
- iterability
  New sources and new features can be added without restructuring everything.
- trust
  Source traceability and stable ids make the database easier to inspect and
  rely on.

## Near-Term Recommendation

The best next implementation step is:

build a stronger canonical memory schema and prepare it for a read API.

That is the shortest path from "working prototype" to "real cloud brain
foundation".
