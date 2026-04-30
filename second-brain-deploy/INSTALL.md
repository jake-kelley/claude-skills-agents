# Deploy the Second Brain Skill

## One-Line Install

```bash
curl -sSL https://raw.githubusercontent.com/YOUR_USERNAME/second-brain-deploy/main/install.py | python3
```

Or download and run:

```bash
git clone https://github.com/YOUR_USERNAME/second-brain-deploy.git
cd second-brain-deploy
python install.py
```

## What's Installed

- **Hooks** (`~/.claude/hooks/`): `kb-capture.py`, `kb-inject.py`
- **Agent** (`~/.claude/agents/`): `kb-extractor.md`
- **Skill** (`~/.claude/skills/`): `second-brain/` with all scripts
- **Storage** (`~/.claude/second-brain/`): Your knowledge base

## Quick Test

After installation:

```
/second-brain status
```

Then have a conversation with Claude. Facts will be captured automatically!