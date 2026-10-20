# Development

Explicit author-assigned variants only. Preserve original files, source hashes, collision rejection and opt-in copy behavior. Reports with thumbnails are local and may contain private cover art.

## 1.2.0 improvement session

Add per-issue thumbnail selection, hash-verified export inspection and resumable copy staging with collision protection.

HTML contact sheets show up to 200 local thumbnails with per-cover selection; --reviewed-plan accepts only unchanged items from the current CSV-derived plan. --copy-to creates a new destination through a matching .DEST.partial plan; --resume retains verified completed copies and restarts incomplete staging copies after rechecking original source hashes. Final file publication uses exclusive hard links and requires filesystem hard-link support. Modified completed copies and case/Unicode collisions are rejected without overwrite. --verify-export DIRECTORY checks listed manifest hashes and reports verified/missing/modified; it does not authenticate the manifest or claim there are no extra files. Original covers remain unchanged. Pillow generates thumbnails, with oversized images rejected and unsupported previews explicitly unavailable.

Local formatting, lint, strict types and regression tests pass. Public release completion requires the protected CI/CodeQL matrix, tagged artifacts and matching Forge catalog/detail deployment.


## Version 1.2.1

Use `variant-cover-organizer --verify-export organized-covers --strict` for read-only inspection of listed hashes plus unexpected files and symlinks. The default verification mode retains listed-copy verification. Strict mode adds `unexpected_paths` and fails verification when extras exist. The existing export metadata files `manifest.json` and `plan.json` are allowed; empty directories (including staging bookkeeping) are ignored. Manifest destinations must be safe relative paths, distinct under NFC/case folding, and use valid SHA-256 values. Root, manifest and listed-path symlinks are rejected. Legacy version 1 copy manifests remain supported. Inspection never removes extras, repairs copies, resumes exports, or authenticates the manifest.


New inventories and direct export plans reserve .copying, manifest.json and plan.json as top-level bookkeeping names (case-insensitive), before staging starts. Existing version 1 manifests may list copies under .copying/ from older exports: verification accepts those exact listed files with the same hash, duplicate-path, traversal and symlink checks as other copies. Strict mode still reports every unlisted file there.

New inventory targets and direct-plan targets use the same portable validation as manifest inspection: backslashes, redundant separators, traversal and trailing-dot/space aliases are rejected before staging.

## Gold completion, version 1.2.2

Preserve the explicit-identity boundary and the existing no-overwrite copy workflow. The completion pass rejects ambiguous CSV input, validates manifest schema/count consistency, guards resumed staging metadata and unrelated files, enforces portable target names, recalculates selected duplicate groups, and creates reports exclusively. Do not weaken the existing supported-platform CI, dependency audit, coverage threshold, CodeQL or release-artifact gates.

The source distribution includes these development/testing instructions and the synthetic examples. Wheel users can obtain examples from the matching source distribution or tagged repository. Gold remains version-bound and limited to the documented workflow; publisher lookup, artwork recognition, authenticated manifests and concurrent filesystem transactions remain outside scope.

Resume also handles an interruption immediately after the exclusive hard link is published: a matching owned partial is verified and retired, while a mismatched partial is preserved and reported as an error. Planning hashes source covers in bounded chunks rather than loading whole files into memory.

Restarting an incomplete plan-owned copy creates a fresh inode exclusively; it never truncates an existing inode that could also be a hard link to a source file. The hard-link regression uses only synthetic files.

Staging metadata and copied files must be ordinary regular files. FIFOs and other special entries are rejected before reading or hashing, so malformed staging cannot block on a pipe.
