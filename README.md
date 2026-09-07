# Variant Cover Organizer

[![CI](https://github.com/loganpendragonmultiverse/variant-cover-organizer/actions/workflows/ci.yml/badge.svg)](https://github.com/loganpendragonmultiverse/variant-cover-organizer/actions/workflows/ci.yml)

Variant Cover Organizer converts an explicit CSV inventory into a safe grouping plan for comic cover variants. It validates source files, issue and variant labels, duplicate assignments, and destination collisions before optionally copying files into issue folders.

## Three-minute start

```bash
python -m pip install .
variant-cover-organizer examples/variants.csv --source examples/covers
variant-cover-organizer variants.csv --source covers --copy-to organized-covers --output plan.json
```

Planning is the default. Reports flag byte-identical covers by grouping the SHA-256 fingerprints already calculated for safety. `--copy-to` creates a new destination through a staged directory, preserves every source file, and writes `manifest.json` mapping each source to its destination and fingerprint. Paths in the CSV must be relative and remain inside the selected source folder.

The tool does not identify cover art, scrape publisher metadata, or decide whether visually similar images are official variants. The user supplies the issue and variant identities. Requires Python 3.10 or newer.

Part of the [Logan Pendragon Forge open-source collection](https://www.loganpendragonforge.com/open-source/). Licensed under the [MIT License](LICENSE).

## Version 1.2.0: reviewed improvements

Add per-issue thumbnail selection, hash-verified export inspection and resumable copy staging with collision protection.

```bash
variant-cover-organizer variants.csv --source ./covers --format html --output review.html
```

HTML contact sheets show up to 200 local thumbnails with per-cover selection; --reviewed-plan accepts only unchanged items from the current CSV-derived plan. --copy-to creates a new destination through a matching .DEST.partial plan; --resume retains verified completed copies and restarts incomplete staging copies after rechecking original source hashes. Final file publication uses exclusive hard links and requires filesystem hard-link support. Modified completed copies and case/Unicode collisions are rejected without overwrite. --verify-export DIRECTORY checks listed manifest hashes and reports verified/missing/modified; it does not authenticate the manifest or claim there are no extra files. Original covers remain unchanged. Pillow generates thumbnails, with oversized images rejected and unsupported previews explicitly unavailable.
