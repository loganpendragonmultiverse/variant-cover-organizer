from __future__ import annotations

import csv
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
        reader = csv.DictReader(handle, strict=True)
        if reader.fieldnames is None or any(field not in reader.fieldnames for field in FIELDS):
            raise ValueError(f"CSV must contain: {', '.join(FIELDS)}")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError("CSV headers must be unique")
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ValueError("CSV rows must have exactly one value per header")
    if not rows:
        raise ValueError("CSV must contain at least one variant")
    assignments: set[tuple[str, str]] = set()
    source_files: set[Path] = set()
    items = []
    for row in rows:
        issue_id = _safe_part(row["issue_id"], "issue_id")
        if issue_id.casefold() in {".copying", "manifest.json", "plan.json"}:
            raise ValueError("issue_id is reserved for export bookkeeping")
        issue_label = _safe_part(row["issue_label"], "issue_label")
        variant = _safe_part(row["variant"], "variant")
        relative = Path(row["file"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"file must be a safe relative path: {row['file']}")
        from .review import digest, safe_path

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
        from .review import canonical_target

        canonical_target(target)
        items.append(
            {
                "issue_id": issue_id,
                "issue_label": issue_label,
                "variant": variant,
                "source": source_file.relative_to(source).as_posix(),
                "target": target,
                "size": source_file.stat().st_size,
                "sha256": digest(source_file),
            }
        )
    targets = [str(item["target"]).casefold() for item in items]
    if len(targets) != len(set(targets)):
        raise ValueError("two variants resolve to the same destination")
    return {
        "version": 1,
        "source": str(source),
        "variant_count": len(items),
        "duplicate_content": duplicate_content(items),
        "items": items,
    }


def export_copies(plan: dict[str, Any], destination: Path, *, resume: bool = False) -> None:
    from .review import export_resumable

    export_resumable(plan, destination, resume=resume)


def duplicate_content(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fingerprints: dict[str, list[dict[str, str]]] = {}
    for item in items:
        fingerprints.setdefault(str(item["sha256"]), []).append(
            {"source": str(item["source"]), "target": str(item["target"])}
        )
    return [
        {"sha256": fingerprint, "files": files}
        for fingerprint, files in fingerprints.items()
        if len(files) > 1
    ]
