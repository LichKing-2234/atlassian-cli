# Atlassian CLI Wheel Release Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add wheel and sdist assets to tagged GitHub Releases, document `uv tool install` from GitHub Release artifacts, and lock the package release contract with tests and CI.

**Architecture:** Extend the existing GitHub Actions release pipeline with a package-assets job that builds and uploads wheel/sdist artifacts without changing binary install/update behavior. Keep the Python package path documentation and tests strictly separate from standalone binary install scripts so the package path is additive, not a hybrid installer.

**Tech Stack:** Python 3.12, `python -m build`, GitHub Actions, release workflow tests, README contract tests, existing project `.venv`

---

### Task 1: Add failing tests for wheel and sdist release assets

**Files:**
- Modify: `tests/release/test_release_workflow.py`
- Test: `tests/release/test_release_workflow.py`

- [ ] **Step 1: Write the failing tests**

Add tests that assert:

```python
def test_release_workflow_builds_python_package_assets() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text())

    package_job = workflow["jobs"]["python-package"]
    steps = package_job["steps"]

    build_step = next(step for step in steps if step["name"] == "Build python package assets")
    upload_step = next(step for step in steps if step.get("uses") == "softprops/action-gh-release@v2")

    assert package_job["needs"] == ["prepare", "verify"]
    assert "python -m build" in build_step["run"]
    assert upload_step["with"]["files"] == "dist/*"


def test_release_workflow_keeps_checksums_scoped_to_binary_assets() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text())

    build_step = next(
        step
        for step in workflow["jobs"]["checksums"]["steps"]
        if step["name"] == "Build release checksums"
    )

    assert "atlassian-cli_*.tar.gz" in build_step["run"]
    assert "atlassian-cli_*.zip" in build_step["run"]
    assert "atlassian_cli-" not in build_step["run"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/release/test_release_workflow.py -q
```

Expected: FAIL because `python-package` job and package upload assertions do not exist yet.

- [ ] **Step 3: Implement the release workflow changes**

Update `.github/workflows/release.yml` so it includes a `python-package` job after `verify` with steps equivalent to:

```yaml
  python-package:
    needs: [prepare, verify]
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v6
        with:
          ref: ${{ needs.prepare.outputs.checkout_ref }}
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: '3.12'
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e '.[dev]'

      - name: Build python package assets
        run: python -m build

      - name: Upload python package assets
        uses: softprops/action-gh-release@v2
        with:
          token: ${{ secrets.RELEASE_TOKEN || github.token }}
          tag_name: ${{ needs.prepare.outputs.tag }}
          target_commitish: ${{ needs.prepare.outputs.commit_sha }}
          prerelease: ${{ needs.prepare.outputs.is_prerelease == 'true' }}
          body_path: release-notes.md
          overwrite_files: true
          files: dist/*
```

Also update `checksums.needs` to:

```yaml
needs: [prepare, python-package, release]
```

while keeping checksum generation itself scoped to standalone archives.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/release/test_release_workflow.py -q
```

Expected: PASS with the new package-asset workflow assertions green.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/release.yml tests/release/test_release_workflow.py
git commit -m "ci: publish wheel assets in release workflow"
```

### Task 2: Add CI coverage for package asset validation

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/release/test_release_workflow.py`
- Test: `tests/release/test_release_workflow.py`

- [ ] **Step 1: Write the failing test**

Add a CI workflow contract test:

```python
def test_ci_workflow_builds_python_packages_without_pyinstaller_smoke() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text())
    steps = workflow["jobs"]["verify"]["steps"]
    names = [step["name"] for step in steps]

    assert "Build package" in names
    assert "Build release binary smoke test" not in names
    assert "Build PyOxidizer smoke test" not in names
```

This branch intentionally handles only the wheel/sdist path, so it should remove the old PyInstaller smoke without adding the PyOxidizer smoke yet.

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/release/test_release_workflow.py::test_ci_workflow_builds_python_packages_without_pyinstaller_smoke -q
```

Expected: FAIL because the CI workflow still contains the PyInstaller smoke step.

- [ ] **Step 3: Implement the minimal CI change**

Edit `.github/workflows/ci.yml` so the `verify` job keeps:

```yaml
      - name: Build package
        run: python -m build
```

and removes the current PyInstaller smoke block entirely in this branch.

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
.venv/bin/python -m pytest tests/release/test_release_workflow.py::test_ci_workflow_builds_python_packages_without_pyinstaller_smoke -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml tests/release/test_release_workflow.py
git commit -m "ci: drop pyinstaller smoke from verify workflow"
```

### Task 3: Add README contract tests for package installation guidance

**Files:**
- Modify: `README.md`
- Modify: `tests/test_readme.py`
- Test: `tests/test_readme.py`

- [ ] **Step 1: Write the failing tests**

Add README tests like:

```python
def test_readme_mentions_uv_tool_install_from_release_assets() -> None:
    readme = Path("README.md").read_text()

    assert "uv tool install" in readme
    assert ".whl" in readme
    assert "GitHub Release" in readme


def test_readme_scopes_update_install_to_binary_installs() -> None:
    readme = Path("README.md").read_text().lower()

    assert "binary install" in readme
    assert "atlassian update install" in readme
    assert "package-managed installs" in readme
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_readme.py -q
```

Expected: FAIL because the README does not yet describe the package-install path or update scoping.

- [ ] **Step 3: Update the README**

Revise the install and update sections so they include:

- a `Python Package Install From GitHub Release` section
- a versioned wheel URL example such as:

```bash
uv tool install \
  https://github.com/LichKing-2234/atlassian-cli/releases/download/v0.1.12/atlassian_cli-0.1.12-py3-none-any.whl
```

- a local-file example such as:

```bash
uv tool install ./atlassian_cli-0.1.12-py3-none-any.whl
```

- explicit wording that `atlassian update install` only applies to standalone binary installs

Keep the repository install URLs real and keep all non-functional sample values on approved placeholders.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_readme.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_readme.py
git commit -m "docs: add uv tool install release asset guidance"
```

### Task 4: Add update-path tests that preserve binary-only updater scope

**Files:**
- Modify: `tests/test_update.py`
- Test: `tests/test_update.py`

- [ ] **Step 1: Write the failing tests**

Add tests that codify current branch intent without changing runtime behavior yet:

```python
def test_update_install_docs_and_urls_still_target_binary_installers() -> None:
    assert install_script_url_for_tag("0.2.0").endswith("/install.sh")
    assert install_script_url_for_tag("0.2.0", platform="win32").endswith("/install.ps1")
```

and a release-contract naming check:

```python
def test_package_version_matches_release_build_contract() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    assert pyproject["project"]["name"] == "atlassian-cli"
```

This task keeps update tests aligned while the runtime behavior itself stays unchanged in the wheel branch.

- [ ] **Step 2: Run tests to verify the new assertions behave as expected**

Run:

```bash
.venv/bin/python -m pytest tests/test_update.py -q
```

Expected: PASS or targeted failure only if the added assertions exposed a contract mismatch. Fix the test content, not runtime behavior, if the failure is caused by a wrong assertion.

- [ ] **Step 3: Keep the test file consistent with the new release contract**

Update test descriptions or helper expectations so they clearly separate:

- package-release assets
- binary install/update assets

Do not modify `src/atlassian_cli/update.py` in this branch.

- [ ] **Step 4: Re-run the test file**

Run:

```bash
.venv/bin/python -m pytest tests/test_update.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_update.py
git commit -m "test: clarify binary updater contract"
```

### Task 5: Run branch verification and finalize the wheel/sdist worktree

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/release.yml`
- Modify: `README.md`
- Modify: `tests/release/test_release_workflow.py`
- Modify: `tests/test_readme.py`
- Modify: `tests/test_update.py`

- [ ] **Step 1: Run focused verification**

Run:

```bash
.venv/bin/python -m pytest tests/release/test_release_workflow.py tests/test_readme.py tests/test_update.py -q
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

- [ ] **Step 3: Inspect git state**

Run:

```bash
git status --short
```

Expected: only intended tracked files are modified and ready to commit.

- [ ] **Step 4: Create the final branch commit**

```bash
git add README.md .github/workflows/ci.yml .github/workflows/release.yml tests/release/test_release_workflow.py tests/test_readme.py tests/test_update.py
git commit -m "feat: add release wheel distribution path"
```

Expected: commit succeeds and leaves the branch with a clean logical end-state for the wheel/sdist worktree.
