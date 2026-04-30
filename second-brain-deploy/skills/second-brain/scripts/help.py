#!/usr/bin/env python
"""Print detailed help for the second-brain skill."""
import sys

HELP = """
==============================================================================
              SECOND BRAIN - Knowledge Base for Claude Code
==============================================================================

Automatic capture (Stop hook) + retrieval (UserPromptSubmit hook) + manual skill.

==============================================================================
QUERIES & BROWSING
==============================================================================

  /second-brain query <q>
    Search the KB for <q>. Returns top 8 matches.

  /second-brain show <path>
    Open a note. E.g.: /second-brain show concepts/bm25.md

  /second-brain status
    Show counts per category, publish target, toggles.

==============================================================================
CAPTURE & INGEST
==============================================================================

  /second-brain ingest <url>
    Capture a URL or local file as a KB note.
    E.g.: /second-brain ingest https://example.com/docs

  Auto-capture happens silently after every assistant turn (Stop hook).
  The extractor filters out fluff: clarifying questions, in-progress thinking,
  hedges, opinions. Only settled, NEW facts are captured.

==============================================================================
MAINTENANCE
==============================================================================

  /second-brain consolidate
    Regenerate INDEX.md, rebuild metadata, find dupes.

  /second-brain config --show
    Show current config (.config.json).

  /second-brain config --set-model <op> <model>
    Set model for extractor|ingest. Default: haiku.
    E.g.: /second-brain config --set-model extractor opus

  /second-brain config --toggle-capture
    Toggle auto_capture on/off.

  /second-brain config --toggle-inject
    Toggle auto_inject (retrieval) on/off.

==============================================================================
PUBLISHING
==============================================================================

  /second-brain publish --set-remote <URL>
    Point to wiki.git URL (GitHub or GitLab).
    E.g.: https://github.com/you/repo.wiki.git
    Run once to configure.

  /second-brain publish --force
    Force-push (first time only; KB owns the wiki).

  /second-brain publish
    Normal commit-and-push after force (subsequent).

==============================================================================
CATEGORIES
==============================================================================

  concepts/         Definitions, explanations ("what is X")
  recipes/          How-tos, working command sequences, code patterns
  references/       External links, API docs, citations
  decisions/        Choices made + rationale
  tools/            Specific libraries, CLIs, services, APIs
  domains/<topic>/  Larger topical areas (auto-created)

==============================================================================
MODELS
==============================================================================

  Default: claude-haiku-4-5-20251001 (cheapest)

  Change per operation:
    /second-brain config --set-model extractor claude-opus-4-7
    /second-brain config --set-model ingest claude-sonnet-4-6

  Supported aliases: haiku, sonnet, opus, or full model IDs.

==============================================================================
HOW IT WORKS
==============================================================================

  AUTOMATIC CAPTURE (Stop hook, async, after every turn):
    1. Reads transcript of just-finished assistant response
    2. Spawns Haiku extractor -> emits JSONL of new facts
    3. Python deduplicates (by hash + title similarity)
    4. Writes/merges Markdown notes with frontmatter
    5. Regenerates INDEX.md and metadata indices

  AUTOMATIC RETRIEVAL (UserPromptSubmit hook, sync, before every prompt):
    1. Keyword-scores KB against user's prompt
    2. Top 5 notes injected as system reminder <second-brain> tag
    3. You see relevant notes in context, cite them if useful

  MANUAL (skill commands):
    Query, browse, ingest URLs, consolidate, publish to GitHub/GitLab wiki.

==============================================================================
LOGS & CONFIG
==============================================================================

  Capture log:     ~/.claude/hooks/kb-capture.log
  KB root:         ~/.claude/second-brain/
  Config file:     ~/.claude/second-brain/.config.json
  Hooks config:    ~/.claude/settings.json (Stop + UserPromptSubmit)

==============================================================================
"""

sys.stdout.write(HELP)