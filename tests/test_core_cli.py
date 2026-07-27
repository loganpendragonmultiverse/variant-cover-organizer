import csv
import json
from pathlib import Path

import pytest

from variant_cover_organizer.cli import main
from variant_cover_organizer.core import build_plan, export_copies


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["issue_id", "issue_label", "variant", "file"])
        writer.writeheader()
        writer.writerows(rows)


def setup(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "covers"
    source.mkdir(parents=True)
    (source / "a.jpg").write_bytes(b"cover-a")
    (source / "b.jpg").write_bytes(b"cover-b")
    inventory = tmp_path / "variants.csv"
    write_csv(
        inventory,
        [
            {"issue_id": "north-1", "issue_label": "North 1", "variant": "A", "file": "a.jpg"},
            {"issue_id": "north-1", "issue_label": "North 1", "variant": "B", "file": "b.jpg"},
        ],
    )
    return source, inventory


def test_plan_and_export(tmp_path: Path) -> None:
    source, inventory = setup(tmp_path)
    plan = build_plan(inventory, source)
    assert plan["variant_count"] == 2
    destination = tmp_path / "organized"
    export_copies(plan, destination)
    assert (destination / "north-1" / "A.jpg").read_bytes() == b"cover-a"
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["variant_count"] == 2
    assert manifest["copies"][0]["destination"] == "north-1/A.jpg"
    assert manifest["copies"][0]["sha256"] == plan["items"][0]["sha256"]
    with pytest.raises(ValueError, match="already exists"):
        export_copies(plan, destination)
    with pytest.raises(ValueError, match="inside"):
        export_copies(plan, source / "inside")


def test_validation(tmp_path: Path) -> None:
    source, inventory = setup(tmp_path)
    with pytest.raises(ValueError, match="directory"):
        build_plan(inventory, tmp_path / "missing")
    write_csv(inventory, [])
    with pytest.raises(ValueError, match="at least one"):
        build_plan(inventory, source)
    write_csv(
        inventory, [{"issue_id": "../bad", "issue_label": "North", "variant": "A", "file": "a.jpg"}]
    )
    with pytest.raises(ValueError, match="unsafe"):
        build_plan(inventory, source)
    write_csv(
        inventory,
        [{"issue_id": "north", "issue_label": "North", "variant": "A", "file": "missing.jpg"}],
    )
    with pytest.raises(ValueError, match="missing or unsafe"):
        build_plan(inventory, source)


def test_duplicates_change_and_temporary_cleanup(tmp_path: Path) -> None:
    source, inventory = setup(tmp_path)
    rows = [
        {"issue_id": "north", "issue_label": "North", "variant": "A", "file": "a.jpg"},
        {"issue_id": "north", "issue_label": "North", "variant": "a", "file": "b.jpg"},
    ]
    write_csv(inventory, rows)
    with pytest.raises(ValueError, match="duplicate variant"):
        build_plan(inventory, source)
    source, inventory = setup(tmp_path / "second")
    plan = build_plan(inventory, source)
    (source / "a.jpg").write_bytes(b"changed")
    destination = tmp_path / "changed-output"
    with pytest.raises(ValueError, match="source changed"):
        export_copies(plan, destination)
    assert not (tmp_path / ".changed-output.tmp").exists()


def test_cli_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source, inventory = setup(tmp_path)
    assert main([str(inventory), "--source", str(source)]) == 0
    assert json.loads(capsys.readouterr().out)["variant_count"] == 2
    output = tmp_path / "plan.json"
    assert main([str(inventory), "--source", str(source), "--output", str(output)]) == 0
    assert main([str(inventory), "--source", str(source), "--output", str(output)]) == 2


def test_reports_byte_identical_variants(tmp_path: Path) -> None:
    source, inventory = setup(tmp_path)
    (source / "b.jpg").write_bytes((source / "a.jpg").read_bytes())
    plan = build_plan(inventory, source)
    assert len(plan["duplicate_content"]) == 1
    duplicate = plan["duplicate_content"][0]
    assert len(duplicate["files"]) == 2
    assert duplicate["sha256"] == plan["items"][0]["sha256"]
