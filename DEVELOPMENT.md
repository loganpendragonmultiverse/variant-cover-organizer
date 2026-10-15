# Development

Explicit author-assigned variants only. Preserve original files, source hashes, collision rejection and opt-in copy behavior. Reports with thumbnails are local and may contain private cover art.

## 1.2.0 improvement session

Add per-issue thumbnail selection, hash-verified export inspection and resumable copy staging with collision protection.

HTML contact sheets show up to 200 local thumbnails with per-cover selection; --reviewed-plan accepts only unchanged items from the current CSV-derived plan. --copy-to creates a new destination through a matching .DEST.partial plan; --resume retains verified completed copies and restarts incomplete staging copies after rechecking original source hashes. Final file publication uses exclusive hard links and requires filesystem hard-link support. Modified completed copies and case/Unicode collisions are rejected without overwrite. --verify-export DIRECTORY checks listed manifest hashes and reports verified/missing/modified; it does not authenticate the manifest or claim there are no extra files. Original covers remain unchanged. Pillow generates thumbnails, with oversized images rejected and unsupported previews explicitly unavailable.

Local formatting, lint, strict types and regression tests pass. Public release completion requires the protected CI/CodeQL matrix, tagged artifacts and matching Forge catalog/detail deployment.


## 1.2.1 candidate

Use `variant-cover-organizer --verify-export organized-covers --strict` for read-only inspection of listed hashes plus unexpected files and symlinks. The default verification mode retains listed-copy verification. Strict mode adds `unexpected_paths` and fails verification when extras exist. The existing export metadata files `manifest.json` and `plan.json` are allowed; empty directories (including staging bookkeeping) are ignored. Manifest destinations must be safe relative paths, distinct under NFC/case folding, and use valid SHA-256 values. Root, manifest and listed-path symlinks are rejected. Legacy version 1 copy manifests remain supported. Inspection never removes extras, repairs copies, resumes exports, or authenticates the manifest.


New inventories and direct export plans reserve .copying, manifest.json and plan.json as top-level bookkeeping names (case-insensitive), before staging starts. Existing version 1 manifests may list copies under .copying/ from older exports: verification accepts those exact listed files with the same hash, duplicate-path, traversal and symlink checks as other copies. Strict mode still reports every unlisted file there.
