# Second Brain

Automatic, factual knowledge base maintained by Claude Code.

Capture is automatic via hooks: every assistant turn fires a Haiku-powered extractor that filters out fluff (clarifying questions, in-progress thinking, opinions) and writes only **new, settled facts** as Markdown notes. Retrieval is automatic via a UserPromptSubmit hook that injects relevant notes into context.

## Layout

| Folder | Contents |
|---|---|
| `concepts/` | Definitions — "what is X" |
| `recipes/` | How-tos, working command sequences |
| `references/` | External links, API docs, citations |
| `decisions/` | Choices made and rationale |
| `tools/` | Specific libraries, CLIs, services |
| `domains/<topic>/` | Auto-created topical subfolders for larger areas |

`INDEX.md` is regenerated automatically. `.metadata/` holds the dedupe and retrieval indices. `.config.json` controls auto-capture, blocklist, and publish target.

## Skill commands

```
/second-brain query <q>         # search KB
/second-brain show <path>       # open a note
/second-brain ingest <url|file> # explicit capture
/second-brain consolidate       # merge near-dupes, regen INDEX
/second-brain publish           # push to <repo>.wiki.git
/second-brain config            # edit .config.json
```