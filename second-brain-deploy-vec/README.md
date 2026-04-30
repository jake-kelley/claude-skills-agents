# Second Brain Skill Deployment Package

A complete, deployable package for the **Second Brain** automatic knowledge base system for Claude Code with hybrid vector + FTS retrieval. This package allows anyone to install an exact replica of the second-brain skill with automatic capture and intelligent hybrid search.

## 📦 What's Included

This package contains everything needed to deploy the second-brain skill:

```
second-brain-deploy/
├── install.py              # Main deployment script
├── manifest.json           # Skill metadata and component list
├── requirements.txt        # Python dependencies (sqlite-vec, fastembed)
├── README.md              # This file
├── INSTALL.md             # Detailed installation guide
├── agents/
│   └── kb-extractor.md    # Subagent definition for the extractor
├── hooks/
│   ├── kb-capture.py      # Stop hook for automatic capture & incremental indexing
│   └── kb-inject.py       # UserPromptSubmit hook for hybrid search retrieval
├── skills/
│   └── second-brain/
│       ├── SKILL.md       # Skill definition
│       └── scripts/
│           ├── db.py                    # Vector DB management (new)
│           ├── embed.py                 # Local embedding via fastembed (new)
│           ├── reindex.py               # DB rebuild from Markdown (new)
│           ├── _text.py                 # Shared text utilities (new)
│           ├── _rrf.py                  # Reciprocal Rank Fusion (new)
│           ├── query.py                 # Hybrid vector+FTS search
│           ├── show.py
│           ├── publish.py
│           ├── consolidate.py           # Now includes DB sync
│           ├── ingest.py
│           ├── config.py
│           ├── status.py                # Now shows DB stats
│           └── help.py
└── templates/
    └── second-brain/
        ├── README.md      # Template for KB README
        └── .config.json   # Default configuration with embeddings section
```

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- Claude Code CLI installed and configured
- `claude` command available in PATH

### Installation

1. **Download this package** to your machine

2. **Run the install script:**

   ```bash
   cd second-brain-deploy
   python install.py
   ```

   The script will:
   - Install Python dependencies (sqlite-vec, fastembed)
   - Install hooks to `~/.claude/hooks/`
   - Install the agent to `~/.claude/agents/`
   - Install the skill to `~/.claude/skills/` (including new DB and embedding modules)
   - Create the storage tree at `~/.claude/second-brain/` (including `.db/` for vector index)
   - Build the initial vector database from any existing notes
   - Update `~/.claude/settings.json` with hook configurations

3. **Start a new Claude Code session**

   The hooks will activate automatically:
   - **Capture**: After every assistant turn, new facts are extracted and saved
   - **Retrieval**: Before every prompt, relevant notes are injected into context

4. **Test the installation:**

   ```
   /second-brain status
   /second-brain help
   ```

## 📋 Installation Options

### Dry Run (Preview)

See what would be installed without making changes:

```bash
python install.py --dry-run
```

### Custom Claude Directory

Install to a non-standard location:

```bash
python install.py --claude-dir ~/custom/.claude
```

## 🧠 How It Works

### Automatic Capture (Stop Hook)

After every assistant turn:
1. The transcript is read
2. A Haiku-powered extractor analyzes it for new, settled facts
3. Facts are deduplicated and saved as Markdown notes with YAML frontmatter
4. The INDEX.md and metadata indices are regenerated

### Automatic Retrieval (UserPromptSubmit Hook)

Before every user prompt, using **hybrid vector + FTS search**:
1. The user's prompt is embedded using local bge-small-en-v1.5 (offline, no API calls)
2. The KB is searched in parallel via:
   - **BM25 full-text search** (FTS5) for exact keyword matches
   - **Vector KNN search** for semantic similarity across synonym and paraphrases
3. Results are merged using Reciprocal Rank Fusion (RRF) for better precision & recall
4. Top 5 notes are injected as system context, filtered by relevance threshold
5. Claude sees both exact and semantically related background without explicit queries

### Manual Skill Commands

- `/second-brain query <q>` — Search the KB
- `/second-brain show <path>` — Open a specific note
- `/second-brain ingest <url|file>` — Explicitly capture a URL or file
- `/second-brain consolidate` — Regenerate INDEX, rebuild metadata
- `/second-brain publish` — Push to GitHub/GitLab wiki
- `/second-brain config` — View/edit configuration
- `/second-brain status` — Show statistics and toggles

## 📁 Storage Layout

```
~/.claude/second-brain/
├── README.md              # Human-facing overview
├── INDEX.md               # Auto-regenerated table of contents
├── .config.json           # Configuration (models, embeddings, retrieval, publish)
├── .db/
│   └── index.sqlite       # Vector DB (sqlite-vec + FTS5 indexes) — derived cache
├── .metadata/
│   ├── hashes.json        # Content hashes for dedupe
│   └── tags.json          # Tag → file index
├── concepts/              # Definitions
├── recipes/               # How-tos, command sequences
├── references/            # External links
├── decisions/             # Choices + rationale
├── tools/                 # Libraries, CLIs, services
└── domains/<topic>/       # Topical subfolders
```

**Note:** Markdown files are the source of truth. The `.db/` directory is a derived cache (rebuilt via `reindex` or `consolidate`) and is excluded from publish.

Each note has YAML frontmatter:
```yaml
---
id: <ulid>
title: <string>
tags: [tag1, tag2]
source: <url | transcript:session:turn>
created: 2026-04-29
updated: 2026-04-29
hash: <sha256>
---
```

## ⚙️ Configuration

Edit `~/.claude/second-brain/.config.json`:

```json
{
  "auto_capture": true,      // Toggle automatic capture
  "auto_inject": true,       // Toggle automatic retrieval
  "models": {
    "extractor": "claude-haiku-4-5-20251001",
    "ingest": "claude-haiku-4-5-20251001",
    "embedder": "local:bge-small-en-v1.5"
  },
  "embeddings": {            // (NEW) Local embedding settings
    "provider": "local",
    "model": "BAAI/bge-small-en-v1.5",
    "dim": 384,
    "chunk_target_words": 500,
    "chunk_overlap_words": 50
  },
  "retrieval": {             // (EXPANDED) Hybrid search tuning
    "excerpt_chars": 200,
    "max_notes": 5,
    "max_total_chars": 8000,
    "fts_top_k": 30,         // BM25 candidates
    "vec_top_k": 30,         // Vector KNN candidates
    "rrf_k": 60,             // RRF fusion parameter
    "min_rrf_score": 0.0153  // Relevance threshold
  },
  "publish": {
    "remote_url": "https://github.com/USER/REPO.wiki.git",
    "branch": "master"
  }
}
```

**Key tuning parameters:**
- `chunk_target_words`: Split notes into ~500-word chunks for embedding (larger = more context per chunk, fewer chunks)
- `max_notes`: How many notes to inject per prompt (higher = more context, slower)
- `min_rrf_score`: Lower threshold = include more marginal matches; raise if injecting irrelevant notes
- `rrf_k`: RRF fusion parameter; 60 is standard (higher = heavier weight on rank position)

## ⚡ Performance & Embeddings

### Retrieval Speed

- **Query latency** (per-prompt): <100ms at 10k notes (vector KNN + BM25 fusion)
  - Cold start (first prompt after session): ~500ms (loads embedding model)
  - Warm (subsequent prompts): ~50ms
  - Old keyword-only system: O(n) file scan = 500ms–3s at 10k notes

- **Embedding generation**: ~50ms per prompt with local bge-small-en-v1.5 (CPU)

- **DB size**: ~2KB per chunk at 384-dim; 10k notes ≈ 100MB total

### Local Embeddings

The embedding model (BAAI/bge-small-en-v1.5) is **100% offline**:
- First use: ~30MB downloads to `~/.cache/fastembed/` (cached, one-time)
- Subsequent uses: Uses cached model, no network calls
- Fully compatible with airgapped environments

### Memory Footprint

- Model load: ~100MB RAM (first call)
- DB query: ~10MB working set (in-process sqlite-vec)

## 🔒 Security

- **Blocklist**: Patterns for API keys, tokens, passwords are filtered
- **Secrets never stored**: Regex patterns detect and drop sensitive data
- **Local-only by default**: No automatic cloud sync
- **Manual publish**: Only push to wiki when explicitly requested

## 🐛 Troubleshooting

### First prompt is slow (~500ms)

This is normal. The embedding model loads on first use. Subsequent prompts are fast (~50ms).

### Vector DB not initialized

Run:
```bash
/second-brain reindex
```

This builds the DB from existing Markdown notes.

### "DB out of sync" warning

Run:
```bash
/second-brain consolidate
```

This syncs the DB with any manual edits to `.md` files.

### fastembed import fails

Install the dependency:
```bash
pip install fastembed>=0.3.0
```

Or let the install script handle it (it runs `pip install` automatically).

### Retrieval injecting irrelevant notes

Adjust in `.config.json`:
- Raise `min_rrf_score` (e.g., 0.02 instead of 0.0153) to be more strict
- Lower `max_notes` (e.g., 3 instead of 5) to inject fewer notes
- Lower `chunk_target_words` to make chunks more granular

### Hooks not firing

Check `~/.claude/settings.json`:
```bash
cat ~/.claude/settings.json | grep -A5 "hooks"
```

### Capture not working

Check the log:
```bash
tail ~/.claude/hooks/kb-capture.log
```

Also check that Python dependencies are installed:
```bash
python -c "import sqlite_vec; import fastembed; print('OK')"
```

### Slow queries or KNN errors

Ensure the DB exists:
```bash
ls -lh ~/.claude/second-brain/.db/index.sqlite
```

If missing, run `/second-brain reindex`.

## 📝 Design Document

For the complete design specification, see `smooth-humming-quokka.md` (the original plan that created this system).

## 🤝 Sharing Your KB

### Method 1: GitHub/GitLab Wiki

```
/second-brain publish --set-remote https://github.com/USER/REPO.wiki.git
/second-brain publish --force
```

### Method 2: Share the Deployment Package

1. Zip this `second-brain-deploy/` directory
2. Share with others
3. They run `python install.py`

### Method 3: Copy KB Contents

The `~/.claude/second-brain/` directory is plain Markdown - copy it anywhere.

## 📄 License

This deployment package is provided as-is for personal use with Claude Code.

## 🔗 Related

- [Claude Code Documentation](https://docs.anthropic.com/en/docs/claude-code)
- [Claude Code Settings Schema](https://json.schemastore.org/claude-code-settings.json)

---

**Created**: 2026-04-29  
**Version**: 1.1.0 (vector DB with hybrid search)  
**Author**: jake-kelley