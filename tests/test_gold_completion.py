import csv
import json
from pathlib import Path

import pytest

from variant_cover_organizer.cli import main
from variant_cover_organizer.core import build_plan, export_copies
from variant_cover_organizer.review import selected_plan, verify_export


def fixture(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.png").write_bytes(b"cover")
    (source / "b.png").write_bytes(b"cover")
    inventory = tmp_path / "inventory.csv"
    with inventory.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["issue_id", "issue_label", "variant", "file"])
        writer.writerow(["Issue", "Issue 1", "A", "a.png"])
        writer.writerow(["Issue", "Issue 1", "B", "b.png"])
    return source, inventory, build_plan(inventory, source)


@pytest.mark.parametrize(
    "contents",
    [
        "issue_id,issue_label,variant,file\nIssue,Issue 1\n",
        "issue_id,issue_label,variant,file\nIssue,Issue 1,A,a.png,extra\n",
        "issue_id,issue_label,variant,file,file\nIssue,Issue 1,A,a.png,b.png\n",
    ],
)
def test_ambiguous_csv_is_an_actionable_error(tmp_path, capsys, contents):
    source, inventory, _ = fixture(tmp_path)
    inventory.write_text(contents)
    assert main([str(inventory), "--source", str(source)]) == 2
    assert "CSV" in capsys.readouterr().err


def test_reviewed_subset_recalculates_duplicate_groups(tmp_path):
    _, _, plan = fixture(tmp_path)
    assert len(plan["duplicate_content"]) == 1
    chosen = selected_plan(plan, {**plan, "items": plan["items"][:1]})
    assert chosen["duplicate_content"] == []
    assert len(plan["duplicate_content"]) == 1


@pytest.mark.parametrize(
    "field,value", [("version", True), ("variant_count", True), ("variant_count", 1)]
)
def test_manifest_rejects_false_schema_and_counts(tmp_path, field, value):
    _, _, plan = fixture(tmp_path)
    output = tmp_path / "export"
    export_copies(plan, output)
    path = output / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest[field] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        verify_export(output)


def test_resume_refuses_unrelated_staged_files(tmp_path):
    _, _, plan = fixture(tmp_path)
    stage = tmp_path / ".export.partial"
    stage.mkdir()
    (stage / "plan.json").write_text(json.dumps(plan))
    extra = stage / "unrelated.txt"
    extra.write_text("preserve me")
    with pytest.raises(ValueError, match="unexpected"):
        export_copies(plan, tmp_path / "export", resume=True)
    assert extra.read_text() == "preserve me"
    assert not (tmp_path / "export").exists()


@pytest.mark.parametrize("metadata", ["plan.json", "manifest.json"])
def test_resume_rejects_metadata_symlinks(tmp_path, metadata):
    _, _, plan = fixture(tmp_path)
    stage = tmp_path / ".export.partial"
    stage.mkdir()
    (stage / "plan.json").write_text(json.dumps(plan))
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(plan) if metadata == "plan.json" else "{}")
    target = stage / metadata
    if target.exists():
        target.unlink()
    try:
        target.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation unavailable")
    before = outside.read_bytes()
    with pytest.raises(ValueError, match="symlink"):
        export_copies(plan, tmp_path / "export", resume=True)
    assert outside.read_bytes() == before
    assert not (tmp_path / "export").exists()


def test_output_created_during_render_is_never_overwritten(monkeypatch, tmp_path):
    source, inventory, _ = fixture(tmp_path)
    output = tmp_path / "report.json"
    real_open = Path.open
    raced = False

    def race(path, mode="r", *args, **kwargs):
        nonlocal raced
        if path == output and mode in {"w", "x"} and not raced:
            raced = True
            with real_open(output, "w") as handle:
                handle.write("arrived concurrently")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", race)
    assert main([str(inventory), "--source", str(source), "--output", str(output)]) == 2
    assert output.read_text() == "arrived concurrently"


@pytest.mark.parametrize("target", ["CON/A.png", "Issue/NUL.png", "LPT1.txt/A.png"])
def test_device_targets_fail_before_staging(tmp_path, target):
    _, _, plan = fixture(tmp_path)
    plan["items"][0]["target"] = target
    with pytest.raises(ValueError, match="unsafe|noncanonical"):
        export_copies(plan, tmp_path / "export")
    assert not (tmp_path / ".export.partial").exists()


@pytest.mark.parametrize("mismatch", [False, True])
def test_resume_after_link_before_partial_retirement(monkeypatch, tmp_path, mismatch):
    from variant_cover_organizer import review

    _, _, plan = fixture(tmp_path)
    destination = tmp_path / "export"
    real_link = review.os.link

    def interrupted_link(source, target):
        real_link(source, target)
        raise KeyboardInterrupt("interrupted after link publication")

    monkeypatch.setattr(review.os, "link", interrupted_link)
    with pytest.raises(KeyboardInterrupt):
        export_copies(plan, destination)
    stage = tmp_path / ".export.partial"
    partial = next((stage / ".copying").iterdir())
    assert (stage / "Issue/A.png").is_file()
    assert partial.read_bytes() == b"cover"
    if mismatch:
        partial.unlink()
        partial.write_bytes(b"unrelated changed bytes")
    monkeypatch.setattr(review.os, "link", real_link)
    if mismatch:
        with pytest.raises(ValueError, match="incomplete staged file hash differs"):
            export_copies(plan, destination, resume=True)
        assert partial.read_bytes() == b"unrelated changed bytes"
        assert not destination.exists()
    else:
        export_copies(plan, destination, resume=True)
        assert verify_export(destination, strict=True)["verified"]
        assert list((destination / ".copying").iterdir()) == []


def test_planning_hashes_covers_without_reading_them_whole(monkeypatch, tmp_path):
    source, inventory, expected = fixture(tmp_path)
    real_read = Path.read_bytes

    def forbid_whole_cover_read(path):
        if path.parent == source:
            raise AssertionError("cover must be hashed in bounded chunks")
        return real_read(path)

    monkeypatch.setattr(Path, "read_bytes", forbid_whole_cover_read)
    assert build_plan(inventory, source) == expected


def test_resume_restarts_incomplete_hardlink_without_changing_source(tmp_path):
    import hashlib
    import os

    source, _, plan = fixture(tmp_path)
    destination = tmp_path / "export"
    stage = tmp_path / ".export.partial"
    (stage / ".copying").mkdir(parents=True)
    (stage / "plan.json").write_text(json.dumps(plan))
    part = (
        stage
        / ".copying"
        / (hashlib.sha256(plan["items"][0]["target"].encode()).hexdigest() + ".part")
    )
    os.link(source / "a.png", part)
    export_copies(plan, destination, resume=True)
    assert (source / "a.png").read_bytes() == b"cover"
    assert verify_export(destination, strict=True)["verified"]


@pytest.mark.parametrize("entry", ["plan.json", "manifest.json", "partial", "target"])
def test_resume_rejects_nonregular_entries_without_blocking(tmp_path, entry):
    import hashlib
    import os
    import subprocess
    import sys

    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO creation unavailable")
    source, inventory, plan = fixture(tmp_path)
    stage = tmp_path / ".export.partial"
    stage.mkdir()
    (stage / "plan.json").write_text(json.dumps(plan))
    name = {
        "partial": ".copying/"
        + hashlib.sha256(plan["items"][0]["target"].encode()).hexdigest()
        + ".part",
        "target": "Issue/A.png",
    }.get(entry, entry)
    path = stage / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    os.mkfifo(path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "variant_cover_organizer",
            str(inventory),
            "--source",
            str(source),
            "--copy-to",
            str(tmp_path / "export"),
            "--resume",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 2 and "regular file" in result.stderr
    assert not (tmp_path / "export").exists()
    assert path.exists()


def test_verification_rejects_manifest_fifo_without_blocking(tmp_path):
    import os
    import subprocess
    import sys

    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO creation unavailable")
    output = tmp_path / "export"
    output.mkdir()
    os.mkfifo(output / "manifest.json")
    result = subprocess.run(
        [sys.executable, "-m", "variant_cover_organizer", "--verify-export", str(output)],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 2 and "regular file" in result.stderr
