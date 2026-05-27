#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:?usage: build-linux-compatible.sh <version>}"
DEFAULT_IMAGE="quay.io/pypa/manylinux_2_28_x86_64@sha256:441c35fdc6ee809ff9260894f8468ab4fea8c15dc880f8700a3f81b7922c1cda"
IMAGE="${LINUX_BUILD_IMAGE:-${DEFAULT_IMAGE}}"
WORKSPACE="${GITHUB_WORKSPACE:-$(pwd)}"
PYOXIDIZER_CACHE_DIR="${PYOXIDIZER_CACHE_DIR:-${HOME}/.cache/pyoxidizer}"

cd "${WORKSPACE}"
mkdir -p "${PYOXIDIZER_CACHE_DIR}"

docker run --rm \
  --platform linux/amd64 \
  -v "${WORKSPACE}:/workspace" \
  -v "${PYOXIDIZER_CACHE_DIR}:/root/.cache/pyoxidizer" \
  -w /workspace \
  -e CARGO_REGISTRIES_CRATES_IO_PROTOCOL=sparse \
  "${IMAGE}" \
  bash -lc "
    set -euo pipefail
    for tool in gcc g++ make curl git xz uv strings; do
      command -v \"\$tool\" >/dev/null
    done
    PYTHON_BIN=\"\${PYTHON_BIN:-/opt/python/cp312-cp312/bin/python}\"
    \"\${PYTHON_BIN}\" -m pip install --upgrade pip
    curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain 1.84.1-x86_64-unknown-linux-gnu
    export PATH=\"\$HOME/.cargo/bin:\$PATH\"
    \"\${PYTHON_BIN}\" .github/scripts/build-pyoxidizer-artifact.py \
      --target-os linux \
      --target-arch amd64 \
      --version \"${VERSION}\" \
      --archive-format tar.gz
    chmod -R a+rX dist/atlassian
  "
