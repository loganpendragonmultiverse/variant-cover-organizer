import hashlib
import json

import pytest

from variant_cover_organizer.core import build_plan, export_copies
from variant_cover_organizer.review import verify_export


def inventory(tmp_path, issue_id):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.png").write_bytes(b"cover")
    path = tmp_path / "inventory.csv"
    path.write_text(
        "issue_id,issue_label,variant,file\n" + issue_id + ",Issue 1,A,a.png\n",
        encoding="utf-8",
    )
    return source, path


@pytest.mark.parametrize("issue_id", [".copying", ".COPYING", "plan.json", "MANIFEST.JSON"])
def test_new_plans_reject_staging_and_metadata_names(tmp_path, issue_id):
    source, path = inventory(tmp_path, issue_id)
    with pytest.raises(ValueError, match="reserved"):
        build_plan(path, source)


def test_own_export_is_verifiable_near_reserved_name(tmp_path):
    source, path = inventory(tmp_path, ".copying-old")
    plan = build_plan(path, source)
    output = tmp_path / "output"
    export_copies(plan, output)
    assert verify_export(output)["verified"]
    assert verify_export(output, strict=True)["verified"]


def test_legacy_copying_directory_manifest_remains_verifiable(tmp_path):
    output = tmp_path / "legacy"
    (output / ".copying").mkdir(parents=True)
    cover = output / ".copying/A.png"
    cover.write_bytes(b"legacy cover")
    manifest = {
        "version": 1,
        "copies": [
            {
                "source": "a.png",
                "destination": ".copying/A.png",
                "sha256": hashlib.sha256(cover.read_bytes()).hexdigest(),
            }
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest))
    (output / "plan.json").write_text("{}")
    assert verify_export(output)["verified"]
    assert verify_export(output, strict=True)["verified"]
    extra = output / ".copying/unlisted.part"
    extra.write_bytes(b"unexpected")
    assert verify_export(output)["verified"]
    strict = verify_export(output, strict=True)
    assert not strict["verified"]
    assert strict["unexpected_paths"] == [".copying/unlisted.part"]


def test_direct_export_rejects_reserved_plan_before_staging(tmp_path):
    source, path = inventory(tmp_path, "Issue")
    plan = build_plan(path, source)
    plan["items"][0]["target"] = ".copying/A.png"
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="reserved"):
        export_copies(plan, output)
    assert not output.exists()
    assert not (tmp_path / ".output.partial").exists()
