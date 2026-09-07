# Development

Explicit author-assigned variants only. Preserve original files, source hashes, collision rejection and opt-in copy behavior. Reports with thumbnails are local and may contain private cover art.

## 1.2.0 improvement session

Add per-issue thumbnail selection, hash-verified export inspection and resumable copy staging with collision protection.

HTML contact sheets show up to 200 local thumbnails with per-cover selection; --reviewed-plan accepts only unchanged items from the current CSV-derived plan. --copy-to creates a new destination through a matching .DEST.partial plan; --resume retains verified completed copies and restarts incomplete staging copies after rechecking original source hashes. Final file publication uses exclusive hard links and requires filesystem hard-link support. Modified completed copies and case/Unicode collisions are rejected without overwrite. --verify-export DIRECTORY checks listed manifest hashes and reports verified/missing/modified; it does not authenticate the manifest or claim there are no extra files. Original covers remain unchanged. Pillow generates thumbnails, with oversized images rejected and unsupported previews explicitly unavailable.

Local formatting, lint, strict types and regression tests pass. Public release completion requires the protected CI/CodeQL matrix, tagged artifacts and matching Forge catalog/detail deployment.
