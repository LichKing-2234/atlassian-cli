# Repository Instructions

- Use Conventional Commits for commit messages, for example `fix: speed up help startup`.
- Write PR titles in the same format because squash merge uses the PR title as the final commit message.

## Public Sample Data

- This repository is public. Do not commit or publish real internal or production-like sample data in code, tests, docs, specs, plans, examples, or PR metadata.
- Do not expose real company names, domains, personal names, usernames, emails, project keys, repo names, branch names, issue keys, page titles, business requirement text, reviewer lists, or other identifiers that look like real working data.
- Use the approved neutral placeholder set consistently: `DEMO`, `DEMO-1`, `DEMO-1234`, `example-repo`, `feature/DEMO-1234/example-change`, `Example Author`, `Example Collaborator`, `reviewer-one`, `reviewer-two`, `reviewer-three`, `reviewer-four`, `Example issue summary`, `Example pull request`, `Example Page`, `example comment`, `example response`, `~example-user`, and `example-user-id`.
- The same rule applies to PR titles and PR descriptions because they are public-facing project artifacts.
- Keep real values only when they are required to remain functional for public use, for example the repository's actual GitHub install URL in `README.md`.
- Before finishing changes that touch README, docs, tests, examples, or sample payloads, scan for real-looking identifiers and normalize them to the approved placeholder set.

## Quality Gates

- If you change CLI behavior, command output, command wiring, or examples, update the matching tests and user-facing documentation in the same change.
- If you add, remove, or rename CLI subcommands, update `tests/e2e/coverage_manifest.py` and the relevant live e2e coverage.
- Before claiming completion, run repository verification with the project virtualenv: `ruff format --check .`, `python -m pytest -q`, and `ruff check README.md pyproject.toml src tests docs`.
- If you are working from a git worktree, use the shared repository virtualenv when the worktree does not have its own `.venv`.
