# Atlassian CLI PyOxidizer Release Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace PyInstaller with PyOxidizer for all standalone release assets, keep install scripts and updater working against the new artifacts, and lock the binary release contract with tests and CI.

**Architecture:** Introduce repository-owned PyOxidizer configuration and helper scripts that emit the same external asset names expected by installers and release consumers. Migrate CI and release workflows from PyInstaller smoke/build steps to PyOxidizer smoke/build steps, then update installer and updater behavior so standalone installs keep working while package-managed installs fail explicitly.

**Tech Stack:** Python 3.12, PyOxidizer, Rust toolchain in CI, GitHub Actions, shell/PowerShell installers, release workflow tests, updater tests

---

### Task 1: Add failing tests for PyOxidizer-based release workflow

**Files:**
- Modify: `tests/release/test_release_workflow.py`
- Test: `tests/release/test_release_workflow.py`

- [ ] **Step 1: Write the failing tests**

Add tests like:

```python
def test_release_workflow_invokes_pyoxidizer_for_standalone_builds() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text())
    steps = workflow["jobs"]["release"]["steps"]

    build = next(step for step in steps if step["name"] == "Build standalone artifact")

    assert "pyoxidizer" in build["run"].lower()
    assert "PyInstaller" not in build["run"]


def test_ci_workflow_uses_pyoxidizer_smoke_test() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text())
    steps = workflow["jobs"]["verify"]["steps"]
    step = next(step for step in steps if step["name"] == "Build PyOxidizer smoke test")

    assert "pyoxidizer" in step["run"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/release/test_release_workflow.py -q
```

Expected: FAIL because the repository still references PyInstaller.

- [ ] **Step 3: Implement the minimal workflow switch**

Edit workflow structure so:

- `.github/workflows/ci.yml` uses a `Build PyOxidizer smoke test` step
- `.github/workflows/release.yml` replaces `Build native binary` / `Build Linux binary` with a platform-aware PyOxidizer build step or helper-script invocation

Keep the existing asset packaging step names so installer and release contract tests continue to target the same public filenames.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/release/test_release_workflow.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml .github/workflows/release.yml tests/release/test_release_workflow.py
git commit -m "ci: switch release workflow to pyoxidizer"
```

### Task 2: Add repository-owned PyOxidizer configuration and smoke scripts

**Files:**
- Create: `pyoxidizer.bzl`
- Create: `.github/scripts/build-pyoxidizer-artifact.py`
- Modify: `tests/release/test_release_workflow.py`
- Test: `tests/release/test_release_workflow.py`

- [ ] **Step 1: Write the failing tests**

Add tests asserting the new repository-owned build inputs exist and are wired:

```python
def test_pyoxidizer_config_exists() -> None:
    assert Path("pyoxidizer.bzl").exists()


def test_release_workflow_uses_repo_pyoxidizer_helper_script() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text())
    steps = workflow["jobs"]["release"]["steps"]

    build = next(step for step in steps if step["name"] == "Build standalone artifact")
    assert ".github/scripts/build-pyoxidizer-artifact.py" in build["run"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/release/test_release_workflow.py::test_pyoxidizer_config_exists tests/release/test_release_workflow.py::test_release_workflow_uses_repo_pyoxidizer_helper_script -q
```

Expected: FAIL because the config and helper script do not exist yet.

- [ ] **Step 3: Add minimal implementation**

Create `pyoxidizer.bzl` and `.github/scripts/build-pyoxidizer-artifact.py` with the minimum repository-owned structure needed to:

- build a standalone executable for the current target
- stage files into a release-archive layout matching existing asset names
- smoke test the built executable with `--version` or `--help`

The helper script should accept explicit arguments like:

```bash
python .github/scripts/build-pyoxidizer-artifact.py \
  --target-os darwin \
  --target-arch arm64 \
  --version "${VERSION}" \
  --archive-format tar.gz
```

and write its unpacked bundle to:

```text
dist/pyoxidizer/<target-os>-<target-arch>/atlassian/
```

with the executable at:

```text
dist/pyoxidizer/<target-os>-<target-arch>/atlassian/atlassian
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/release/test_release_workflow.py::test_pyoxidizer_config_exists tests/release/test_release_workflow.py::test_release_workflow_uses_repo_pyoxidizer_helper_script -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyoxidizer.bzl .github/scripts/build-pyoxidizer-artifact.py tests/release/test_release_workflow.py
git commit -m "build: add repository pyoxidizer packaging entrypoint"
```

### Task 3: Adapt install scripts to the PyOxidizer bundle contract

**Files:**
- Modify: `install.sh`
- Modify: `install.ps1`
- Modify: `tests/release/test_install_script.py`
- Test: `tests/release/test_install_script.py`

- [ ] **Step 1: Write the failing tests**

Add installer tests that encode the new PyOxidizer bundle assumptions without changing public file names:

```python
def test_install_script_supports_pyoxidizer_bundle_layout() -> None:
    latest_json, downloads_root, _ = _write_bundle_release_fixture(tmp_path)
    archive = downloads_root / "v0.1.0" / "atlassian-cli_0.1.0_darwin_arm64.tar.gz"
    assert archive.exists()


def test_install_powershell_script_supports_pyoxidizer_bundle_layout() -> None:
    latest_json, downloads_root, _ = _write_bundle_release_fixture(tmp_path)
    archive = downloads_root / "v0.1.0" / "atlassian-cli_0.1.0_windows_amd64.zip"
    assert archive.exists()
```

Model the fixture after the actual PyOxidizer bundle layout you choose in Task 2, while preserving external archive names.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/release/test_install_script.py -q
```

Expected: FAIL because the installers only understand the old bundle assumptions.

- [ ] **Step 3: Implement the minimal installer changes**

Update `install.sh` and `install.ps1` so they:

- continue downloading the same release asset names
- validate the archive layout expected from PyOxidizer
- install the launcher and runtime bundle consistently
- do not change the Python package path behavior

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/release/test_install_script.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add install.sh install.ps1 tests/release/test_install_script.py
git commit -m "fix: support pyoxidizer release bundles in installers"
```

### Task 4: Make updater behavior explicit for package-managed installs

**Files:**
- Modify: `src/atlassian_cli/update.py`
- Modify: `tests/test_update.py`
- Test: `tests/test_update.py`

- [ ] **Step 1: Write the failing tests**

Add tests that distinguish binary installs from package-managed installs. Cover cases like:

```python
def test_update_install_rejects_package_managed_install(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(update_module, "_is_binary_install", lambda **_: False)
    result = runner.invoke(app, ["update", "install"])
    assert "uv tool upgrade" in result.stdout.lower() or result.stderr.lower()


def test_update_install_allows_binary_runtime_layout(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(update_module, "_is_binary_install", lambda **_: True)
    monkeypatch.setattr(update_command, "install_latest_release", lambda **_: InstallResult(version="0.1.12", install_dir=tmp_path, updated=True, message="ok"))
    result = runner.invoke(app, ["update", "install"])
    assert result.exit_code == 0
```

Use the existing helper style in `tests/test_update.py` and model install-origin detection from executable layout.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_update.py -q
```

Expected: FAIL because install-origin detection is not yet explicit enough.

- [ ] **Step 3: Implement the minimal runtime change**

Update `src/atlassian_cli/update.py` so it can distinguish:

- standalone binary installs that should use the installer flow
- package-managed installs that should fail with actionable guidance

The error message should tell users to upgrade through their package tool instead of pretending self-update is supported.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_update.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/update.py tests/test_update.py
git commit -m "feat: reject self-update for package installs"
```

### Task 5: Update README for the final dual-distribution state

**Files:**
- Modify: `README.md`
- Modify: `tests/test_readme.py`
- Test: `tests/test_readme.py`

- [ ] **Step 1: Write the failing tests**

Add README tests covering the final merged state:

```python
def test_readme_mentions_pyoxidizer_backed_binary_release_path() -> None:
    readme = Path("README.md").read_text().lower()
    assert "pyoxidizer" in readme


def test_readme_mentions_package_managers_should_upgrade_package_installs() -> None:
    readme = Path("README.md").read_text().lower()
    assert "uv tool upgrade" in readme or "package-managed installs" in readme
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_readme.py -q
```

Expected: FAIL because the README does not yet reflect the final PyOxidizer migration state.

- [ ] **Step 3: Update the README**

Revise README so it:

- keeps the wheel/sdist install path from the first branch
- updates binary-install wording to describe the PyOxidizer-backed standalone releases
- explains that `atlassian update install` is only for binary installs
- gives package-managed users the correct upgrade direction

Do not remove the wheel/sdist path added by the first branch.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_readme.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_readme.py
git commit -m "docs: document pyoxidizer release behavior"
```

### Task 6: Rebase on merged wheel branch and resolve shared workflow/docs conflicts

**Files:**
- Modify: `README.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/release.yml`
- Modify: `tests/release/*`

- [ ] **Step 1: Update branch base**

Run:

```bash
git fetch origin
git rebase origin/main
```

Expected: branch rebases onto `main` after the wheel/sdist work has merged.

- [ ] **Step 2: Resolve conflicts by preserving both distribution paths**

During conflict resolution, keep:

- wheel/sdist release job and docs from the first branch
- PyOxidizer standalone build path from this branch
- checksum scope limited to standalone archives

Expected end state:

- both install paths documented
- package assets still uploaded
- PyInstaller references removed

- [ ] **Step 3: Re-run focused regression tests**

Run:

```bash
.venv/bin/python -m pytest tests/release/test_release_workflow.py tests/release/test_install_script.py tests/test_update.py tests/test_readme.py -q
```

Expected: PASS after conflict resolution.

- [ ] **Step 4: Continue the rebase after conflict resolution**

If rebase stops for conflicts, continue with:

```bash
git add README.md .github/workflows/ci.yml .github/workflows/release.yml tests/release tests/test_update.py tests/test_readme.py
git rebase --continue
```

### Task 7: Run full repository verification and finalize the PyOxidizer branch

**Files:**
- Modify: all intended PyOxidizer migration files from prior tasks

- [ ] **Step 1: Run focused smoke checks**

Run:

```bash
.venv/bin/python -m pytest tests/release/test_release_workflow.py tests/release/test_install_script.py tests/test_update.py tests/test_readme.py -q
```

Expected: PASS.

- [ ] **Step 2: Run repository verification**

Run:

```bash
.venv/bin/ruff format --check .
.venv/bin/python -m pytest -q
.venv/bin/ruff check README.md pyproject.toml src tests docs
```

Expected: all commands PASS.

- [ ] **Step 3: Run a local standalone smoke check**

Run the repository-owned PyOxidizer helper for the current platform and then execute the produced binary:

```bash
.venv/bin/python .github/scripts/build-pyoxidizer-artifact.py --target-os darwin --target-arch arm64 --version 0.1.12 --archive-format tar.gz
```

Then run the produced executable with:

```bash
dist/pyoxidizer/darwin-arm64/atlassian/atlassian --version
```

Expected: prints the repository version and exits 0.

- [ ] **Step 4: Inspect git state**

Run:

```bash
git status --short
```

Expected: only intended files are modified.

- [ ] **Step 5: Create the final branch commit**

```bash
git add README.md .github/workflows/ci.yml .github/workflows/release.yml install.sh install.ps1 src/atlassian_cli/update.py pyoxidizer.bzl .github/scripts/build-pyoxidizer-artifact.py tests/release tests/test_update.py tests/test_readme.py
git commit -m "feat: migrate standalone releases to pyoxidizer"
```

Expected: commit succeeds and leaves the branch ready to merge after the wheel branch rebase.
