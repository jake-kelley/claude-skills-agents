# Deploy the Second Brain Skill

## Prerequisites

- **Python 3.9+** (required for sqlite-vec and fastembed)
- **Claude Code CLI** installed and configured
- **Internet connection** (for initial dependency installation and embedding model download)
  - Embedding model (~30MB) downloads to `~/.cache/fastembed/` on first use, then works offline

## Installation

### Standard Install

```bash
git clone https://github.com/YOUR_USERNAME/second-brain-deploy.git
cd second-brain-deploy
python install.py
```

During installation, you'll be prompted to select a model for knowledge base operations:

```
🤖 Select model for knowledge base operations:
   (Used for extracting facts and ingesting content)

   1. Haiku 4.5 (fastest, cheapest, recommended)
   2. Sonnet 4.6 (balanced)
   3. Opus 4.7 (most capable, expensive)
   4. Enter a custom model ID

Enter your choice [1-4] (default: 1):
```

The selected model will be used for fact extraction and content ingestion operations.

**During installation**, the script will automatically install required Python packages:
- `sqlite-vec>=0.1.6` - Vector database engine
- `fastembed>=0.3.0` - Local ONNX embeddings for offline semantic search

If `pip install` fails, you can install manually:
```bash
pip install sqlite-vec fastembed
```

### Existing Hooks Handling

If you already have hooks configured for `UserPromptSubmit` or `Stop` events, the installer will detect them and prompt you:

```
⚠️  Existing UserPromptSubmit hooks detected (2 hook(s))
   The second-brain skill needs to add its hook to UserPromptSubmit.

   Options:
   1. Append - Add second-brain hook, keep existing hooks (recommended)
   2. Replace - Replace all hooks with only second-brain hook
   3. Skip - Don't modify this hook (skill may not work correctly)

   Enter your choice [1-3] (default: 1):
```

**Recommended**: Choose option 1 (Append) to preserve your existing hooks while adding the second-brain functionality.

### Advanced Options

**Preview installation without making changes:**
```bash
python install.py --dry-run
```

**Install to a custom location:**
```bash
python install.py --claude-dir ~/custom/.claude
```

**Combine options:**
```bash
python install.py --dry-run --claude-dir ~/custom/.claude
```

## First Run: Embedding Model Download

On your first query or prompt after installation:
1. The `bge-small-en-v1.5` embedding model (~30MB) will download to `~/.cache/fastembed/`
2. This is a one-time download; subsequent runs use the cached model
3. This happens automatically and silently (may take 10–30s the first time)
4. All processing is **100% offline** after this download

This enables fast, local semantic search without any API calls or cloud dependencies.

## What Gets Installed

The installer creates the following structure in your `~/.claude/` directory:

- **Hooks** (`~/.claude/hooks/`):
  - `kb-capture.py` - Extracts facts after each assistant turn
  - `kb-inject.py` - Injects relevant notes before each user prompt
  - ⚠️ **Note**: Only these two files are copied. Your other hook files are preserved.

- **Agent** (`~/.claude/agents/`):
  - `kb-extractor.md` - Agent definition for knowledge extraction
  - ⚠️ **Note**: Only this file is copied. Your other agent files are preserved.

- **Skill** (`~/.claude/skills/second-brain/`):
  - `SKILL.md` - Main skill definition
  - `scripts/` - Includes:
    - **New**: `db.py`, `embed.py`, `reindex.py`, `_text.py`, `_rrf.py` (vector DB and embeddings)
    - Updated: `query.py` (hybrid search), `consolidate.py` (DB sync), `status.py` (DB stats)
    - Original: `show.py`, `publish.py`, `ingest.py`, `config.py`, `help.py`
  - ⚠️ **Note**: Only the `second-brain/` directory is affected. Your other skills are preserved.

- **Storage** (`~/.claude/second-brain/`):
  - Category folders: `concepts/`, `recipes/`, `references/`, `decisions/`, `tools/`, `domains/`
  - **New**: `.db/` directory containing `index.sqlite` (vector database with FTS5 indexes)
  - `.config.json` - Configuration including selected model and embeddings settings (only copied if doesn't exist)
  - `.metadata/` - Internal metadata storage
  - `README.md` - Knowledge base documentation (only copied if doesn't exist)
  - ✓ **Your existing knowledge base content is never touched**
  - ✓ **The `.db/` directory is a derived cache** and can be rebuilt anytime via `/second-brain reindex`

- **Settings** (`~/.claude/settings.json`):
  - Hook configurations for automatic capture and injection
  - ⚠️ **Note**: Existing hooks for other events are preserved. You'll be prompted if `UserPromptSubmit` or `Stop` hooks already exist.

## Verification

The installer automatically verifies that all components are installed correctly. You should see:

```
🔍 Verifying installation...
  ✓ settings.json
  ✓ hooks/kb-capture.py
  ✓ hooks/kb-inject.py
  ✓ agents/kb-extractor.md
  ✓ skills/second-brain/SKILL.md
  ✓ second-brain/.config.json
```

## Quick Test

After installation, start a new Claude Code session and test:

```
/second-brain status
```

You should see:
- Knowledge base statistics (notes per category)
- **Vector DB stats** (indexed notes, chunks, embeddings)
- Configuration (auto-capture, auto-inject, models, publish target)

```
/second-brain help
```

This displays all available commands and usage examples.

## How It Works

Once installed, the system operates automatically:

1. **Capture**: After each assistant turn, the `kb-capture.py` hook extracts factual knowledge and saves it to `~/.claude/second-brain/` as Markdown files
2. **Inject**: Before each user prompt, the `kb-inject.py` hook searches your knowledge base and injects relevant notes into the context

No manual intervention required - just have conversations with Claude!

## Optional: Configure Publishing

To push your knowledge base to a GitHub wiki:

```
/second-brain publish --set-remote https://github.com/YOU/REPO.wiki.git
/second-brain publish --force
```

## Troubleshooting

### Installation Issues

**Missing manifest.json error:**
Make sure you're running `install.py` from the `second-brain-deploy` directory.

**Permission errors:**
The installer will automatically make hook and script files executable on Unix systems.

**pip install failed:**
If the dependency installation fails, you can install manually:
```bash
pip install sqlite-vec fastembeat
```
Then start a new Claude Code session.

**Python version mismatch:**
Verify you're using Python 3.9+:
```bash
python --version
```
If needed, use `python3.9` or `python3.10` explicitly.

### Runtime Issues

**Custom model not working:**
Verify your model ID format. Government cloud example: `us-gov.anthropic.claude-sonnet-4-5-20250929-v1:0`

**Hooks not running:**
Restart your Claude Code session after installation to activate the hooks.

**Vector DB not initialized:**
The DB is built automatically during install. If it's missing, run:
```bash
/second-brain reindex
```

**First prompt is slow (~500ms):**
This is normal—the embedding model loads on first use. Subsequent prompts are fast (~50ms).

**"Can't find sqlite_vec" error:**
The sqlite-vec extension isn't loaded. Ensure `pip install sqlite-vec` succeeded and restart your session.

**Embedding model download fails:**
The embedding model requires internet on first use. If your network is restricted:
- Ensure `~/.cache/fastembed/` is writable
- Check internet connectivity
- Try again—the download is only needed once

**Skipped hook configuration:**
If you chose "Skip" during installation, the skill won't work automatically. To manually add the hooks later, edit `~/.claude/settings.json` and add:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/kb-inject.py",
            "timeout": 10
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/kb-capture.py",
            "timeout": 600,
            "async": true
          }
        ]
      }
    ]
  }
}
```

**Re-running installation:**
The installer detects if second-brain hooks are already configured and won't prompt again. To reconfigure, manually remove the hooks from `settings.json` first, or edit the file directly.