# Testing

Run `ruff format --check .`, `ruff check .`, `mypy src`, `pytest`, and `python -m build`. CI also audits dependencies and runs the supported OS/Python matrix.

## 1.2.0 regression acceptance

Run the complete existing suite plus the new regression fixtures. Confirm the documented command produces the selected output, malformed input remains actionable, and source files remain unchanged. Add per-issue thumbnail selection, hash-verified export inspection and resumable copy staging with collision protection.

## Feature-wave regression gate

Run `ruff format --check .`, `ruff check .`, `mypy src`, `pytest`, and `python -m build` after installing `.[dev]` in an isolated environment. The focused regressions are in `tests/test_feature_wave.py`; run them together with the existing suite. Keep the configured coverage threshold. Repository CI supplies the supported OS/Python matrix.

Review-hold regressions cover new reserved issue IDs/direct plans, the tool's own valid exports, and legacy .copying/ manifests with listed copies plus unexpected files. Existing unsafe-path and symlink regressions remain required.
