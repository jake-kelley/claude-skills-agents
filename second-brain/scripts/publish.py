#!/usr/bin/env python
"""Publish the second-brain to a configured <repo>.wiki.git remote.

Usage: publish.py [--set-remote URL] [--message "commit msg"]

First run on a fresh KB: sets up git, force-pushes (KB owns the wiki).
Subsequent runs: commit and push fast-forward.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

KB_ROOT = Path.home() / ".claude" / "second-brain"
CONFIG_PATH = KB_ROOT / ".config.json"


def run(cmd, check=True, capture=True):
    print(f"$ {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=str(KB_ROOT), capture_output=capture, text=True, encoding="utf-8", errors="replace")
    if r.stdout:
        print(r.stdout.rstrip())
    if r.stderr:
        print(r.stderr.rstrip(), file=sys.stderr)
    if check and r.returncode != 0:
        sys.exit(r.returncode)
    return r


def load_cfg():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_cfg(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set-remote", help="Set the wiki.git remote URL and exit")
    ap.add_argument("--message", default=None)
    ap.add_argument("--force", action="store_true", help="Force push (use for first publish)")
    args = ap.parse_args()

    cfg = load_cfg()

    if args.set_remote:
        cfg.setdefault("publish", {})["remote_url"] = args.set_remote
        save_cfg(cfg)
        print(f"Remote URL saved: {args.set_remote}")
        return

    remote = cfg.get("publish", {}).get("remote_url", "")
    if not remote:
        print("No publish remote configured. Run with --set-remote <url> first.", file=sys.stderr)
        print("URL pattern: https://github.com/<user>/<repo>.wiki.git or https://gitlab.com/<user>/<repo>.wiki.git", file=sys.stderr)
        sys.exit(2)

    branch = cfg.get("publish", {}).get("branch", "master")
    msg = args.message or cfg.get("publish", {}).get("auto_commit_message", "kb: sync from second-brain")
    msg = f"{msg} ({datetime.now().strftime('%Y-%m-%d %H:%M')})"

    if not (KB_ROOT / ".git").exists():
        run(["git", "init", "-b", branch])

    # ensure remote
    r = subprocess.run(["git", "remote", "get-url", "origin"], cwd=str(KB_ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        run(["git", "remote", "add", "origin", remote])
    else:
        existing = r.stdout.strip()
        if existing != remote:
            run(["git", "remote", "set-url", "origin", remote])

    run(["git", "add", "-A"])
    r = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(KB_ROOT))
    if r.returncode == 0:
        print("Nothing to commit.")
    else:
        run(["git", "commit", "-m", msg])

    push_cmd = ["git", "push", "origin", f"HEAD:{branch}"]
    if args.force:
        push_cmd.append("--force")
    run(push_cmd)
    print(f"\nPublished to {remote} ({branch}).")


if __name__ == "__main__":
    main()
