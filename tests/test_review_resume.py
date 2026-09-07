import copy
import csv
import json

import pytest
from PIL import Image

from variant_cover_organizer import review
from variant_cover_organizer.cli import main
from variant_cover_organizer.core import build_plan, export_copies
from variant_cover_organizer.review import render_html, safe_path, selected_plan, verify_export


def fixture(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for name, color in (("a", "red"), ("b", "blue")):
        Image.new("RGB", (30, 40), color).save(source / (name + ".png"))
    inventory = tmp_path / "inventory.csv"
    with inventory.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["issue_id", "issue_label", "variant", "file"])
        writer.writerow(["issue-1", "Issue 1", "A", "a.png"])
        writer.writerow(["issue-1", "Issue 1", "B", "b.png"])
    return source, inventory, build_plan(inventory, source)


def test_contact_sheet_selection_and_cli(tmp_path):
    source, inventory, plan = fixture(tmp_path)
    original = copy.deepcopy(plan)
    html = render_html(plan)
    assert html.count('src="data:image/jpeg;base64,') == 2
    assert "Issue 1" in html and "Download selected plan" in html
    chosen = {**plan, "items": plan["items"][:1]}
    assert selected_plan(plan, chosen)["variant_count"] == 1
    assert plan == original
    selection = tmp_path / "selection.json"
    selection.write_text(json.dumps(chosen))
    output = tmp_path / "report.html"
    assert (
        main(
            [
                str(inventory),
                "--source",
                str(source),
                "--reviewed-plan",
                str(selection),
                "--format",
                "html",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    for bad in (
        {},
        {**plan, "items": []},
        {**plan, "items": [plan["items"][0], plan["items"][0]]},
        {**plan, "items": [{"target": "changed"}]},
    ):
        with pytest.raises(ValueError):
            selected_plan(plan, bad)
    assert main([]) == 2
    assert main([str(inventory), "--source", str(source), "--resume"]) == 2


def test_interrupt_mid_copy_then_resume_and_verify(monkeypatch, tmp_path):
    source, _inventory, plan = fixture(tmp_path)
    hashes = {p.name: review.digest(p) for p in source.iterdir()}
    output = tmp_path / "export"
    real = review.shutil.copyfileobj
    calls = 0

    def interrupted(incoming, outgoing):
        nonlocal calls
        calls += 1
        if calls == 2:
            outgoing.write(incoming.read(5))
            raise KeyboardInterrupt("simulated mid-copy interruption")
        return real(incoming, outgoing)

    monkeypatch.setattr(review.shutil, "copyfileobj", interrupted)
    with pytest.raises(KeyboardInterrupt):
        export_copies(plan, output)
    assert not output.exists()
    assert (tmp_path / ".export.partial/issue-1/A.png").exists()
    monkeypatch.setattr(review.shutil, "copyfileobj", real)
    export_copies(plan, output, resume=True)
    assert verify_export(output)["verified"]
    assert main(["--verify-export", str(output)]) == 0
    assert main(["--verify-export", str(output), "--copy-to", str(tmp_path / "other")]) == 2
    assert {p.name: review.digest(p) for p in source.iterdir()} == hashes
    (output / "issue-1/A.png").write_bytes(b"changed copy")
    (output / "issue-1/B.png").unlink()
    result = verify_export(output)
    assert [x["status"] for x in result["copies"]] == ["modified", "missing"]
    assert main(["--verify-export", str(output)]) == 1


def test_resume_mismatch_collision_and_path_guards(tmp_path):
    source, _inventory, plan = fixture(tmp_path)
    with pytest.raises(ValueError, match="matching"):
        export_copies(plan, tmp_path / "new", resume=True)
    duplicated = {**plan, "items": [plan["items"][0], plan["items"][0]]}
    with pytest.raises(ValueError, match="collision"):
        export_copies(duplicated, tmp_path / "new")
    for path in ("../outside", "", str(tmp_path.absolute())):
        with pytest.raises(ValueError):
            safe_path(source, path)
    stage = tmp_path / ".new.partial"
    stage.mkdir()
    (stage / "plan.json").write_text(json.dumps(plan))
    (stage / "issue-1").mkdir()
    (stage / "issue-1/A.png").write_bytes(b"unknown changed staged content")
    with pytest.raises(ValueError, match="hash differs"):
        export_copies(plan, tmp_path / "new", resume=True)
    (stage / "plan.json").write_text("{}")
    with pytest.raises(ValueError, match="matching"):
        export_copies(plan, tmp_path / "new", resume=True)


def test_manifest_validation_and_preview_failure(tmp_path):
    source, _inventory, plan = fixture(tmp_path)
    output = tmp_path / "export"
    export_copies(plan, output)
    path = output / "manifest.json"
    manifest = json.loads(path.read_text())
    for bad in (
        {},
        {**manifest, "copies": [{}]},
        {**manifest, "copies": [manifest["copies"][0], manifest["copies"][0]]},
    ):
        path.write_text(json.dumps(bad))
        with pytest.raises((ValueError, TypeError)):
            verify_export(output)
    (source / "a.png").write_bytes(b"not an image")
    assert "Preview unavailable" in render_html(plan)
    with pytest.raises(ValueError, match="200"):
        render_html({**plan, "items": plan["items"] * 101})
