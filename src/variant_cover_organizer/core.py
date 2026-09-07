from __future__ import annotations

import csv
import hashlib
import re
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
        from .review import safe_path

        source_file = safe_path(source, row["file"]).resolve()
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
    fingerprints: dict[str, list[dict[str, str]]] = {}
    for item in items:
        fingerprints.setdefault(str(item["sha256"]), []).append(
            {"source": str(item["source"]), "target": str(item["target"])}
        )
    duplicate_content = [
        {"sha256": fingerprint, "files": files}
        for fingerprint, files in fingerprints.items()
        if len(files) > 1
    ]
    return {
        "version": 1,
        "source": str(source),
        "variant_count": len(items),
        "duplicate_content": duplicate_content,
        "items": items,
    }


def export_copies(plan: dict[str, Any], destination: Path, *, resume: bool = False) -> None:
    from .review import export_resumable

    export_resumable(plan, destination, resume=resume)
