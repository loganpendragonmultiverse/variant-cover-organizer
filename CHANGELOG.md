# Changelog

## 1.2.2 - 2026-10-20

- Recover the post-link interruption window without publishing leftover partial files; preserve mismatches.
- Restart incomplete copies with a fresh inode so staging hard links cannot truncate source files.
- Stream source hashing rather than reading complete covers into memory.
- Reject special staging/manifest files before reading or hashing to avoid blocking on pipes.
- Refuse pre-existing dangling output symlinks explicitly across supported platforms.
- Reject malformed or ambiguous CSV rows and recompute duplicate groups for selected covers.
- Refuse symlinked staging metadata and unexpected staged files without deleting them.
- Validate manifest versions and declared counts while retaining safe legacy manifests.
- Reject nonportable device targets and create report files exclusively.
- Include development/testing instructions in the source distribution and document the bounded Gold scope.

## 1.2.1 - 2026-10-16

- Apply shared portable target validation before staging, including Windows backslash and trailing-dot/space aliases.

- Reserve staging/metadata names for new export plans while retaining safe verification of legacy .copying/ manifest copies.

- Add optional strict read-only export inspection and reject unsafe manifest paths.

## 1.2.0 - 2026-09-07

- Add per-issue thumbnail selection, hash-verified export inspection and resumable copy staging with collision protection.
- Added regression coverage for the audited behavior and invalid inputs.

## 1.1.0 - 2026-07-27

- Added byte-identical cover reporting using the existing SHA-256 planning fingerprints.
- Added an export manifest mapping each source and destination to its verified fingerprint.

## 1.0.0 - 2026-07-26

- Added CSV-based issue and variant grouping plans.
- Added duplicate, path, source, and destination validation.
- Added opt-in staged copy export that preserves original files.
