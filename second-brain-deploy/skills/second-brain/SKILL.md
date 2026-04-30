---
name: second-brain
description: Manage the user's automatic Markdown knowledge base at ~/.claude/second-brain/. Use when the user asks to query, show, ingest, consolidate, or publish their second brain — or asks "what do I have on X" / "search my notes" / "publish my KB". Capture and retrieval happen automatically via hooks; this skill is for explicit operations.
---

# Second Brain skill

The user has an automatic Markdown knowledge base at `~/.claude/second-brain/`, maintained by the Stop and UserPromptSubmit hooks. This skill is the manual interface for querying, browsing, ingesting, consolidating, and publishing it.

Capture/retrieval are automatic and silent — **do not** invoke this skill for normal Q&A. Only invoke when the user explicitly wants to interact with the KB.

## Subcommands

Route on the first word of the args after `/second-brain`:

| Subcommand | What to do |
|---|---|
| `query <q>` or no subcommand with text | Run `python <SKILL_DIR>/scripts/query.py "<q>"` and report top matches with paths and excerpts |
| `show <path>` | Read the file at `~/.claude/second-brain/<path>` and print it cleanly |
| `ingest <url-or-path>` | Run `python <SKILL_DIR>/scripts/ingest.py "<arg>"` to capture a URL or local file as a KB note |
| `consolidate` | Run `python <SKILL_DIR>/scripts/consolidate.py` — regenerates INDEX, rebuilds metadata, reports near-duplicates |
| `publish` | Run `python <SKILL_DIR>/scripts/publish.py` — commits and pushes to the configured `<repo>.wiki.git` remote |
| `config` | Read `~/.claude/second-brain/.config.json`, ask user what to change, then update it |
| `config --set-model <op> <model>` | Set the model for a specific operation (extractor, ingest). E.g. `config --set-model extractor claude-opus-4-7` |
| `status` | Show counts (notes per category), publish target, auto-capture toggle |
| `help` or (no args) | Show detailed help (all subcommands, examples, how it works) |

## Layout reference

```
~/.claude/second-brain/
├── concepts/      definitions
├── recipes/       how-tos, working command sequences
├── references/    external links
├── decisions/     choices + rationale
├── tools/         libs, CLIs, services
├── domains/       topical subfolders
├── INDEX.md       auto-regenerated TOC
└── .config.json   publish target, blocklist, toggles
```

## Model configuration

Each operation uses a configurable model for flexibility:

```json
"models": {
  "extractor": "claude-haiku-4-5-20251001",
  "ingest": "claude-haiku-4-5-20251001"
}
```

- **extractor** — used by `kb-capture.py` (Stop hook) and the agent. Default: Haiku 4.5 (cheapest).
- **ingest** — used by `python ingest.py`. Default: Haiku 4.5.

Change via: `/second-brain config --set-model extractor <model-id>` or edit `.config.json` directly.

Supported model IDs: `claude-haiku-4-5-20251001`, `claude-sonnet-4-6`, `claude-opus-4-7`, or any alias like `haiku`, `sonnet`, `opus`.

## When the user asks for `publish` for the first time

If `.config.json`'s `publish.remote_url` is empty, ask the user for their `<repo>.wiki.git` URL (works for both GitHub and GitLab — both expose the wiki as a separate git repo at that URL pattern). Save it to `.config.json`. Then run the publish script.

## Routing help requests

When the user runs `/second-brain` with no arguments, or asks for `/second-brain help`:
- Run `python <SKILL_DIR>/scripts/help.py`
- Print the output verbatim

## Notes on output

- For `query`: list at most 8 results. For each, show **title** — `path` — 1-line excerpt.
- For `show`: print the body without the YAML frontmatter unless the user asks to see it.
- For `consolidate`: report what changed (counts only, not full diffs).
- For `publish`: report the commit SHA and remote URL it pushed to.
- For `help`: invoke help.py and print its output.