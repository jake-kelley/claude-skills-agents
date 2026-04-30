#!/usr/bin/env python3
"""
Second Brain Skill Deployment Script

Installs the complete second-brain knowledge base system for Claude Code.
Run this script to deploy an exact replica of the skill.

Usage:
    python install.py [--dry-run] [--claude-dir PATH]

Options:
    --dry-run       Show what would be installed without making changes
    --claude-dir    Specify custom Claude config directory (default: ~/.claude)
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Optional


def get_claude_dir(args) -> Path:
    """Get the Claude config directory."""
    if args.claude_dir:
        return Path(args.claude_dir).expanduser().resolve()
    return Path.home() / ".claude"


def get_source_dir() -> Path:
    """Get the directory containing this script (the deploy package)."""
    return Path(__file__).parent.resolve()


def ensure_dir(path: Path, dry_run: bool = False) -> None:
    """Create directory if it doesn't exist."""
    if dry_run:
        print(f"  [DRY-RUN] Would create directory: {path}")
        return
    path.mkdir(parents=True, exist_ok=True)
    print(f"  ✓ Directory ready: {path}")


def copy_file(src: Path, dst: Path, dry_run: bool = False) -> None:
    """Copy a file from src to dst."""
    if dry_run:
        print(f"  [DRY-RUN] Would copy: {src} -> {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"  ✓ Copied: {dst.name}")


def load_json(path: Path) -> dict:
    """Load JSON file or return empty dict."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_json(path: Path, data: dict, dry_run: bool = False) -> None:
    """Save data to JSON file."""
    if dry_run:
        print(f"  [DRY-RUN] Would write JSON: {path}")
        return
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"  ✓ Updated: {path.name}")


def get_python_executable() -> str:
    """Get the Python executable path."""
    return sys.executable


def make_executable(path: Path) -> None:
    """Make a file executable (Unix only)."""
    if os.name != 'nt':  # Not Windows
        os.chmod(path, 0o755)


def check_existing_hooks(settings: dict, hook_name: str, script_name: str) -> bool:
    """Check if a specific second-brain hook already exists."""
    if "hooks" not in settings or hook_name not in settings["hooks"]:
        return False

    for hook_group in settings["hooks"][hook_name]:
        if "hooks" in hook_group:
            for hook in hook_group["hooks"]:
                if hook.get("type") == "command" and script_name in str(hook.get("command", "")):
                    return True
    return False


def prompt_hook_action(hook_name: str, existing_count: int) -> str:
    """Prompt user for action when existing hooks are detected."""
    print(f"\n⚠️  Existing {hook_name} hooks detected ({existing_count} hook(s))")
    print(f"   The second-brain skill needs to add its hook to {hook_name}.")
    print()
    print("   Options:")
    print("   1. Append - Add second-brain hook, keep existing hooks (recommended)")
    print("   2. Replace - Replace all hooks with only second-brain hook")
    print("   3. Skip - Don't modify this hook (skill may not work correctly)")
    print()

    while True:
        choice = input("   Enter your choice [1-3] (default: 1): ").strip() or "1"
        if choice in ["1", "2", "3"]:
            return {"1": "append", "2": "replace", "3": "skip"}[choice]
        print("   Invalid choice. Please enter 1-3.")


def update_settings_json(claude_dir: Path, source_dir: Path, dry_run: bool = False) -> None:
    """Update settings.json with hook configurations."""
    settings_path = claude_dir / "settings.json"

    # Load existing settings or create new
    settings = load_json(settings_path)

    # Ensure hooks section exists
    if "hooks" not in settings:
        settings["hooks"] = {}

    hooks_dir = claude_dir / "hooks"

    # Define the hooks we want to add
    kb_inject_hook = {
        "hooks": [
            {
                "type": "command",
                "command": f"{get_python_executable()} {hooks_dir / 'kb-inject.py'}",
                "timeout": 10
            }
        ]
    }

    kb_capture_hook = {
        "hooks": [
            {
                "type": "command",
                "command": f"{get_python_executable()} {hooks_dir / 'kb-capture.py'}",
                "timeout": 600,
                "async": True
            }
        ]
    }

    # Process UserPromptSubmit hook
    if not check_existing_hooks(settings, "UserPromptSubmit", "kb-inject.py"):
        existing_hooks = settings["hooks"].get("UserPromptSubmit", [])

        if existing_hooks and not dry_run:
            action = prompt_hook_action("UserPromptSubmit", len(existing_hooks))
            if action == "append":
                settings["hooks"]["UserPromptSubmit"] = existing_hooks + [kb_inject_hook]
                print("   ✓ Appended kb-inject.py hook to UserPromptSubmit")
            elif action == "replace":
                settings["hooks"]["UserPromptSubmit"] = [kb_inject_hook]
                print("   ✓ Replaced UserPromptSubmit hooks with kb-inject.py")
            else:  # skip
                print("   ⊘ Skipped UserPromptSubmit hook modification")
        else:
            # No existing hooks or dry run - just set it
            settings["hooks"]["UserPromptSubmit"] = [kb_inject_hook]
            if not dry_run:
                print("   ✓ Configured UserPromptSubmit hook")
    else:
        print("   ⊘ kb-inject.py hook already exists in UserPromptSubmit")

    # Process Stop hook
    if not check_existing_hooks(settings, "Stop", "kb-capture.py"):
        existing_hooks = settings["hooks"].get("Stop", [])

        if existing_hooks and not dry_run:
            action = prompt_hook_action("Stop", len(existing_hooks))
            if action == "append":
                settings["hooks"]["Stop"] = existing_hooks + [kb_capture_hook]
                print("   ✓ Appended kb-capture.py hook to Stop")
            elif action == "replace":
                settings["hooks"]["Stop"] = [kb_capture_hook]
                print("   ✓ Replaced Stop hooks with kb-capture.py")
            else:  # skip
                print("   ⊘ Skipped Stop hook modification")
        else:
            # No existing hooks or dry run - just set it
            settings["hooks"]["Stop"] = [kb_capture_hook]
            if not dry_run:
                print("   ✓ Configured Stop hook")
    else:
        print("   ⊘ kb-capture.py hook already exists in Stop")

    save_json(settings_path, settings, dry_run)


def prompt_for_model() -> str:
    """Prompt user to select a model for knowledge base operations."""
    models = {
        "1": ("claude-haiku-4-5-20251001", "Haiku 4.5 (fastest, cheapest, recommended)"),
        "2": ("claude-sonnet-4-6", "Sonnet 4.6 (balanced)"),
        "3": ("claude-opus-4-7", "Opus 4.7 (most capable, expensive)"),
        "4": ("custom", "Enter a custom model ID"),
    }

    print("\n🤖 Select model for knowledge base operations:")
    print("   (Used for extracting facts and ingesting content)")
    print()
    for key, (model_id, desc) in models.items():
        print(f"   {key}. {desc}")
    print()

    while True:
        choice = input("Enter your choice [1-4] (default: 1): ").strip() or "1"
        if choice in models:
            selected_model, description = models[choice]
            if choice == "4":
                # Custom model ID
                print("\n   Example: us-gov.anthropic.claude-sonnet-4-5-20250929-v1:0")
                custom_id = input("   Enter custom model ID: ").strip()
                if custom_id:
                    print(f"   ✓ Selected: {custom_id}")
                    return custom_id
                else:
                    print("   Invalid model ID. Please try again.")
                    continue
            print(f"   ✓ Selected: {description}")
            return selected_model
        print("   Invalid choice. Please enter 1-4.")


def create_storage_tree(claude_dir: Path, source_dir: Path, dry_run: bool = False, model_id: Optional[str] = None) -> None:
    """Create the second-brain storage directory structure."""
    kb_root = claude_dir / "second-brain"

    print("\n📁 Creating storage tree...")

    # Create category directories
    categories = ["concepts", "recipes", "references", "decisions", "tools", "domains"]
    for cat in categories:
        ensure_dir(kb_root / cat, dry_run)

    # Create metadata directory
    ensure_dir(kb_root / ".metadata", dry_run)

    # Copy template files if they don't exist
    template_dir = source_dir / "templates" / "second-brain"

    readme_dst = kb_root / "README.md"
    if not readme_dst.exists() or dry_run:
        copy_file(template_dir / "README.md", readme_dst, dry_run)

    config_dst = kb_root / ".config.json"
    if not config_dst.exists() or dry_run:
        copy_file(template_dir / ".config.json", config_dst, dry_run)

        # Update config with selected model
        if not dry_run and model_id:
            config = load_json(config_dst)
            if "models" not in config:
                config["models"] = {}
            config["models"]["extractor"] = model_id
            config["models"]["ingest"] = model_id
            save_json(config_dst, config, dry_run=False)
            print(f"   ✓ Configured models: {model_id}")


def install_hooks(claude_dir: Path, source_dir: Path, dry_run: bool = False) -> None:
    """Install hook scripts."""
    hooks_dir = claude_dir / "hooks"
    source_hooks = source_dir / "hooks"
    
    print("\n🪝 Installing hooks...")
    
    # Copy hook scripts
    copy_file(source_hooks / "kb-capture.py", hooks_dir / "kb-capture.py", dry_run)
    copy_file(source_hooks / "kb-inject.py", hooks_dir / "kb-inject.py", dry_run)
    
    # Make executable on Unix
    if not dry_run and os.name != 'nt':
        make_executable(hooks_dir / "kb-capture.py")
        make_executable(hooks_dir / "kb-inject.py")


def install_agents(claude_dir: Path, source_dir: Path, dry_run: bool = False) -> None:
    """Install agent definitions."""
    agents_dir = claude_dir / "agents"
    source_agents = source_dir / "agents"
    
    print("\n🤖 Installing agents...")
    
    copy_file(source_agents / "kb-extractor.md", agents_dir / "kb-extractor.md", dry_run)


def install_skills(claude_dir: Path, source_dir: Path, dry_run: bool = False) -> None:
    """Install skill files and scripts."""
    skills_dir = claude_dir / "skills" / "second-brain"
    source_skills = source_dir / "skills" / "second-brain"
    
    print("\n📚 Installing skill...")
    
    # Copy SKILL.md
    copy_file(source_skills / "SKILL.md", skills_dir / "SKILL.md", dry_run)
    
    # Copy scripts
    scripts_dir = skills_dir / "scripts"
    source_scripts = source_skills / "scripts"
    
    script_files = [
        "query.py",
        "publish.py",
        "consolidate.py",
        "ingest.py",
        "config.py",
        "status.py",
        "help.py",
        "show.py"
    ]
    
    for script in script_files:
        copy_file(source_scripts / script, scripts_dir / script, dry_run)
        if not dry_run and os.name != 'nt':
            make_executable(scripts_dir / script)


def verify_installation(claude_dir: Path) -> bool:
    """Verify that all components are installed correctly."""
    print("\n🔍 Verifying installation...")
    
    required_paths = [
        claude_dir / "settings.json",
        claude_dir / "hooks" / "kb-capture.py",
        claude_dir / "hooks" / "kb-inject.py",
        claude_dir / "agents" / "kb-extractor.md",
        claude_dir / "skills" / "second-brain" / "SKILL.md",
        claude_dir / "second-brain" / ".config.json",
    ]
    
    all_ok = True
    for path in required_paths:
        if path.exists():
            print(f"  ✓ {path.relative_to(claude_dir)}")
        else:
            print(f"  ✗ MISSING: {path.relative_to(claude_dir)}")
            all_ok = False
    
    return all_ok


def print_next_steps() -> None:
    """Print instructions for next steps."""
    print("""
✅ Installation complete!

🚀 Next steps:

1. Start a new Claude Code session - the hooks will activate automatically.

2. Test the skill:
   /second-brain status      # Check installation
   /second-brain help        # View full help

3. Configure publishing (optional):
   /second-brain publish --set-remote https://github.com/YOU/REPO.wiki.git
   /second-brain publish --force

4. The system works automatically:
   - After each assistant turn → facts are captured to ~/.claude/second-brain/
   - Before each prompt → relevant notes are injected into context

📁 Key locations:
   Config:    ~/.claude/settings.json
   KB root:   ~/.claude/second-brain/
   Hooks:     ~/.claude/hooks/
   Agents:    ~/.claude/agents/
   Skills:    ~/.claude/skills/

📖 Learn more:
   Read the design doc: smooth-humming-quokka.md
   Skill usage: /second-brain help
""")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deploy the second-brain skill for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python install.py                    # Standard installation
  python install.py --dry-run          # Preview changes
  python install.py --claude-dir ~/custom/.claude  # Custom location
""")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be installed without making changes")
    parser.add_argument("--claude-dir", type=str, default=None,
                        help="Custom Claude config directory (default: ~/.claude)")
    
    args = parser.parse_args()
    
    print("🧠 Second Brain Skill Deployment")
    print("=" * 50)
    
    if args.dry_run:
        print("\n⚠️  DRY RUN MODE - No changes will be made\n")
    
    # Get directories
    claude_dir = get_claude_dir(args)
    source_dir = get_source_dir()
    
    print(f"\n📍 Claude directory: {claude_dir}")
    print(f"📦 Source directory: {source_dir}")
    
    # Verify source files exist
    manifest_path = source_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"\n❌ Error: manifest.json not found in {source_dir}")
        print("   Make sure you're running install.py from the deployment package directory.")
        return 1
    
    # Create base directories
    print("\n📁 Creating base directories...")
    ensure_dir(claude_dir, args.dry_run)
    ensure_dir(claude_dir / "hooks", args.dry_run)
    ensure_dir(claude_dir / "agents", args.dry_run)
    ensure_dir(claude_dir / "skills", args.dry_run)
    
    # Prompt for model selection (skip in dry-run mode)
    model_id = None
    if not args.dry_run:
        model_id = prompt_for_model()

    # Install components
    try:
        install_hooks(claude_dir, source_dir, args.dry_run)
        install_agents(claude_dir, source_dir, args.dry_run)
        install_skills(claude_dir, source_dir, args.dry_run)
        create_storage_tree(claude_dir, source_dir, args.dry_run, model_id)

        print("\n⚙️  Updating settings.json...")
        update_settings_json(claude_dir, source_dir, args.dry_run)
        
    except Exception as e:
        print(f"\n❌ Error during installation: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Verify
    if not args.dry_run:
        if verify_installation(claude_dir):
            print_next_steps()
            return 0
        else:
            print("\n⚠️  Some components may not have installed correctly.")
            return 1
    else:
        print("\n✅ Dry run complete. No changes were made.")
        return 0


if __name__ == "__main__":
    sys.exit(main())