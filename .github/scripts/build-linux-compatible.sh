#!/usr/bin/env bash
set -euo pipefail

cd "${GITHUB_WORKSPACE:-/github/workspace}"

PYTHON="${LINUX_BUILD_PYTHON:-/usr/local/bin/python}"
PYTHON_BIN_DIR="$(dirname "${PYTHON}")"
LIBPYTHON="dist/atlassian/_internal/libpython3.12.so.1.0"

"${PYTHON}" -m pip install --upgrade pip
"${PYTHON}" -m pip install -e '.[dev]'
PATH="${PYTHON_BIN_DIR}:${PATH}" pyinstaller atlassian.spec --clean --noconfirm
./dist/atlassian/atlassian --help >/dev/null

if command -v strings >/dev/null 2>&1 && [ -f "${LIBPYTHON}" ]; then
  if strings "${LIBPYTHON}" | grep -Eq 'GLIBC_2\.(3[8-9]|[4-9][0-9])'; then
    echo "bundled Python requires glibc newer than the supported release baseline" >&2
    exit 1
  fi
fi
