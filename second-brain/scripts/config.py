#!/usr/bin/env python
"""Manage second-brain config via CLI: set models, toggle auto-capture, etc."""
import argparse
import json
import sys
from pathlib import Path

KB_ROOT = Path.home() / ".claude" / "second-brain"
CONFIG_PATH = KB_ROOT / ".config.json"


def load_cfg():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_cfg(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, sort_keys=True), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Manage second-brain config")
    ap.add_argument("--set-model", nargs=2, metavar=("operation", "model"), help="Set model for an operation (extractor|ingest)")
    ap.add_argument("--toggle-capture", action="store_true", help="Toggle auto_capture on/off")
    ap.add_argument("--toggle-inject", action="store_true", help="Toggle auto_inject on/off")
    ap.add_argument("--show", action="store_true", help="Show current config")
    args = ap.parse_args()

    if not args.show and not args.set_model and not args.toggle_capture and not args.toggle_inject:
        args.show = True

    cfg = load_cfg()

    if args.set_model:
        op, model = args.set_model
        if op not in ("extractor", "ingest"):
            print(f"Unknown operation: {op}. Supported: extractor, ingest", file=sys.stderr)
            sys.exit(2)
        cfg.setdefault("models", {})[op] = model
        save_cfg(cfg)
        print(f"Set {op} model to {model}")

    if args.toggle_capture:
        cfg["auto_capture"] = not cfg.get("auto_capture", True)
        save_cfg(cfg)
        print(f"auto_capture: {cfg['auto_capture']}")

    if args.toggle_inject:
        cfg["auto_inject"] = not cfg.get("auto_inject", True)
        save_cfg(cfg)
        print(f"auto_inject: {cfg['auto_inject']}")

    if args.show:
        print(json.dumps(cfg, indent=2))


if __name__ == "__main__":
    main()
