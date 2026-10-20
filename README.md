# Variant Cover Organizer

[![CI](https://github.com/loganpendragonmultiverse/variant-cover-organizer/actions/workflows/ci.yml/badge.svg)](https://github.com/loganpendragonmultiverse/variant-cover-organizer/actions/workflows/ci.yml)

Variant Cover Organizer converts an explicit CSV inventory into a safe grouping plan for comic cover variants. It validates source files, issue and variant labels, duplicate assignments, and destination collisions before optionally copying files into issue folders.

## Forge Gold scope

This tool covers the complete explicit-inventory workflow: validate assignments, review local thumbnails, download a selected plan, copy without changing originals, resume interrupted exports, and verify the resulting manifest. It does not identify artwork or fetch publisher metadata. Gold reflects this bounded scope and the tested release; it is not a promise of defect-free software.

## Three-minute start

```bash
python -m pip install .
variant-cover-organizer examples/variants.csv --source examples/covers
variant-cover-organizer variants.csv --source covers --copy-to organized-covers --output plan.json
```

The example paths are included in the source distribution and repository. Run them from the extracted source folder; installing the wheel provides the command, not a separate copy of that example folder.

Planning is the default. Reports flag byte-identical covers by grouping the SHA-256 fingerprints already calculated for safety. `--copy-to` creates a new destination through a staged directory, preserves every source file, and writes `manifest.json` mapping each source to its destination and fingerprint. Paths in the CSV must be relative and remain inside the selected source folder.

The tool does not identify cover art, scrape publisher metadata, or decide whether visually similar images are official variants. The user supplies the issue and variant identities. Requires Python 3.10 or newer.

Part of the [Logan Pendragon Forge open-source collection](https://www.loganpendragonforge.com/open-source/). Licensed under the [MIT License](LICENSE).

## Version 1.2.0: reviewed improvements

Add per-issue thumbnail selection, hash-verified export inspection and resumable copy staging with collision protection.

```bash
variant-cover-organizer variants.csv --source ./covers --format html --output review.html
```

HTML contact sheets show up to 200 local thumbnails with per-cover selection; --reviewed-plan accepts only unchanged items from the current CSV-derived plan. --copy-to creates a new destination through a matching .DEST.partial plan; --resume retains verified completed copies and restarts incomplete staging copies after rechecking original source hashes. Final file publication uses exclusive hard links and requires filesystem hard-link support. Modified completed copies and case/Unicode collisions are rejected without overwrite. --verify-export DIRECTORY checks listed manifest hashes and reports verified/missing/modified; it does not authenticate the manifest or claim there are no extra files. Original covers remain unchanged. Pillow generates thumbnails, with oversized images rejected and unsupported previews explicitly unavailable.


## Version 1.2.1

Use `variant-cover-organizer --verify-export organized-covers --strict` for read-only inspection of listed hashes plus unexpected files and symlinks. The default verification mode retains listed-copy verification. Strict mode adds `unexpected_paths` and fails verification when extras exist. The existing export metadata files `manifest.json` and `plan.json` are allowed; empty directories (including staging bookkeeping) are ignored. Manifest destinations must be safe relative paths, distinct under NFC/case folding, and use valid SHA-256 values. Root, manifest and listed-path symlinks are rejected. Legacy version 1 copy manifests remain supported. Inspection never removes extras, repairs copies, resumes exports, or authenticates the manifest.


New inventories and direct export plans reserve .copying, manifest.json and plan.json as top-level bookkeeping names (case-insensitive), before staging starts. Existing version 1 manifests may list copies under .copying/ from older exports: verification accepts those exact listed files with the same hash, duplicate-path, traversal and symlink checks as other copies. Strict mode still reports every unlisted file there.

New inventory targets and direct-plan targets use the same portable validation as manifest inspection: backslashes, redundant separators, traversal and trailing-dot/space aliases are rejected before staging.

## Version 1.2.2

Malformed CSV rows and duplicate column names now stop with an actionable error instead of dropping values or raising a traceback. Selected plans recalculate duplicate-content groups from the covers actually selected. Verification rejects boolean schema versions and inconsistent declared copy counts while retaining legacy manifests without a count.

Resume requires ordinary staging metadata files, rejects symlinks and unexpected staged files, and preserves those files for inspection. It still resumes matching incomplete copies and verifies every source and completed copy. Export targets reject Windows device names and invalid filename characters before creating staging. Report files use exclusive creation, so a concurrently created file is never overwritten.

Use a stable local folder while planning or copying; concurrent edits to source or staging are not a supported transaction mechanism. A manifest proves byte agreement with its supplied hashes, not the provenance of the artwork. Hard-link support is required for publishing copied files. SVG and other unsupported image formats can be copied but show an explicit unavailable-preview message.

Resume also handles an interruption immediately after the exclusive hard link is published: a matching owned partial is verified and retired, while a mismatched partial is preserved and reported as an error. Planning hashes source covers in bounded chunks rather than loading whole files into memory.

Resuming an incomplete copy also preserves the original when the staging file is a hard link to it.

Staging metadata and copied files must be ordinary regular files. FIFOs and other special entries are rejected before reading or hashing, so malformed staging cannot block on a pipe.
