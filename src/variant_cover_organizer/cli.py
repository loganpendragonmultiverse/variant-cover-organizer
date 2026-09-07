from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .core import build_plan, export_copies
from .review import render_html, selected_plan, verify_export


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan explicit comic cover-variant groups.")
    parser.add_argument("input", type=Path, nargs="?")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--copy-to", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--format", choices=("json", "html"), default="json")
    parser.add_argument("--reviewed-plan", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--verify-export", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output and args.output.exists():
            raise ValueError("output already exists")
        if args.verify_export:
            if args.copy_to or args.resume or args.reviewed_plan or args.format != "json":
                raise ValueError("verification is read-only and emits JSON")
            report = verify_export(args.verify_export)
            rendered = json.dumps(report, indent=2) + "\n"
        else:
            if not args.input or not args.source:
                raise ValueError("inventory and --source are required")
            if args.resume and not args.copy_to:
                raise ValueError("--resume requires --copy-to")
            plan = build_plan(args.input, args.source)
            if args.reviewed_plan:
                plan = selected_plan(
                    plan, json.loads(args.reviewed_plan.read_text(encoding="utf-8"))
                )
            rendered = (
                render_html(plan)
                if args.format == "html"
                else json.dumps(plan, indent=2, ensure_ascii=False) + "\n"
            )
            if args.copy_to:
                export_copies(plan, args.copy_to, resume=args.resume)
        if args.output:
            if args.output.exists():
                raise ValueError(f"output already exists: {args.output}")
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, TypeError, ValueError, csv.Error, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return int(args.verify_export is not None and not report["verified"])
