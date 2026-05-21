#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:?usage: build-linux-compatible.sh <version>}"
IMAGE="${LINUX_BUILD_IMAGE:-python:3.12-bullseye}"
WORKSPACE="${GITHUB_WORKSPACE:-$(pwd)}"

cd "${WORKSPACE}"

docker run --rm \
  --platform linux/amd64 \
  -v "${WORKSPACE}:/workspace" \
  -w /workspace \
  -e CARGO_REGISTRIES_CRATES_IO_PROTOCOL=sparse \
  "${IMAGE}" \
  bash -lc "
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y --no-install-recommends \
      binutils \
      build-essential \
      ca-certificates \
      curl \
      git \
      libssl-dev \
      pkg-config \
      xz-utils
    python -m pip install --upgrade pip
    python -m pip install uv
    curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain 1.84.1-x86_64-unknown-linux-gnu
    export PATH=\"\$HOME/.cargo/bin:\$PATH\"
    python .github/scripts/build-pyoxidizer-artifact.py \
      --target-os linux \
      --target-arch amd64 \
      --version \"${VERSION}\" \
      --archive-format tar.gz
  "
