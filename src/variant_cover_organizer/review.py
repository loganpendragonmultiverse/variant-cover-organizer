from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import shutil
import stat
import unicodedata
from html import escape
from pathlib import Path, PurePosixPath
from typing import Any


def canonical_target(name: str) -> PurePosixPath:
    """Require a portable target spelling before native filesystem operations."""
    relative = PurePosixPath(name)
    if (
        not name
        or not relative.parts
        or relative.is_absolute()
        or ".." in relative.parts
        or "\\" in name
        or ":" in name
        or "\x00" in name
        or name != relative.as_posix()
        or any(part.endswith((".", " ")) for part in relative.parts)
        or any(ord(char) < 32 or char in '<>"|?*' for char in name)
        or any(
            part.split(".", 1)[0].casefold()
            in {
                "con",
                "prn",
                "aux",
                "nul",
                *(f"com{x}" for x in "123456789¹²³"),
                *(f"lpt{x}" for x in "123456789¹²³"),
            }
            for part in relative.parts
        )
    ):
        raise ValueError("unsafe or noncanonical manifest path")
    return relative


def safe_path(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise ValueError("unsafe manifest path")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("symlinks are not allowed in export paths")
    if root.resolve() not in current.resolve().parents:
        raise ValueError("manifest path escapes root")
    return current


def require_regular(path: Path) -> None:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("expected a non-symlink regular file")


def read_json(path: Path) -> Any:
    require_regular(path)
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    require_regular(path)
    with path.open("rb") as handle:
        result = hashlib.sha256()
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def export_resumable(plan: dict[str, Any], destination: Path, *, resume: bool = False) -> None:
    source = Path(plan["source"]).resolve()
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("copy destination already exists")
    if source == destination.resolve() or source in destination.resolve().parents:
        raise ValueError("copy destination cannot be inside the source")
    targets = [unicodedata.normalize("NFC", item["target"]).casefold() for item in plan["items"]]
    if len(set(targets)) != len(targets):
        raise ValueError("case or Unicode destination collision")
    for item in plan["items"]:
        first = canonical_target(item["target"]).parts[0].casefold()
        if first in {".copying", "manifest.json", "plan.json"}:
            raise ValueError("copy target uses a reserved export bookkeeping name")
        if digest(safe_path(source, item["source"])) != item["sha256"]:
            raise ValueError("source changed after planning")
    stage = destination.with_name("." + destination.name + ".partial")
    if stage.is_symlink():
        raise ValueError("unsafe staging symlink")
    if resume:
        if not stage.is_dir() or read_json(safe_path(stage, "plan.json")) != plan:
            raise ValueError("resume requires the original matching staging plan")
        allowed = {"plan.json", "manifest.json"}
        for item in plan["items"]:
            allowed.add(item["target"])
            allowed.add(".copying/" + hashlib.sha256(item["target"].encode()).hexdigest() + ".part")
        for directory, folders, files in os.walk(stage, followlinks=False, onerror=walk_error):
            for entry in folders + files:
                path = Path(directory) / entry
                if path.is_symlink():
                    raise ValueError("symlinks are not allowed in staging")
                if not path.is_dir():
                    require_regular(path)
                if not path.is_dir() and path.relative_to(stage).as_posix() not in allowed:
                    raise ValueError("unexpected file in staging; inspect without deleting it")
    else:
        stage.mkdir(parents=True, exist_ok=False)
        with (stage / "plan.json").open("x", encoding="utf-8") as handle:
            json.dump(plan, handle, indent=2)
    copies = []
    for item in plan["items"]:
        target = safe_path(stage, item["target"])
        source_file = safe_path(source, item["source"])
        copying = safe_path(
            stage, ".copying/" + hashlib.sha256(item["target"].encode()).hexdigest() + ".part"
        )
        if target.exists():
            if digest(target) != item["sha256"]:
                raise ValueError("existing staged file hash differs; inspect without overwriting")
            if copying.exists():
                if digest(copying) != item["sha256"]:
                    raise ValueError(
                        "incomplete staged file hash differs; inspect without overwriting"
                    )
                copying.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            copying.parent.mkdir(exist_ok=True)
            # Restart only this plan-owned partial, using a new inode so a hard link
            # cannot truncate a source file or another file outside staging.
            if resume and copying.exists():
                copying.unlink()
            with source_file.open("rb") as incoming, copying.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
            if digest(copying) != item["sha256"] or digest(source_file) != item["sha256"]:
                raise ValueError("source or copy changed during export")
            os.link(copying, target)  # Atomic exclusive publication; never replace a target.
            copying.unlink()
        copies.append(
            {"source": item["source"], "destination": item["target"], "sha256": item["sha256"]}
        )
    manifest = {"version": 1, "source": str(source), "variant_count": len(copies), "copies": copies}
    manifest_path = safe_path(stage, "manifest.json")
    if manifest_path.exists():
        if read_json(manifest_path) != manifest:
            raise ValueError("staged manifest differs")
    else:
        with manifest_path.open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
    if destination.exists():
        raise ValueError("destination appeared during export")
    os.rename(stage, destination)


def verify_export(destination: Path, *, strict: bool = False) -> dict[str, Any]:
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError("export root must be a real directory")
    manifest_path = safe_path(destination, "manifest.json")
    manifest = read_json(manifest_path)
    if (
        not isinstance(manifest, dict)
        or type(manifest.get("version")) is not int
        or manifest.get("version") != 1
        or not isinstance(manifest.get("copies"), list)
    ):
        raise ValueError("invalid version 1 export manifest")
    if "variant_count" in manifest and (
        type(manifest["variant_count"]) is not int
        or manifest["variant_count"] != len(manifest["copies"])
    ):
        raise ValueError("manifest variant_count differs from its copies")
    results = []
    seen = set()
    expected = {"manifest.json", "plan.json"}
    for item in manifest["copies"]:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("destination"), str)
            or not isinstance(item.get("sha256"), str)
        ):
            raise TypeError("invalid copy manifest item")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", item["sha256"]):
            raise ValueError("invalid SHA-256 in manifest")
        name = item["destination"]
        canonical_target(name)
        if name.casefold() in {"manifest.json", "plan.json"}:
            raise ValueError("copy destination conflicts with export metadata")
        expected.add(name)
        normalized = unicodedata.normalize("NFC", name).casefold()
        if normalized in seen:
            raise ValueError("duplicate manifest destination")
        seen.add(normalized)
        path = safe_path(destination, name)
        status = (
            "missing"
            if not path.is_file()
            else "verified"
            if digest(path) == item["sha256"].lower()
            else "modified"
        )
        results.append({"destination": name, "status": status})
    unexpected = []
    if strict:
        for directory, folders, files in os.walk(
            destination, followlinks=False, onerror=walk_error
        ):
            for entry in sorted(folders + files):
                path = Path(directory) / entry
                name = path.relative_to(destination).as_posix()
                if path.is_symlink() or (not path.is_dir() and name not in expected):
                    unexpected.append(name)
        unexpected.sort()
    return {
        "version": 1,
        "strict": strict,
        "unexpected_paths": unexpected,
        "verified": all(item["status"] == "verified" for item in results) and not unexpected,
        "copies": results,
        "note": "Checks local manifest hashes; strict mode also reports unexpected files and symlinks. Does not authenticate the manifest.",
    }


def selected_plan(original: dict[str, Any], chosen: Any) -> dict[str, Any]:
    if (
        not isinstance(chosen, dict)
        or type(chosen.get("version")) is not int
        or chosen.get("version") != 1
        or chosen.get("source") != original["source"]
        or not isinstance(chosen.get("items"), list)
        or not chosen["items"]
    ):
        raise ValueError("reviewed plan must select at least one original item")
    if any(item not in original["items"] for item in chosen["items"]) or len(
        {item["target"] for item in chosen["items"]}
    ) != len(chosen["items"]):
        raise ValueError("reviewed plan contains changed or duplicate items")
    from .core import duplicate_content

    return {
        **original,
        "items": chosen["items"],
        "variant_count": len(chosen["items"]),
        "duplicate_content": duplicate_content(chosen["items"]),
    }


def render_html(plan: dict[str, Any]) -> str:
    from PIL import Image, UnidentifiedImageError

    if len(plan["items"]) > 200:
        raise ValueError("contact sheet is limited to 200 covers; select a smaller inventory")
    groups: dict[str, list[str]] = {}
    for index, item in enumerate(plan["items"]):
        path = safe_path(Path(plan["source"]), item["source"])
        try:
            with Image.open(path) as picture:
                if picture.width * picture.height > 40_000_000:
                    raise ValueError("cover image exceeds 40 million pixels")
                picture.thumbnail((260, 360))
                buffer = io.BytesIO()
                picture.convert("RGB").save(buffer, format="JPEG")
            preview = (
                '<img alt="'
                + escape(item["variant"], quote=True)
                + ' cover preview" src="data:image/jpeg;base64,'
                + base64.b64encode(buffer.getvalue()).decode()
                + '">'
            )
        except (UnidentifiedImageError, OSError):
            preview = "<p>Preview unavailable for this file</p>"
        groups.setdefault(item["issue_label"], []).append(
            f'<article>{preview}<label><input type="checkbox" data-index="{index}" checked> Include {escape(item["variant"])}</label><p>{escape(item["target"])}</p></article>'
        )
    payload = (
        json.dumps(plan, ensure_ascii=True)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    body = "".join(
        "<section><h2>"
        + escape(issue)
        + '</h2><div class="grid">'
        + "".join(items)
        + "</div></section>"
        for issue, items in groups.items()
    )
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Variant cover review</title><style>body{font:17px system-ui;background:#f4f0e7;color:#203442;max-width:1100px;margin:auto;padding:22px;line-height:1.5}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:18px}article{background:white;border:1px solid #bbc;padding:16px;border-radius:12px}img{display:block;max-width:100%;height:300px;object-fit:contain;margin:auto}label{display:block;margin:16px 0}p{overflow-wrap:anywhere}button{font:inherit;padding:12px}output{display:block}@media(max-width:600px){body{padding:12px}}</style><h1>Review issue variants</h1><p>Assignments come from your inventory. Select covers for a new reviewed plan; original files remain unchanged. This local report contains cover thumbnails.</p>'
        + body
        + '<button id="download">Download selected plan</button><output id="status" role="status"></output><script type="application/json" id="plan">'
        + payload
        + '</script><script>const p=JSON.parse(document.getElementById("plan").textContent);document.getElementById("download").onclick=()=>{const items=[...document.querySelectorAll("input:checked")].map(x=>p.items[Number(x.dataset.index)]);if(!items.length){document.getElementById("status").textContent="Select at least one cover";return;}const duplicate_content=p.duplicate_content.map(g=>({...g,files:g.files.filter(f=>items.some(i=>i.target===f.target))})).filter(g=>g.files.length>1);const url=URL.createObjectURL(new Blob([JSON.stringify({...p,items,variant_count:items.length,duplicate_content},null,2)],{type:"application/json"}));const a=document.createElement("a");a.href=url;a.download="reviewed-variants.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);document.getElementById("status").textContent=items.length+" covers selected. Use --reviewed-plan for export.";};</script></html>'
    )


def walk_error(error: OSError) -> None:
    raise error
