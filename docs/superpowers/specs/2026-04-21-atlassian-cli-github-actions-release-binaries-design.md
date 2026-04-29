# Atlassian CLI GitHub Actions Release Binaries Design

## Summary

Add GitHub Actions support for two distinct flows:

- a gating workflow that runs on pull requests and on pushes to `main` and `release/*`
- a release workflow that builds and publishes installable CLI binaries to GitHub Releases

The implementation should follow the structure used in `example-org/example-repo`: separate `ci.yml` and `release.yml` workflows, stable release asset names, and a repository-owned install script that downloads the matching release binary and verifies checksums before installing it locally.

Because this repository is a Python CLI rather than a Go project, the release binaries will be produced with PyInstaller instead of GoReleaser. The first supported release targets are:

- `linux/amd64`
- `darwin/arm64`

`macOS arm64` binaries are intentionally unsigned in the first version. Documentation must state that Gatekeeper may require a manual allow step on first run.

## Goals

- Add a GitHub Actions gating workflow suitable for branch protection on `main` and `release/*`.
- Add a GitHub Actions release workflow that publishes binary release assets for `linux/amd64` and `darwin/arm64`.
- Publish a repository-owned `install.sh` script that installs the correct binary from GitHub Releases.
- Keep the release asset naming and installer behavior close to the `ai-efficiency` reference repository.
- Validate both Python package builds and release-binary builds before publishing.

## Non-Goals

- Publishing to PyPI.
- Supporting Windows binaries in this change.
- Apple code signing or notarization.
- Managing GitHub branch protection settings from code. The workflows only provide the required checks; repository settings still need to mark them as required.
- Expanding the existing smoke tests into CI-required external integration tests.

## Reference Alignment

The implementation should mirror these reference-repo behaviors:

- separate `ci.yml` and `release.yml` workflows
- `release.yml` triggered by `v*` tags and `workflow_dispatch`
- a `prepare -> verify -> release` job structure in the release workflow
- repository-owned install script that:
  - detects OS and architecture
  - resolves the release tag from GitHub Releases
  - downloads the matching archive plus `checksums.txt`
  - verifies the archive checksum before installation

The implementation should intentionally diverge from the reference in these areas:

- use `actions/setup-python` and Python build tooling instead of Go and GoReleaser
- build release binaries with PyInstaller
- publish CLI tarballs rather than container images

## Versioning and Release Semantics

### Tag format

The canonical release tag format is `vX.Y.Z`.

Examples:

- `v0.1.0`
- `v1.4.2`

Pre-release tags may use an additional suffix such as `v0.2.0-rc.1`. The release workflow should treat any suffixed version as a GitHub prerelease.

### Version source of truth

`pyproject.toml` remains the package version source of truth inside the repository.

The release workflow must fail if:

- the pushed or dispatched tag does not match `^v[0-9]+\.[0-9]+\.[0-9]+([-.][0-9A-Za-z.-]+)?$`
- the normalized tag version does not match `project.version` in `pyproject.toml`

This prevents publishing binaries that report a different version from the tagged source.

### Manual dispatch behavior

`workflow_dispatch` remains available to match the reference repository.

The dispatch form should accept a required `tag` input. If the tag already exists, the workflow releases that tagged source. If the tag does not exist yet, the workflow should create and push an annotated tag at the selected commit before continuing. This keeps manual releases aligned with the tag-based release model instead of creating detached one-off artifacts.

## Workflow Architecture

### Gating workflow

Add `.github/workflows/ci.yml`.

Triggers:

- `pull_request`
- `push` on `main`
- `push` on `release/*`

Permissions:

- `contents: read`

Concurrency:

- cancel in-progress runs for the same workflow and ref, matching the reference repository pattern

The gating workflow should expose one stable job name so branch protection can require it consistently. The simplest shape is a single `verify` job that performs all checks in order.

### Release workflow

Add `.github/workflows/release.yml`.

Triggers:

- `push` tags matching `v*`
- `workflow_dispatch` with a required `tag` input

Permissions:

- `contents: write`

The release workflow should use three jobs:

1. `prepare`
2. `verify`
3. `release`

This mirrors the reference repository and keeps release metadata validation separate from binary production.

## Gating Workflow Design

### Python setup

Use a single supported Python runtime for verification:

- Python `3.12`

The repository currently declares `requires-python = ">=3.12"`, so the workflow should verify against the minimum supported version first rather than introducing a larger matrix immediately.

### Verification steps

The `verify` job should run these steps in order:

1. check out the repository
2. set up Python `3.12`
3. install the project in editable mode with dev dependencies
4. run `ruff check .`
5. run `ruff format --check .`
6. run `pytest`
7. run `python -m build`
8. run a lightweight Linux-only PyInstaller build smoke check

The PyInstaller smoke check exists to catch binary-build breakage during normal development instead of discovering it only when a tag is pushed.

### Test scope

The existing `tests/integration/test_smoke.py` file is already guarded by `ATLASSIAN_SMOKE`. The gating workflow should not set that variable, so smoke tests stay skipped by default. The required checks remain hermetic and repository-local.

### Lint and format scope

The repository does not currently define lint tooling. This change should add a minimal `ruff` configuration that:

- enables core correctness and import-sorting checks
- keeps the initial rule set intentionally small
- uses `ruff format` as the formatter

The goal is stable gating, not a wide style-policy change.

## Release Workflow Design

### Prepare job

The `prepare` job should:

- resolve the requested tag from either `github.ref` or the dispatch input
- validate the tag format
- derive:
  - `tag`
  - normalized `version`
  - `is_prerelease`
  - `checkout_ref`
  - `commit_sha`
  - `build_time`
- expose these values as workflow outputs

If the workflow was started by `workflow_dispatch` and the tag does not exist yet, the job should prepare enough metadata for the later release job to create and push it.

### Verify job

The `verify` job should run against the exact tag or commit selected by `prepare`.

It should repeat the same validation steps as `ci.yml`:

- install dependencies
- `ruff check .`
- `ruff format --check .`
- `pytest`
- `python -m build`

The release workflow should not trust that a previous CI run exists or is still representative of the tagged source.

### Release job

The `release` job should:

- ensure the release tag exists and check out that exact ref
- build release binaries for:
  - `linux/amd64`
  - `darwin/arm64`
- verify each produced binary with `--help`
- package each binary into a tarball
- generate `checksums.txt`
- create or update the matching GitHub Release
- upload all release assets

The release job should depend on both `prepare` and `verify`.

## Binary Build Strategy

### Packaging tool

Use PyInstaller in `--onefile` mode to produce a standalone binary named `atlassian`.

The implementation should avoid relying on ad hoc module-path behavior from `src/` layout. A small checked-in PyInstaller entrypoint or spec file is acceptable if needed to make imports deterministic across both release targets.

### Expected binary behavior

Each produced binary must:

- expose the same CLI behavior as the Python package entry point
- support `atlassian --help`
- not require a preinstalled Python runtime on the target system

### Build matrix

The release workflow should build on native GitHub-hosted runners for the supported targets:

- `ubuntu-latest` for `linux/amd64`
- `macos-latest` for `darwin/arm64`

Cross-compiling PyInstaller binaries is intentionally out of scope for the first iteration. Native runners reduce packaging risk.

### Release archive layout

Each release artifact should be packaged as a tarball containing exactly one top-level executable file:

- archive name: `atlassian-cli_<version>_linux_amd64.tar.gz`
- archive name: `atlassian-cli_<version>_darwin_arm64.tar.gz`
- internal file name: `atlassian`

The workflow must reject archives that do not contain a regular top-level `atlassian` file.

### Checksums

Generate a single `checksums.txt` file containing SHA-256 checksums for all published tarballs in the release. The installer uses this file to verify downloads before replacing an installed binary.

## Installer Script Design

### File location

Add a repository-root `install.sh`.

This matches the discoverability of the reference repository and keeps the installation entry point stable for README examples.

### Supported platforms

The installer should support:

- `linux` + `amd64`
- `darwin` + `arm64`

Architecture normalization rules:

- `x86_64` -> `amd64`
- `aarch64` -> `arm64`
- `arm64` -> `arm64`

Unsupported operating systems or architectures must fail fast with a clear error.

### Installation flow

The installer should:

1. verify required tools exist:
   - `curl`
   - `tar`
   - either `sha256sum` or `shasum`
2. detect OS and architecture
3. resolve the target tag:
   - use `INSTALL_VERSION` if provided
   - otherwise query the latest GitHub Release
4. download:
   - the matching tarball
   - `checksums.txt`
5. verify the downloaded tarball checksum
6. verify the tarball contains a regular `atlassian` file
7. install the extracted binary to `~/.local/bin/atlassian`
8. print a short success message and a `PATH` hint if `~/.local/bin` is not currently on `PATH`

Installation should be atomic: copy into a temporary path in the install directory, mark executable, then move into place.

### Configurable installer inputs

The installer should support small environment-variable overrides to keep testing and future reuse practical:

- `INSTALL_VERSION` to install a specific tag
- `INSTALL_DIR` to override the target directory
- `INSTALL_RELEASE_API_URL` to override the GitHub Releases API endpoint
- `INSTALL_RELEASE_DOWNLOAD_BASE` to override the GitHub Releases download base URL
- `INSTALL_TEST_OS` and `INSTALL_TEST_ARCH` for script-level testing only

Defaults should point to this repository's GitHub Releases endpoints.

### Failure handling

The installer must exit immediately on:

- unsupported platform
- missing required commands
- failure to resolve the release tag
- missing checksum entry for the selected archive
- checksum mismatch
- missing or malformed archive contents
- failed installation move

The installer must not silently fall back to an unchecked install path.

## Repository Configuration Changes

### Python project metadata

Update `pyproject.toml` to add development dependencies required by CI and release packaging:

- `build`
- `pyinstaller`
- `ruff`

Add a minimal `ruff` configuration in `pyproject.toml` so local development and GitHub Actions use the same behavior.

### Optional PyInstaller spec support

If PyInstaller cannot reliably bundle the CLI directly from the current `src/` layout, add one minimal checked-in build helper:

- either `atlassian.spec`
- or a tiny wrapper entry script used only for PyInstaller

That helper should exist solely to make imports deterministic and should not change runtime CLI behavior.

## Documentation Changes

Update `README.md` with these sections:

- `GitHub Actions`
- `Release Binaries`
- `Install From GitHub Release`

The documentation should cover:

- that PRs and pushes to `main` and `release/*` are gated by CI
- that releases are produced from `v*` tags
- the supported binary platforms
- the release asset naming convention
- the one-line installer invocation
- manual download and extraction from GitHub Releases
- the unsigned `macOS arm64` binary caveat

## Testing

Add or update tests and checks for:

- `ruff check` and `ruff format --check` succeeding in CI
- `pytest` continuing to pass after any lint-driven edits
- `python -m build` producing valid package artifacts
- PyInstaller producing a runnable `atlassian` binary on Linux in CI
- release jobs running `./dist/atlassian --help` before packaging artifacts
- installer script behavior for:
  - platform detection
  - unsupported platform rejection
  - archive-name selection
  - checksum validation

Script tests can stay lightweight shell-level checks rather than introducing a large shell test framework.

## Operational Notes

After the workflows land, repository settings should mark the stable `ci.yml` verification job as a required status check for:

- `main`
- `release/*`

That repository-settings step is required for true merge gating, but it is intentionally not managed from this code change.
