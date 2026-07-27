from __future__ import annotations

import csv
import hashlib
import os
import re
import shutil
from pathlib import Path
from typing import Any

SAFE_LABEL = re.compile(r"^[\w .()&+,'-]+$", re.UNICODE)
FIELDS = ("issue_id", "issue_label", "variant", "file")


def _safe_part(value: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned or not SAFE_LABEL.fullmatch(cleaned) or cleaned in {".", ".."}:
        raise ValueError(f"unsafe or empty {field}: {value!r}")
    return cleaned


def build_plan(csv_path: Path, source: Path) -> dict[str, Any]:
    if not source.is_dir():
        raise ValueError("source must be a directory")
    source = source.resolve()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or any(field not in reader.fieldnames for field in FIELDS):
            raise ValueError(f"CSV must contain: {', '.join(FIELDS)}")
        rows = list(reader)
    if not rows:
        raise ValueError("CSV must contain at least one variant")
    assignments: set[tuple[str, str]] = set()
    source_files: set[Path] = set()
    items = []
    for row in rows:
        issue_id = _safe_part(row["issue_id"], "issue_id")
        issue_label = _safe_part(row["issue_label"], "issue_label")
        variant = _safe_part(row["variant"], "variant")
        relative = Path(row["file"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"file must be a safe relative path: {row['file']}")
        source_file = (source / relative).resolve()
        if (
            source not in source_file.parents
            or not source_file.is_file()
            or source_file.is_symlink()
        ):
            raise ValueError(f"source file is missing or unsafe: {row['file']}")
        assignment = (issue_id.casefold(), variant.casefold())
        if assignment in assignments:
            raise ValueError(f"duplicate variant assignment: {issue_id} / {variant}")
        if source_file in source_files:
            raise ValueError(f"source file assigned more than once: {row['file']}")
        assignments.add(assignment)
        source_files.add(source_file)
        extension = source_file.suffix.casefold()
        target = f"{issue_id}/{variant}{extension}"
        items.append(
            {
                "issue_id": issue_id,
                "issue_label": issue_label,
                "variant": variant,
                "source": source_file.relative_to(source).as_posix(),
                "target": target,
                "size": source_file.stat().st_size,
                "sha256": hashlib.sha256(source_file.read_bytes()).hexdigest(),
            }
        )
    targets = [str(item["target"]).casefold() for item in items]
    if len(targets) != len(set(targets)):
        raise ValueError("two variants resolve to the same destination")
    return {"version": 1, "source": str(source), "variant_count": len(items), "items": items}


def export_copies(plan: dict[str, Any], destination: Path) -> None:
    source = Path(plan["source"])
    destination = destination.resolve()
    if destination.exists():
        raise ValueError("copy destination already exists")
    if source == destination or source in destination.parents:
        raise ValueError("copy destination cannot be inside the source")
    temporary = destination.with_name(f".{destination.name}.tmp")
    if temporary.exists():
        raise ValueError("temporary export path already exists")
    try:
        for item in plan["items"]:
            source_file = source / item["source"]
            if hashlib.sha256(source_file.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError(f"source changed after planning: {item['source']}")
            target = temporary / item["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target)
        os.replace(temporary, destination)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
