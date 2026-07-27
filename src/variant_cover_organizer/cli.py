from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .core import build_plan, export_copies


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan explicit comic cover-variant groups.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--copy-to", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        plan = build_plan(args.input, args.source)
        if args.copy_to:
            export_copies(plan, args.copy_to)
        rendered = json.dumps(plan, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            if args.output.exists():
                raise ValueError(f"output already exists: {args.output}")
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, TypeError, ValueError, csv.Error, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
