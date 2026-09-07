from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shutil
import unicodedata
from html import escape
from pathlib import Path
from typing import Any


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


def digest(path: Path) -> str:
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
        if digest(safe_path(source, item["source"])) != item["sha256"]:
            raise ValueError("source changed after planning")
    stage = destination.with_name("." + destination.name + ".partial")
    if stage.is_symlink():
        raise ValueError("unsafe staging symlink")
    if resume:
        if (
            not stage.is_dir()
            or json.loads((stage / "plan.json").read_text(encoding="utf-8")) != plan
        ):
            raise ValueError("resume requires the original matching staging plan")
    else:
        stage.mkdir(parents=True, exist_ok=False)
        with (stage / "plan.json").open("x", encoding="utf-8") as handle:
            json.dump(plan, handle, indent=2)
    copies = []
    for item in plan["items"]:
        target = safe_path(stage, item["target"])
        source_file = safe_path(source, item["source"])
        if target.exists():
            if digest(target) != item["sha256"]:
                raise ValueError("existing staged file hash differs; inspect without overwriting")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            copying = safe_path(
                stage, ".copying/" + hashlib.sha256(item["target"].encode()).hexdigest() + ".part"
            )
            copying.parent.mkdir(exist_ok=True)
            # A matching plan owns this incomplete staging copy. Resume restarts only it.
            with (
                source_file.open("rb") as incoming,
                copying.open("wb" if resume else "xb") as outgoing,
            ):
                shutil.copyfileobj(incoming, outgoing)
            if digest(copying) != item["sha256"] or digest(source_file) != item["sha256"]:
                raise ValueError("source or copy changed during export")
            os.link(copying, target)  # Atomic exclusive publication; never replace a target.
            copying.unlink()
        copies.append(
            {"source": item["source"], "destination": item["target"], "sha256": item["sha256"]}
        )
    manifest = {"version": 1, "source": str(source), "variant_count": len(copies), "copies": copies}
    manifest_path = stage / "manifest.json"
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("staged manifest differs")
    else:
        with manifest_path.open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
    if destination.exists():
        raise ValueError("destination appeared during export")
    os.rename(stage, destination)


def verify_export(destination: Path) -> dict[str, Any]:
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    if (
        not isinstance(manifest, dict)
        or manifest.get("version") != 1
        or not isinstance(manifest.get("copies"), list)
    ):
        raise ValueError("invalid version 1 export manifest")
    results = []
    seen = set()
    for item in manifest["copies"]:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("destination"), str)
            or not isinstance(item.get("sha256"), str)
        ):
            raise TypeError("invalid copy manifest item")
        name = item["destination"]
        normalized = unicodedata.normalize("NFC", name).casefold()
        if normalized in seen:
            raise ValueError("duplicate manifest destination")
        seen.add(normalized)
        path = safe_path(destination, name)
        status = (
            "missing"
            if not path.is_file()
            else "verified"
            if digest(path) == item["sha256"]
            else "modified"
        )
        results.append({"destination": name, "status": status})
    return {
        "version": 1,
        "verified": all(item["status"] == "verified" for item in results),
        "copies": results,
        "note": "Verifies listed copies against the local manifest, not manifest authenticity or extra files",
    }


def selected_plan(original: dict[str, Any], chosen: Any) -> dict[str, Any]:
    if (
        not isinstance(chosen, dict)
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
    return {**original, "items": chosen["items"], "variant_count": len(chosen["items"])}


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
        + '</script><script>const p=JSON.parse(document.getElementById("plan").textContent);document.getElementById("download").onclick=()=>{const items=[...document.querySelectorAll("input:checked")].map(x=>p.items[Number(x.dataset.index)]);if(!items.length){document.getElementById("status").textContent="Select at least one cover";return;}const url=URL.createObjectURL(new Blob([JSON.stringify({...p,items,variant_count:items.length},null,2)],{type:"application/json"}));const a=document.createElement("a");a.href=url;a.download="reviewed-variants.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);document.getElementById("status").textContent=items.length+" covers selected. Use --reviewed-plan for export.";};</script></html>'
    )
