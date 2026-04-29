# Atlassian CLI GitHub Actions Release Binaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add GitHub Actions gating for `main` and `release/*`, publish installable `linux/amd64` and `darwin/arm64` binaries from GitHub Releases, and provide a repository-owned installer script.

**Architecture:** Keep the implementation close to the `ai-efficiency` reference repository with separate `.github/workflows/ci.yml` and `.github/workflows/release.yml` files, but replace GoReleaser with a checked-in PyInstaller build path. Add one repository-root `install.sh` that downloads release tarballs from `example-org/example-repo`, verifies SHA-256 checksums, and installs `atlassian` into a local bin directory without requiring Python on the target machine.

**Tech Stack:** Python 3.12+, Hatchling, PyInstaller, Ruff, Pytest, GitHub Actions, POSIX shell

---

## Planned File Structure

### Create

- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `atlassian.spec`
- `install.sh`
- `tests/release/test_install_script.py`

### Modify

- `.gitignore`
- `pyproject.toml`
- `README.md`

### Responsibility Notes

- `pyproject.toml` owns dev dependencies for CI and release packaging plus the minimal Ruff configuration used locally and in GitHub Actions.
- `.gitignore` keeps build artifacts from `python -m build` and PyInstaller out of git status noise.
- `atlassian.spec` is the single source of truth for PyInstaller entrypoint configuration so local builds and release workflow builds use the same executable layout.
- `install.sh` owns platform detection, release tag resolution, checksum verification, and atomic local installation.
- `tests/release/test_install_script.py` owns installer coverage by exercising `install.sh` through `subprocess` with local file-based fake release assets.
- `.github/workflows/ci.yml` owns branch-gating verification.
- `.github/workflows/release.yml` owns tag-driven and manual release publication to GitHub Releases.
- `README.md` owns user-facing CI, release, and installation guidance.

### Common Commands

- Refresh dev environment: `.venv/bin/python -m pip install --upgrade pip && .venv/bin/python -m pip install -e '.[dev]'`
- Installer tests: `.venv/bin/python -m pytest tests/release/test_install_script.py -v`
- Existing suite plus installer tests: `.venv/bin/python -m pytest -q`
- Lint: `.venv/bin/ruff check .`
- Format check: `.venv/bin/ruff format --check .`
- Package build: `.venv/bin/python -m build`
- PyInstaller smoke build: `.venv/bin/pyinstaller atlassian.spec --clean --noconfirm`

## Task 1: Add Local Build and Lint Tooling

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Create: `atlassian.spec`

- [ ] **Step 1: Run the current package and binary build commands to capture the failures**

Run:

```bash
.venv/bin/python -m build
.venv/bin/pyinstaller atlassian.spec --clean --noconfirm
```

Expected:

- `python -m build` fails because `build` is not installed in the current dev extras
- `pyinstaller` fails because the dependency and spec file do not exist yet

- [ ] **Step 2: Update `pyproject.toml` with the required dev dependencies and Ruff configuration**

Replace the current `[project.optional-dependencies]` block and append the Ruff configuration:

```toml
[project.optional-dependencies]
dev = [
  "build>=1.2.2",
  "pyinstaller>=6.16.0",
  "pytest>=8.3.0",
  "ruff>=0.11.8",
]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I"]
ignore = ["E501"]
```

- [ ] **Step 3: Update `.gitignore` so local release artifacts stay out of git status**

Append these lines to `.gitignore`:

```gitignore
build/
dist/
*.egg-info/
```

- [ ] **Step 4: Add a checked-in PyInstaller spec file**

Create `atlassian.spec` with this content:

```python
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"


a = Analysis(
    [str(SRC_ROOT / "atlassian_cli" / "main.py")],
    pathex=[str(SRC_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="atlassian",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
```

- [ ] **Step 5: Refresh the editable dev environment with the new tooling**

Run:

```bash
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
```

Expected:

- pip installs `build`, `pyinstaller`, and `ruff`
- the editable install still succeeds for `atlassian-cli`

- [ ] **Step 6: Run the package build, lint, and binary smoke checks**

Run:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m build
.venv/bin/pyinstaller atlassian.spec --clean --noconfirm
./dist/atlassian --help >/dev/null
```

Expected:

- `ruff check .` passes
- `python -m build` produces `dist/atlassian_cli-0.1.0.tar.gz` and a wheel
- `pyinstaller` writes `dist/atlassian`
- `./dist/atlassian --help` exits `0`

- [ ] **Step 7: Commit the build-tooling changes**

```bash
git add pyproject.toml .gitignore atlassian.spec
git commit -m "chore: add release build tooling"
```

## Task 2: Add Installer Coverage and Implement `install.sh`

**Files:**
- Create: `tests/release/test_install_script.py`
- Create: `install.sh`

- [ ] **Step 1: Write the failing installer tests**

Create `tests/release/test_install_script.py` with this content:

```python
import hashlib
import json
import os
import stat
import subprocess
import tarfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = REPO_ROOT / "install.sh"


def _write_release_fixture(
    tmp_path: Path,
    *,
    tag: str = "v0.1.0",
    checksum_mismatch: bool = False,
) -> tuple[Path, Path, str]:
    downloads_root = tmp_path / "downloads"
    release_dir = downloads_root / tag
    release_dir.mkdir(parents=True)

    payload_dir = tmp_path / "payload"
    payload_dir.mkdir()
    binary_path = payload_dir / "atlassian"
    binary_path.write_text("#!/bin/sh\necho fixture-atlassian\n")
    binary_path.chmod(binary_path.stat().st_mode | stat.S_IXUSR)

    archive_name = "atlassian-cli_0.1.0_linux_amd64.tar.gz"
    archive_path = release_dir / archive_name
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(binary_path, arcname="atlassian")

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if checksum_mismatch:
        digest = "0" * 64
    (release_dir / "checksums.txt").write_text(f"{digest}  {archive_name}\n")

    latest_json = tmp_path / "latest.json"
    latest_json.write_text(json.dumps({"tag_name": tag}))
    return latest_json, downloads_root, archive_name


def test_install_script_installs_latest_linux_binary(tmp_path: Path) -> None:
    latest_json, downloads_root, _ = _write_release_fixture(tmp_path)
    install_dir = tmp_path / "bin"

    result = subprocess.run(
        ["sh", str(INSTALL_SCRIPT)],
        cwd=tmp_path,
        env=os.environ
        | {
            "HOME": str(tmp_path / "home"),
            "INSTALL_DIR": str(install_dir),
            "INSTALL_RELEASE_API_URL": latest_json.resolve().as_uri(),
            "INSTALL_RELEASE_DOWNLOAD_BASE": downloads_root.resolve().as_uri(),
            "INSTALL_TEST_OS": "Linux",
            "INSTALL_TEST_ARCH": "x86_64",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    installed_binary = install_dir / "atlassian"
    assert installed_binary.exists()
    assert os.access(installed_binary, os.X_OK)

    run_result = subprocess.run(
        [str(installed_binary)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert run_result.stdout.strip() == "fixture-atlassian"


def test_install_script_rejects_unsupported_platform(tmp_path: Path) -> None:
    result = subprocess.run(
        ["sh", str(INSTALL_SCRIPT)],
        cwd=tmp_path,
        env=os.environ
        | {
            "HOME": str(tmp_path / "home"),
            "INSTALL_DIR": str(tmp_path / "bin"),
            "INSTALL_VERSION": "v0.1.0",
            "INSTALL_TEST_OS": "Darwin",
            "INSTALL_TEST_ARCH": "x86_64",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "unsupported platform" in result.stderr.lower()


def test_install_script_fails_on_checksum_mismatch(tmp_path: Path) -> None:
    latest_json, downloads_root, _ = _write_release_fixture(
        tmp_path,
        checksum_mismatch=True,
    )

    result = subprocess.run(
        ["sh", str(INSTALL_SCRIPT)],
        cwd=tmp_path,
        env=os.environ
        | {
            "HOME": str(tmp_path / "home"),
            "INSTALL_DIR": str(tmp_path / "bin"),
            "INSTALL_VERSION": "v0.1.0",
            "INSTALL_RELEASE_API_URL": latest_json.resolve().as_uri(),
            "INSTALL_RELEASE_DOWNLOAD_BASE": downloads_root.resolve().as_uri(),
            "INSTALL_TEST_OS": "Linux",
            "INSTALL_TEST_ARCH": "x86_64",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "checksum mismatch" in result.stderr.lower()
```

- [ ] **Step 2: Run the installer tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/release/test_install_script.py -v
```

Expected:

- FAIL with `AssertionError` or shell exit errors because `install.sh` does not exist yet

- [ ] **Step 3: Implement `install.sh`**

Create `install.sh` with this content:

```sh
#!/bin/sh
set -eu

REPO_OWNER="example-org"
REPO_NAME="atlassian-cli"
INSTALL_DIR="${INSTALL_DIR:-${HOME}/.local/bin}"
INSTALL_RELEASE_API_URL="${INSTALL_RELEASE_API_URL:-https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest}"
INSTALL_RELEASE_DOWNLOAD_BASE="${INSTALL_RELEASE_DOWNLOAD_BASE:-https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download}"

TMP_ROOT=""

log() {
  printf '%s\n' "$*" >&2
}

die() {
  log "error: $*"
  exit 1
}

cleanup() {
  if [ -n "${TMP_ROOT}" ] && [ -d "${TMP_ROOT}" ]; then
    rm -rf "${TMP_ROOT}"
  fi
}

trap cleanup EXIT INT TERM

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

detect_os() {
  raw_os="${INSTALL_TEST_OS:-$(uname -s)}"
  raw_os="$(printf '%s' "${raw_os}" | tr '[:upper:]' '[:lower:]')"
  case "${raw_os}" in
    linux)
      printf 'linux'
      ;;
    darwin)
      printf 'darwin'
      ;;
    *)
      die "unsupported operating system: ${raw_os}"
      ;;
  esac
}

detect_arch() {
  raw_arch="${INSTALL_TEST_ARCH:-$(uname -m)}"
  case "${raw_arch}" in
    x86_64|amd64)
      printf 'amd64'
      ;;
    aarch64|arm64)
      printf 'arm64'
      ;;
    *)
      die "unsupported architecture: ${raw_arch}"
      ;;
  esac
}

ensure_supported_target() {
  target="${1}/${2}"
  case "${target}" in
    linux/amd64|darwin/arm64)
      ;;
    *)
      die "unsupported platform: ${target}"
      ;;
  esac
}

resolve_tag() {
  if [ -n "${INSTALL_VERSION:-}" ]; then
    printf '%s' "${INSTALL_VERSION}"
    return
  fi

  metadata="$(curl -fsSL "${INSTALL_RELEASE_API_URL}")" || die "failed to resolve latest release"
  tag="$(printf '%s' "${metadata}" | tr -d '\n' | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
  [ -n "${tag}" ] || die "failed to parse tag_name from release metadata"
  printf '%s' "${tag}"
}

archive_name() {
  version="${1#v}"
  printf 'atlassian-cli_%s_%s_%s.tar.gz' "${version}" "${2}" "${3}"
}

checksum_for_archive() {
  archive_name="$1"
  checksums_file="$2"
  awk -v target="${archive_name}" '$2 == target {print $1}' "${checksums_file}"
}

sha256_file() {
  target_file="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${target_file}" | awk '{print $1}'
    return
  fi
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${target_file}" | awk '{print $1}'
    return
  fi
  die "missing required command: sha256sum or shasum"
}

verify_archive_layout() {
  archive_path="$1"
  listing="$(tar -tzf "${archive_path}")"
  [ "${listing}" = "atlassian" ] || die "archive must contain a top-level atlassian binary"
}

install_binary() {
  archive_path="$1"
  destination_dir="$2"
  extract_dir="${TMP_ROOT}/extract"
  temp_binary="${destination_dir}/.atlassian.tmp.$$"

  mkdir -p "${extract_dir}" "${destination_dir}"
  tar -xzf "${archive_path}" -C "${extract_dir}"
  [ -f "${extract_dir}/atlassian" ] || die "archive did not extract an atlassian binary"

  chmod +x "${extract_dir}/atlassian"
  cp "${extract_dir}/atlassian" "${temp_binary}"
  chmod +x "${temp_binary}"
  mv "${temp_binary}" "${destination_dir}/atlassian"
}

main() {
  require_cmd curl
  require_cmd tar

  os_name="$(detect_os)"
  arch_name="$(detect_arch)"
  ensure_supported_target "${os_name}" "${arch_name}"

  release_tag="$(resolve_tag)"
  archive="$(archive_name "${release_tag}" "${os_name}" "${arch_name}")"

  TMP_ROOT="$(mktemp -d)"
  archive_path="${TMP_ROOT}/${archive}"
  checksums_path="${TMP_ROOT}/checksums.txt"

  curl -fsSL "${INSTALL_RELEASE_DOWNLOAD_BASE}/${release_tag}/${archive}" -o "${archive_path}"
  curl -fsSL "${INSTALL_RELEASE_DOWNLOAD_BASE}/${release_tag}/checksums.txt" -o "${checksums_path}"

  expected_checksum="$(checksum_for_archive "${archive}" "${checksums_path}")"
  [ -n "${expected_checksum}" ] || die "missing checksum entry for ${archive}"

  actual_checksum="$(sha256_file "${archive_path}")"
  [ "${actual_checksum}" = "${expected_checksum}" ] || die "checksum mismatch for ${archive}"

  verify_archive_layout "${archive_path}"
  install_binary "${archive_path}" "${INSTALL_DIR}"

  printf 'installed %s to %s/atlassian\n' "${release_tag}" "${INSTALL_DIR}"
  case ":${PATH}:" in
    *":${INSTALL_DIR}:"*)
      ;;
    *)
      printf 'add %s to PATH to run atlassian directly\n' "${INSTALL_DIR}" >&2
      ;;
  esac
}

main "$@"
```

- [ ] **Step 4: Mark the installer executable**

Run:

```bash
chmod +x install.sh
```

Expected:

- `install.sh` becomes executable for local testing and for direct raw GitHub download usage

- [ ] **Step 5: Run the installer tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/release/test_install_script.py -v
```

Expected:

- all three tests pass
- the success-path test leaves an executable `atlassian` file in the temporary install directory

- [ ] **Step 6: Commit the installer changes**

```bash
git add install.sh tests/release/test_install_script.py
git commit -m "feat: add github release installer"
```

## Task 3: Add the Gating Workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write `.github/workflows/ci.yml`**

Create `.github/workflows/ci.yml` with this content:

```yaml
name: CI

'on':
  pull_request:
  push:
    branches:
      - main
      - 'release/*'

permissions:
  contents: read

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e '.[dev]'

      - name: Lint
        run: ruff check .

      - name: Format check
        run: ruff format --check .

      - name: Run tests
        run: python -m pytest -q

      - name: Build package
        run: python -m build

      - name: Build release binary smoke test
        run: |
          pyinstaller atlassian.spec --clean --noconfirm
          ./dist/atlassian --help >/dev/null
```

- [ ] **Step 2: Validate the workflow structure locally**

Run:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import yaml

workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text())
assert "pull_request" in workflow["on"]
assert workflow["on"]["push"]["branches"] == ["main", "release/*"]
assert workflow["jobs"]["verify"]["runs-on"] == "ubuntu-latest"
step_names = [step["name"] for step in workflow["jobs"]["verify"]["steps"]]
assert step_names[-1] == "Build release binary smoke test"
PY
```

Expected:

- the script exits `0`
- the workflow contains one stable `verify` job suitable for branch protection

- [ ] **Step 3: Run the same verification commands locally once before committing the workflow**

Run:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m pytest -q
.venv/bin/python -m build
.venv/bin/pyinstaller atlassian.spec --clean --noconfirm
./dist/atlassian --help >/dev/null
```

Expected:

- the local command bundle matches what `ci.yml` will enforce

- [ ] **Step 4: Commit the gating workflow**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add gating workflow"
```

## Task 4: Add the Release Workflow

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Write `.github/workflows/release.yml`**

Create `.github/workflows/release.yml` with this content:

```yaml
name: Release

'on':
  push:
    tags:
      - 'v*'
  workflow_dispatch:
    inputs:
      tag:
        description: Release tag, for example v0.1.0
        required: true
        type: string

permissions:
  contents: write

concurrency:
  group: release-${{ github.workflow }}-${{ github.ref_name || inputs.tag }}
  cancel-in-progress: false

jobs:
  prepare:
    runs-on: ubuntu-latest
    outputs:
      tag: ${{ steps.meta.outputs.tag }}
      version: ${{ steps.meta.outputs.version }}
      is_prerelease: ${{ steps.meta.outputs.is_prerelease }}
      checkout_ref: ${{ steps.meta.outputs.checkout_ref }}
      commit_sha: ${{ steps.meta.outputs.commit_sha }}
    steps:
      - name: Check out repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Resolve release metadata
        id: meta
        env:
          INPUT_TAG: ${{ github.event.inputs.tag }}
        run: |
          set -euo pipefail

          if [ "${GITHUB_EVENT_NAME}" = "workflow_dispatch" ]; then
            TAG="${INPUT_TAG}"
            CHECKOUT_REF="${GITHUB_SHA}"
          else
            TAG="${GITHUB_REF_NAME}"
            CHECKOUT_REF="${GITHUB_REF}"
          fi

          echo "${TAG}" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+([-.][0-9A-Za-z.-]+)?$' || {
            echo "invalid tag: ${TAG}" >&2
            exit 1
          }

          VERSION="${TAG#v}"
          PYPROJECT_VERSION="$(
            python - <<'PY'
            import tomllib

            with open("pyproject.toml", "rb") as fh:
                print(tomllib.load(fh)["project"]["version"])
            PY
          )"
          [ "${VERSION}" = "${PYPROJECT_VERSION}" ] || {
            echo "tag version ${VERSION} does not match pyproject version ${PYPROJECT_VERSION}" >&2
            exit 1
          }

          if [ "${GITHUB_EVENT_NAME}" = "workflow_dispatch" ] && ! git rev-parse -q --verify "refs/tags/${TAG}" >/dev/null; then
            git config user.name "github-actions[bot]"
            git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
            git tag -a "${TAG}" "${GITHUB_SHA}" -m "Release ${TAG}"
            git push origin "refs/tags/${TAG}"
            CHECKOUT_REF="refs/tags/${TAG}"
          fi

          if printf '%s' "${VERSION}" | grep -Eq '[-]'; then
            IS_PRERELEASE=true
          else
            IS_PRERELEASE=false
          fi

          {
            echo "tag=${TAG}"
            echo "version=${VERSION}"
            echo "is_prerelease=${IS_PRERELEASE}"
            echo "checkout_ref=${CHECKOUT_REF}"
            echo "commit_sha=$(git rev-list -n 1 "${CHECKOUT_REF}")"
          } >> "${GITHUB_OUTPUT}"

  verify:
    runs-on: ubuntu-latest
    needs: prepare
    steps:
      - name: Check out repository
        uses: actions/checkout@v4
        with:
          ref: ${{ needs.prepare.outputs.checkout_ref }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e '.[dev]'

      - name: Lint
        run: ruff check .

      - name: Format check
        run: ruff format --check .

      - name: Run tests
        run: python -m pytest -q

      - name: Build package
        run: python -m build

  release:
    needs: [prepare, verify]
    strategy:
      fail-fast: false
      max-parallel: 1
      matrix:
        include:
          - runner: ubuntu-latest
            target_os: linux
            target_arch: amd64
            publish_checksums: false
          - runner: macos-latest
            target_os: darwin
            target_arch: arm64
            publish_checksums: true
    runs-on: ${{ matrix.runner }}
    env:
      TAG: ${{ needs.prepare.outputs.tag }}
      VERSION: ${{ needs.prepare.outputs.version }}
    steps:
      - name: Check out repository
        uses: actions/checkout@v4
        with:
          ref: ${{ needs.prepare.outputs.checkout_ref }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e '.[dev]'

      - name: Build binary
        run: |
          pyinstaller atlassian.spec --clean --noconfirm
          ./dist/atlassian --help >/dev/null

      - name: Package archive
        id: package
        run: |
          ARCHIVE_NAME="atlassian-cli_${VERSION}_${{ matrix.target_os }}_${{ matrix.target_arch }}.tar.gz"
          tar -C dist -czf "${ARCHIVE_NAME}" atlassian
          echo "archive_name=${ARCHIVE_NAME}" >> "${GITHUB_OUTPUT}"

      - name: Upload platform archive
        uses: softprops/action-gh-release@v2
        with:
          tag_name: ${{ needs.prepare.outputs.tag }}
          target_commitish: ${{ needs.prepare.outputs.commit_sha }}
          prerelease: ${{ needs.prepare.outputs.is_prerelease == 'true' }}
          overwrite_files: true
          files: ${{ steps.package.outputs.archive_name }}

      - name: Build release checksums
        if: ${{ matrix.publish_checksums }}
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          mkdir -p release-assets
          gh release download "${TAG}" --repo "${GITHUB_REPOSITORY}" --pattern 'atlassian-cli_*.tar.gz' --dir release-assets
          cd release-assets
          shasum -a 256 atlassian-cli_*.tar.gz > checksums.txt

      - name: Upload checksums
        if: ${{ matrix.publish_checksums }}
        uses: softprops/action-gh-release@v2
        with:
          tag_name: ${{ needs.prepare.outputs.tag }}
          overwrite_files: true
          files: release-assets/checksums.txt
```

- [ ] **Step 2: Validate the release workflow structure locally**

Run:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import yaml

workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text())
assert workflow["permissions"]["contents"] == "write"
assert workflow["on"]["push"]["tags"] == ["v*"]
assert workflow["on"]["workflow_dispatch"]["inputs"]["tag"]["required"] is True
assert list(workflow["jobs"]) == ["prepare", "verify", "release"]
matrix = workflow["jobs"]["release"]["strategy"]["matrix"]["include"]
assert matrix[0]["target_os"] == "linux"
assert matrix[1]["target_arch"] == "arm64"
assert workflow["jobs"]["release"]["strategy"]["max-parallel"] == 1
PY
```

Expected:

- the script exits `0`
- the workflow contains the required `prepare`, `verify`, and `release` jobs

- [ ] **Step 3: Dry-run the release asset naming logic locally**

Run:

```bash
VERSION="$(.venv/bin/python - <<'PY'
import tomllib
with open("pyproject.toml", "rb") as fh:
    print(tomllib.load(fh)["project"]["version"])
PY
)"
printf 'atlassian-cli_%s_linux_amd64.tar.gz\n' "${VERSION}"
printf 'atlassian-cli_%s_darwin_arm64.tar.gz\n' "${VERSION}"
```

Expected:

- the command prints the exact two archive names the workflow will publish
- the names match the installer expectations

- [ ] **Step 4: Commit the release workflow**

```bash
git add .github/workflows/release.yml
git commit -m "ci: add release workflow"
```

## Task 5: Document Binary Releases and Run Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add CI, release, and install documentation to `README.md`**

Insert the following sections after `## Install` and before `## Examples`:

```md
## GitHub Actions

The repository ships two GitHub Actions workflows:

- `CI`: runs on every pull request and on pushes to `main` and `release/*`
- `Release`: runs on tags matching `v*` and can also be started manually with `workflow_dispatch`

`CI` is intended to back branch protection for `main` and `release/*`.

## Release Binaries

Tagged releases publish standalone CLI binaries for:

- `linux/amd64`
- `darwin/arm64`

Each release uploads:

- `atlassian-cli_<version>_linux_amd64.tar.gz`
- `atlassian-cli_<version>_darwin_arm64.tar.gz`
- `checksums.txt`

## Install From GitHub Release

Install the latest binary release:

```bash
curl -fsSL https://raw.githubusercontent.com/example-org/example-repo/main/install.sh | sh
```

Install a specific release:

```bash
curl -fsSL https://raw.githubusercontent.com/example-org/example-repo/main/install.sh | env INSTALL_VERSION=v0.1.0 sh
```

By default the installer writes `atlassian` to `~/.local/bin`.

You can also download a tarball from the GitHub Release page and extract `atlassian` manually.

`darwin/arm64` binaries are unsigned in the first release version, so macOS may require a manual Gatekeeper allow step on first run.
```

- [ ] **Step 2: Run README spot checks**

Run:

```bash
rg -n "GitHub Actions|Release Binaries|Install From GitHub Release" README.md
```

Expected:

- the three new section headers appear exactly once

- [ ] **Step 3: Run the full local verification bundle**

Run:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m pytest -q
.venv/bin/python -m build
.venv/bin/pyinstaller atlassian.spec --clean --noconfirm
./dist/atlassian --help >/dev/null
```

Expected:

- lint, formatting, tests, package build, and binary smoke build all pass together from a clean checkout

- [ ] **Step 4: Commit the documentation and any verification-driven fixes**

```bash
git add README.md
git commit -m "docs: add binary release guidance"
```

## Manual Follow-Up

- [ ] Mark the `CI / verify` status check as required in GitHub branch protection for `main` and `release/*` after the workflows are merged and green once on GitHub.
