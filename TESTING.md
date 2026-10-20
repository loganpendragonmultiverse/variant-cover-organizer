# Testing

Run `ruff format --check .`, `ruff check .`, `mypy src`, `pytest`, and `python -m build`. CI also audits dependencies and runs the supported OS/Python matrix.

## 1.2.0 regression acceptance

Run the complete existing suite plus the new regression fixtures. Confirm the documented command produces the selected output, malformed input remains actionable, and source files remain unchanged. Add per-issue thumbnail selection, hash-verified export inspection and resumable copy staging with collision protection.

## Feature-wave regression gate

Run `ruff format --check .`, `ruff check .`, `mypy src`, `pytest`, and `python -m build` after installing `.[dev]` in an isolated environment. The focused regressions are in `tests/test_feature_wave.py`; run them together with the existing suite. Keep the configured coverage threshold. Repository CI supplies the supported OS/Python matrix.

Review-hold regressions cover new reserved issue IDs/direct plans, the tool's own valid exports, and legacy .copying/ manifests with listed copies plus unexpected files. Existing unsafe-path and symlink regressions remain required.

Direct-plan regressions include Windows backslash and trailing-dot/space aliases and assert that neither destination nor staging is created.

## Gold completion acceptance

Run the complete suite including `tests/test_gold_completion.py`. Its regressions cover short/long CSV rows, duplicate headers, selected duplicate groups, boolean manifest versions, inconsistent counts, Windows device targets, unrelated staged files, metadata symlinks and a report-path creation race. Existing interrupted-copy resume and legacy `.copying/` manifest tests remain required.

Build both wheel and source distribution. Install each in a clean environment away from the repository and run the complete suite with the installed package, then execute the shipped source examples, create/resume a synthetic export, and verify strict inspection and source hash preservation. Inspect the generated HTML review at desktop and mobile widths in Chromium, Firefox and WebKit: select a subset, download its JSON, and feed it back through `--reviewed-plan`. Confirm unsupported previews are labeled, keyboard controls work and no unexpected network requests occur. Never test against real cover collections.

Resume also handles an interruption immediately after the exclusive hard link is published: a matching owned partial is verified and retired, while a mismatched partial is preserved and reported as an error. Planning hashes source covers in bounded chunks rather than loading whole files into memory.

Restarting an incomplete plan-owned copy creates a fresh inode exclusively; it never truncates an existing inode that could also be a hard link to a source file. The hard-link regression uses only synthetic files.

Staging metadata and copied files must be ordinary regular files. FIFOs and other special entries are rejected before reading or hashing, so malformed staging cannot block on a pipe.
