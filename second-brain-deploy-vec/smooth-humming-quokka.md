# Second Brain — automatic KB for Claude Code

## Context

You want a persistent, factual knowledge base that Claude Code maintains and consults *automatically*, without you invoking a tool each time. Today none of this exists in `~/.claude/` — the existing memory system there stores user prefs/feedback per project, and the existing skills (`owasp-security`, `VibeSec-Skill`) are unrelated. Clean slate, no collisions.

The intended outcome: every research result, fact, command, URL, and decision Claude encounters in a conversation is silently extracted and filed into a clean Markdown KB. On every new prompt, relevant snippets from the KB are silently injected back into context. You can query or publish the KB on demand, but the capture/retrieval loop is invisible.

## Architecture

Three surfaces, one storage tree:

| Surface | Trigger | Purpose |
|---|---|---|
| **Hook: `Stop`** | After every assistant turn (async) | Extract facts from transcript → write/update Markdown |
| **Hook: `UserPromptSubmit`** | Before every user prompt | Search KB → inject relevant notes via `additionalContext` |
| **Skill: `second-brain`** | User-invoked (`/second-brain ...`) | Query, browse, reorganize, publish |

Hooks make it *automatic*. The skill is the *manual* surface for query/publish/maintenance.

### Storage layout

```
~/.claude/second-brain/
├── README.md                  # human-facing top-level
├── INDEX.md                   # auto-regenerated table of contents
├── concepts/                  # definitions, "what is X"
├── recipes/                   # how-tos, working command sequences
├── references/                # external links, API docs, citations
├── decisions/                 # choices made + rationale
├── tools/                     # info on specific libs/CLIs/services
├── domains/<topic>/           # auto-created topical subfolders
├── .metadata/
│   ├── hashes.json            # content hashes for dedupe
│   ├── tags.json              # tag → file index
│   └── retrieval.idx          # lightweight keyword/BM25 index
└── .config.json               # publish target, blocklist, toggles
```

Every note has YAML frontmatter:

```yaml
---
id: <ulid>
title: <string>
tags: [tag1, tag2]
source: <url | transcript:<session>:<turn>>
created: 2026-04-29
updated: 2026-04-29
hash: <sha256 of body>
---
```

### Components

**1. `Stop` hook → `kb-capture.sh`** (async, runs on every turn)
- Reads `transcript_path` from hook input JSON
- Forks `claude -p --model claude-haiku-4-5-20251001` (cheapest current Haiku) with the extractor agent
- The extractor's prompt is the heart of the filter — it must capture **only NEW, settled, factual knowledge** and reject fluff:
  - REJECT: clarifying questions, in-progress thinking ("let me check..."), hedged statements, opinions, planning chatter, restated user prompts, "I'll do X next" intent
  - REJECT: anything already covered in this session's prior turns (within-session dedupe — extractor sees a list of titles already captured this session)
  - ACCEPT: definitions, working command sequences, URLs with what they contain, library/API findings, error→fix pairs, decisions with rationale, stable facts
  - Each emitted fact must carry a `source:` (URL or `transcript:<session>:<turn>`); facts without source are dropped
- Output: JSONL with `{category, title, body, tags, source}`
- For each emitted fact:
  - Compute body hash → skip if duplicate of any existing note
  - Title similarity check (token-set ratio) against existing notes in target subfolder → if >0.85, **merge** (append new info under a `## Update <date>` section) rather than create
  - Write/update Markdown file with full frontmatter
  - Update `INDEX.md` and `.metadata/retrieval.idx`
- Blocklist (regex over body): API keys, tokens, passwords, `.env`-style assignments → drop silently
- Async + `asyncRewake: false` so the main session never blocks

**2. `UserPromptSubmit` hook → `kb-inject.sh`** (sync, fast)
- Reads user prompt from stdin
- Greps/BM25 over `.metadata/retrieval.idx` for top 3–5 relevant notes
- Emits `additionalContext` with note titles + 200-char excerpts + paths (well under 10K char budget)
- Wrapped in a `<second-brain>` system reminder so Claude knows the source

**3. Skill: `~/.claude/skills/second-brain/SKILL.md`**
- `/second-brain query <q>` — full-text search, returns top matches
- `/second-brain show <path>` — open a note
- `/second-brain ingest <url|file>` — explicit capture (bypasses extractor heuristics)
- `/second-brain consolidate` — sweep tree, merge near-duplicates, regenerate INDEX
- `/second-brain publish` — push entire tree to a configured `<repo>.wiki.git` remote (works for GitHub and GitLab; both platforms expose the wiki as a separate git repo at that URL pattern). On first run, prompts for the wiki URL and writes it to `.config.json`. Uses plain `git push`; no platform-specific CLI required.
- `/second-brain config` — set publish target, toggle auto-capture, edit blocklist

**4. Headless extractor agent: `~/.claude/agents/kb-extractor.md`**
- Defined as a subagent so the Stop hook can invoke `claude -p` with a clean, narrow system prompt
- Tools restricted to: Read (transcript only), Write (KB only), Glob, Grep
- Model: `claude-haiku-4-5-20251001` (cheapest current Haiku) — pinned in the agent's frontmatter so it never silently upgrades
- Same model used for any other non-publish KB ops (consolidate, ingest); the user-facing skill commands run with whatever model the user is in

### Why this satisfies "automatic"

- Capture: `Stop` hook fires after every turn — no model invocation, deterministic
- Retrieval: `UserPromptSubmit` hook fires before every prompt — Claude sees KB context wrapped as a system reminder, just like CLAUDE.md
- You never type a command for the loop to run

### Trade-offs

| Concern | Mitigation |
|---|---|
| **Cost** — headless extractor on every turn | Pinned to `claude-haiku-4-5-20251001` (cheapest Haiku); short, structured extractor prompt; extractor returns empty JSONL when nothing new is settled, costing only a few hundred input tokens for fluff turns |
| **Latency** — extractor takes seconds | Run async; eventually-consistent capture is fine |
| **Hallucinated facts** | Extractor prompt forbids unsourced claims; every note carries `source:` frontmatter |
| **Secrets leaked to disk** | Regex blocklist (API keys, tokens, `password`, `.env` patterns); on-disk dir is local-only by default |
| **Storage bloat** | Hash-based dedupe on write; manual `consolidate` pass; retention policy in config |
| **KB drift** | `consolidate` skill regenerates INDEX and merges near-duplicates |

## Critical files to create

- `~/.claude/settings.json` — add `Stop` and `UserPromptSubmit` hook entries (will be modified, not replaced)
- `~/.claude/hooks/kb-capture.sh` (or `.ps1` for Windows-native) — Stop hook script
- `~/.claude/hooks/kb-inject.sh` — UserPromptSubmit hook script
- `~/.claude/agents/kb-extractor.md` — subagent definition for the extractor
- `~/.claude/skills/second-brain/SKILL.md` — skill entry point
- `~/.claude/skills/second-brain/scripts/` — query, publish, consolidate scripts
- `~/.claude/second-brain/` — storage tree (created on first run)
- `~/.claude/second-brain/.config.json` — publish target + toggles

## Implementation phases

1. **Scaffold storage tree + config** — create dirs, write template `INDEX.md`, `.config.json` with `auto_capture: true`, blocklist defaults
2. **Build `kb-inject.sh`** (retrieval-first — easier and validates the read path)
3. **Build extractor subagent + `kb-capture.sh`** — wire Stop hook
4. **Wire hooks into `~/.claude/settings.json`** — `Stop` + `UserPromptSubmit`, both at user scope so they apply everywhere
5. **Build the `second-brain` skill** — query/show/ingest/consolidate/publish
6. **Test** (see Verification)
7. **Publishing** — `git init` inside `~/.claude/second-brain/`, set `origin` to the user's `<repo>.wiki.git` URL, implement `publish` as a sync-and-push subcommand. First push uses `--force` (wiki is owned by the KB); subsequent pushes are fast-forward.

## Verification

- **Capture works**: Run a Claude Code session, ask "what is BM25?", let Claude answer. Check `~/.claude/second-brain/concepts/` for a new note within ~30s. Frontmatter must have valid `source:` and `hash:`.
- **Dedup works**: Ask the same question again in a new session. No new note created; `updated:` timestamp on the existing note advances.
- **Blocklist works**: Paste a fake API key into a turn. Confirm no note containing that token appears anywhere under `second-brain/`.
- **Retrieval works**: Start a fresh session, ask "remind me about BM25." Check the transcript — Claude's response should reference the stored note (and the `<second-brain>` system reminder should appear in `transcript.jsonl`).
- **Skill query works**: `/second-brain query bm25` returns the note path + excerpt.
- **Publish works**: Create a test repo on GitHub or GitLab, enable its wiki, point `.config.json` at `https://.../<repo>.wiki.git`, run `/second-brain publish`, confirm pages render in the wiki UI.
- **Cost sanity**: After 20 turns of normal use, check Anthropic usage dashboard — extractor turns should be a small fraction (Haiku, short prompts).

## Out of scope (v1)

- Vector embeddings (BM25/keyword is enough to start; can swap in later behind same `kb-inject` interface)
- Multi-user sync (single-user, single-machine)
- Real-time GitHub/GitLab wiki sync (manual `publish` only — automatic push would surprise)
- Auto-pruning by age (`consolidate` is manual)

---

## v1.1: Vector DB Migration (April 2026)

The "out of scope: vector embeddings" decision was reversed in v1.1. **Rationale:**

1. **File-scan retrieval became a bottleneck.** At ~13 notes in early use, keyword search is snappy. But testing with 10k notes showed O(n) file I/O scaling to 500ms–3s per prompt—unacceptable for a hook that blocks every interaction.

2. **Fastembed + bge-small made embeddings practical.** No PyTorch bloat (pure ONNX, ~50MB install), no API key dependency (100% offline after first model download), and out-of-the-box BAAI/bge-small-en-v1.5 quality. This removes all barriers to shipping vector search.

3. **Hybrid BM25+vector search is strictly better.** Keyword search catches exact matches; vector search catches synonyms and paraphrases. Reciprocal Rank Fusion merges both. At 10k notes, cold latency is <500ms (model load) and warm is <100ms; both acceptable for hook context injection.

4. **Architecture stays clean.** Markdown files remain canonical (never auto-deleted). The `.db/index.sqlite` is a derived cache, rebuilt anytime via `reindex.py` or `consolidate`. Publish to GitHub wiki is unchanged (dotted `.db/` dir excluded). Upgrade path is smooth: install the new scripts, let reindex build the DB on first run.

**Implementation:** See [the migration plan](../../.claude/plans/build-an-implementation-plan-squishy-wind.md) and the completed code in `/skills/second-brain/scripts/db.py`, `embed.py`, `reindex.py`, `_rrf.py`. `query.py` and `kb-inject.py` now use hybrid search. `consolidate.py` syncs the DB. All backward-compatible with v1 installs.
