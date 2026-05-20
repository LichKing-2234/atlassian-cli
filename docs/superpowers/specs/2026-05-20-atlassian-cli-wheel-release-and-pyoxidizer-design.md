# Atlassian CLI Wheel Release Assets and PyOxidizer Migration Design

## Summary

Extend `atlassian-cli` so `main` supports two long-term distribution paths at the same time:

- Python package distribution through GitHub Release wheel and sdist assets for `uv tool install` workflows
- standalone binary distribution through PyOxidizer, replacing the current PyInstaller-based release pipeline

The repository should continue to publish GitHub Releases on version tags, but the release contents and validation model change:

- GitHub Releases keep the existing platform-specific standalone archives
- those standalone archives are produced by PyOxidizer instead of PyInstaller
- GitHub Releases also upload a universal wheel and sdist
- README, tests, CI, and release automation are updated so both distribution paths are first-class and internally consistent

Implementation will be split across two isolated worktrees and merged back to `main` in sequence:

1. `feat/wheel-release-assets`
2. `feat/pyoxidizer-release`

## Goals

- Add GitHub Release wheel and sdist assets for every tagged release.
- Document and support `uv tool install` based installation from GitHub Release package artifacts.
- Keep binary install scripts as the supported path for standalone runtime installation.
- Replace PyInstaller with PyOxidizer for standalone binary release artifacts on:
  - `linux/amd64`
  - `darwin/arm64`
  - `darwin/amd64`
  - `windows/amd64`
- Update CI so package builds and PyOxidizer binary builds are verified in automation.
- Update release tests so the release contract is locked in by assertions instead of only by docs.
- Keep `atlassian update check` available.
- Keep `atlassian update install` supported only for binary installations and make package-installed environments fail explicitly with the correct remediation.
- Merge both workstreams back to `main` without dragging the current dirty working tree into feature branches.

## Non-Goals

- Publishing to PyPI.
- Supporting `uv tool install atlassian-cli` from a package index.
- Preserving PyInstaller as a parallel release path after PyOxidizer lands.
- Replacing shell and PowerShell install scripts with a package installer.
- Redesigning the CLI command surface unrelated to distribution and update behavior.
- Refactoring unrelated in-flight user changes currently present in the main checkout.

## Current State

The repository currently has:

- `CI` building packages with `python -m build`
- `Release` publishing standalone platform archives produced by PyInstaller
- install scripts that assume GitHub Release binary archives
- `atlassian update install` that reuses the binary installer flow
- README content centered on GitHub Release binary installation

The repository does not currently have:

- wheel/sdist assets attached to GitHub Releases
- package-install documentation for `uv tool install`
- a release path based on PyOxidizer
- automated distinction between binary-installed and package-installed self-update behavior

## Supported Distribution Paths

### Path 1: Python Package Assets

Each tagged release should upload:

- `atlassian_cli-<version>.tar.gz`
- `atlassian_cli-<version>-py3-none-any.whl`

These assets are intended for:

- `uv tool install <wheel-file>`
- `uv tool install <release-wheel-url>`
- manual `pip` or `uv pip` based installation from downloaded assets

These assets are not used by:

- `install.sh`
- `install.ps1`
- `atlassian update install`

### Path 2: Standalone Binary Assets

Each tagged release should continue to upload:

- `atlassian-cli_<version>_linux_amd64.tar.gz`
- `atlassian-cli_<version>_darwin_arm64.tar.gz`
- `atlassian-cli_<version>_darwin_amd64.tar.gz`
- `atlassian-cli_<version>_windows_amd64.zip`
- `checksums.txt`

These assets remain the source of truth for:

- `install.sh`
- `install.ps1`
- `atlassian update install`

The standalone assets should be built by PyOxidizer instead of PyInstaller.

## User-Facing Behavior

### README

README should separate installation into two explicit sections:

- binary installation from GitHub Release archives
- Python package installation from GitHub Release wheel assets

README should explicitly state:

- binary installation is the right path for self-updating standalone installs
- `uv tool install` is the right path for Python-managed installs
- `atlassian update install` is only for standalone binary installs

README should not claim an index-based install path such as `uv tool install atlassian-cli`, because publishing to PyPI is out of scope.

### Binary Install Scripts

`install.sh` and `install.ps1` should continue to:

- download standalone release assets
- verify checksums
- install the standalone runtime bundle and launcher

They should not gain package-install responsibilities.

### `atlassian update` Behavior

`atlassian update check` continues to inspect GitHub release metadata.

`atlassian update install` should:

- succeed for supported standalone binary installs
- refuse to run for package-managed installs such as `uv tool install`
- explain what to do instead for package-managed installs, e.g. reinstall or upgrade through the Python tool manager

This avoids ambiguous hybrid update behavior.

## Release Contract

The release contract after both branches merge is:

- every release tag produces wheel and sdist assets
- every release tag produces four standalone platform archives through PyOxidizer
- `checksums.txt` covers standalone archives
- release notes remain generated from commit history
- release notification continues to use the generated GitHub Release body

The wheel and sdist assets should not be folded into the current standalone checksum contract. They are different installation modes and should remain logically separate.

## CI and Release Workflow Design

### CI Workflow

`CI` should continue to run:

- `ruff check .`
- `ruff format --check .`
- `python -m pytest -q`
- `python -m build`

`CI` should change in these ways:

- remove the PyInstaller standalone smoke test
- add a PyOxidizer smoke path that verifies the repository can produce a runnable standalone artifact for the local CI target
- keep package-build validation as a first-class gate

The CI smoke target does not need to build every platform on every push. It needs to prove the PyOxidizer path is wired correctly and runnable in CI.

### Release Workflow

The current `Release` workflow should evolve into these logical stages:

1. `prepare`
   - validate tag/version parity
   - preserve current release metadata logic
2. `verify`
   - install dependencies
   - run lint, formatting, tests, and package build
3. `python-package`
   - build wheel and sdist
   - upload them to the GitHub Release
4. `standalone-release`
   - build standalone platform artifacts with PyOxidizer
   - upload each platform artifact to the GitHub Release
5. `checksums`
   - download standalone archives
   - generate `checksums.txt`
   - upload `checksums.txt`
6. `notify`
   - keep current release-note backed WeCom notification behavior

The workflow should preserve the existing tagged-release entrypoint and should not introduce a second release process outside GitHub Actions.

## PyOxidizer Migration Design

PyOxidizer becomes the only standalone release builder after the migration branch lands.

The migration needs explicit repository-owned build configuration, not a temporary benchmark-only path.

Repository-owned PyOxidizer support should include:

- checked-in PyOxidizer configuration
- per-platform build scripts or workflow steps that produce the release asset layout expected by install and update code
- a stable artifact naming and packaging layer matching current release filenames
- smoke validation that the produced executable can run `--help` or `--version`

Because the benchmark showed real compatibility and tooling friction, the migration work must treat these as design constraints:

- Python runtime compatibility must be explicit and reproducible
- Rust toolchain requirements must be encoded in automation, not assumed from the developer machine
- platform packaging differences must be handled in repository scripts rather than in ad hoc shell history

Repository-owned helper scripts around PyOxidizer should be expected so the release workflow stays readable, testable, and reviewable.

## Package Asset Design

The wheel path should stay intentionally simple:

- build with `python -m build`
- upload wheel and sdist to the GitHub Release
- document `uv tool install` from a file or versioned URL

No package-index publishing behavior should leak into the release workflow or docs.

## Testing Strategy

### Repository Verification

Repository completion gates remain:

- `ruff format --check .`
- `python -m pytest -q`
- `ruff check README.md pyproject.toml src tests docs`

### Package Asset Tests

Add or extend tests to cover:

- release workflow uploads wheel and sdist assets
- release asset naming remains stable
- README examples for package installation stay aligned with actual artifact names

### Standalone Release Tests

Add or extend tests to cover:

- release workflow uses PyOxidizer instead of PyInstaller
- each targeted platform remains represented in the release matrix
- standalone artifact packaging names stay aligned with install script expectations
- checksum generation continues to cover standalone archives

### Update Path Tests

Add or extend tests to cover:

- binary install environments still support `atlassian update install`
- package-managed installs fail with an explicit and actionable message

### Documentation Tests

Update README tests so both installation paths are validated:

- binary install examples
- wheel/sdist install examples
- update-command guidance

## Worktree Execution Plan

Implementation should happen in two linked worktrees rooted from the clean tracked history, not from the current dirty working tree state.

### Worktree A

- branch: `feat/wheel-release-assets`
- ownership:
  - package asset release flow
  - README package-install documentation
  - package-related tests
  - CI/release changes related only to wheel and sdist

Primary files likely touched:

- `README.md`
- `pyproject.toml`
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `tests/test_readme.py`
- `tests/release/*`

### Worktree B

- branch: `feat/pyoxidizer-release`
- ownership:
  - PyOxidizer build system
  - binary install/update integration changes
  - PyOxidizer CI/release changes
  - standalone release tests

Primary files likely touched:

- `README.md`
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `install.sh`
- `install.ps1`
- `src/atlassian_cli/update.py`
- PyOxidizer config and helper scripts
- `tests/test_update.py`
- `tests/release/*`

### Merge Order

The branches should merge in this order:

1. `feat/wheel-release-assets`
2. rebase `feat/pyoxidizer-release` on updated `main`
3. merge `feat/pyoxidizer-release`

This order is required because both branches intentionally modify:

- `README.md`
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- release-contract tests

The PyOxidizer branch should resolve conflicts against the already-landed wheel asset workflow rather than expecting both branches to land independently without rebase.

## Risks

- PyOxidizer cross-platform reproducibility may be materially more complex than PyInstaller, especially across Linux and Windows.
- Package-installed update detection can become unreliable if install-origin detection is under-specified.
- README drift is likely because both branches touch installation documentation.
- Release workflow complexity will grow; helper scripts and release tests must absorb that complexity instead of embedding everything inline in YAML.
- The current checkout is dirty, so branch creation must avoid accidentally capturing unrelated changes.

## Recommended Implementation Order

1. Land wheel/sdist release assets and docs first.
2. Land package-install tests and CI assertions.
3. Build repository-owned PyOxidizer packaging scripts and per-platform smoke tests.
4. Switch release workflow binary assets from PyInstaller to PyOxidizer.
5. Update binary installers and self-update logic to the new asset source.
6. Remove PyInstaller-specific CI and release logic after PyOxidizer parity is proven.

## Success Criteria

- GitHub Releases attach wheel and sdist assets alongside standalone archives.
- README documents `uv tool install` from GitHub Release artifacts and keeps binary install guidance intact.
- Standalone release assets are produced by PyOxidizer, not PyInstaller.
- `install.sh`, `install.ps1`, and `atlassian update install` still work against the standalone assets.
- Package-installed environments fail cleanly and explicitly when `atlassian update install` is invoked.
- CI and release workflow tests cover both distribution paths.
- Both feature branches merge back to `main` without relying on manual, undocumented local packaging steps.
