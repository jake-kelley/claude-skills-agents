# Second Brain Skill Deployment Package

A complete, deployable package for the **Second Brain** automatic knowledge base system for Claude Code. This package allows anyone to install an exact replica of the second-brain skill with automatic capture and retrieval.

## 📦 What's Included

This package contains everything needed to deploy the second-brain skill:

```
second-brain-deploy/
├── install.py              # Main deployment script
├── manifest.json           # Skill metadata and component list
├── README.md              # This file
├── agents/
│   └── kb-extractor.md    # Subagent definition for the extractor
├── hooks/
│   ├── kb-capture.py      # Stop hook for automatic capture
│   └── kb-inject.py       # UserPromptSubmit hook for retrieval
├── skills/
│   └── second-brain/
│       ├── SKILL.md       # Skill definition
│       └── scripts/
│           ├── query.py
│           ├── show.py
│           ├── publish.py
│           ├── consolidate.py
│           ├── ingest.py
│           ├── config.py
│           ├── status.py
│           └── help.py
└── templates/
    └── second-brain/
        ├── README.md      # Template for KB README
        └── .config.json   # Default configuration
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
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
   - Install hooks to `~/.claude/hooks/`
   - Install the agent to `~/.claude/agents/`
   - Install the skill to `~/.claude/skills/`
   - Create the storage tree at `~/.claude/second-brain/`
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

Before every user prompt:
1. The user's prompt is analyzed for keywords
2. The KB is searched for relevant notes (weighted keyword matching: title 4x, tags 3x, body 1x)
3. Top 5 notes are injected as system context
4. Claude sees relevant background without explicit queries

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
├── .config.json           # Configuration (models, toggles, publish target)
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
    "ingest": "claude-haiku-4-5-20251001"
  },
  "publish": {
    "remote_url": "https://github.com/USER/REPO.wiki.git",
    "branch": "master"
  }
}
```

## 🔒 Security

- **Blocklist**: Patterns for API keys, tokens, passwords are filtered
- **Secrets never stored**: Regex patterns detect and drop sensitive data
- **Local-only by default**: No automatic cloud sync
- **Manual publish**: Only push to wiki when explicitly requested

## 🐛 Troubleshooting

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

### Retrieval not injecting

Verify `auto_inject` is enabled:
```bash
/second-brain config --show
```

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
**Version**: 1.0.0  
**Author**: jake-kelley