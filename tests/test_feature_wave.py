import json

import pytest

from variant_cover_organizer.cli import main
from variant_cover_organizer.review import verify_export


def fixture(tmp_path):
    output = tmp_path / "export"
    output.mkdir()
    (output / "A").write_bytes(b"cover")
    import hashlib

    item = {"destination": "A", "sha256": hashlib.sha256(b"cover").hexdigest()}
    manifest = {"version": 1, "copies": [item]}
    (output / "manifest.json").write_text(json.dumps(manifest))
    return output, manifest


def test_strict_extras_legacy_and_read_only(tmp_path):
    output, _manifest = fixture(tmp_path)
    assert verify_export(output, strict=True)["verified"]
    (output / "extra.txt").write_text("leave untouched")
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    assert verify_export(output)["verified"]
    strict = verify_export(output, strict=True)
    assert not strict["verified"] and strict["unexpected_paths"] == ["extra.txt"]
    assert main(["--verify-export", str(output), "--strict"]) == 1
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before
    assert main(["--strict"]) == 2


@pytest.mark.parametrize(
    "destination",
    ["../outside", "./A", "x//A", "/absolute", "C:\\outside", "x\\..\\a", "manifest.json"],
)
def test_unsafe_destinations(tmp_path, destination):
    output, manifest = fixture(tmp_path)
    manifest["copies"][0]["destination"] = destination
    (output / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        verify_export(output, strict=True)


@pytest.mark.parametrize("names", [("A", "a"), ("é", "e\u0301"), ("A", "A")])
def test_duplicate_destinations(tmp_path, names):
    output, manifest = fixture(tmp_path)
    item = manifest["copies"][0]
    manifest["copies"] = [{**item, "destination": name} for name in names]
    (output / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="duplicate"):
        verify_export(output, strict=True)


def test_symlinks_root_manifest_listed_and_unexpected(tmp_path):
    output, _manifest = fixture(tmp_path)
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(output, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable on this platform")
    with pytest.raises(ValueError):
        verify_export(alias, strict=True)
    extra = output / "extra"
    extra.symlink_to(tmp_path / "missing")
    assert verify_export(output, strict=True)["unexpected_paths"] == ["extra"]
    extra.unlink()
    (output / "A").unlink()
    (output / "A").symlink_to(tmp_path / "missing")
    with pytest.raises(ValueError):
        verify_export(output, strict=True)
    (output / "A").unlink()
    (output / "manifest.json").unlink()
    (output / "manifest.json").symlink_to(tmp_path / "missing")
    with pytest.raises(ValueError):
        verify_export(output, strict=True)


def test_invalid_digest_and_shape(tmp_path):
    output, manifest = fixture(tmp_path)
    for bad in (
        {},
        {**manifest, "copies": [None]},
        {**manifest, "copies": [{"destination": "A", "sha256": "invalid"}]},
    ):
        (output / "manifest.json").write_text(json.dumps(bad))
        with pytest.raises((ValueError, TypeError)):
            verify_export(output, strict=True)


def test_strict_traversal_failure_is_not_verified(tmp_path, monkeypatch):
    output, _manifest = fixture(tmp_path)
    from variant_cover_organizer import review

    def blocked(*args, **kwargs):
        kwargs["onerror"](PermissionError("fixture inaccessible directory"))
        return iter(())

    monkeypatch.setattr(review.os, "walk", blocked)
    assert verify_export(output)["verified"]
    with pytest.raises(PermissionError):
        verify_export(output, strict=True)
