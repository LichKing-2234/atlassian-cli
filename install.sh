#!/bin/sh
set -eu

REPO_OWNER="LichKing-2234"
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
    x86_64 | amd64)
      printf 'amd64'
      ;;
    aarch64 | arm64)
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
    linux/amd64 | darwin/arm64)
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
  awk -v target="${archive_name}" '$2 == target { print $1 }' "${checksums_file}"
}

sha256_file() {
  target_file="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${target_file}" | awk '{ print $1 }'
    return
  fi
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${target_file}" | awk '{ print $1 }'
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
  [ ! -L "${extract_dir}/atlassian" ] || die "archive extracted a symbolic link for atlassian"
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

  TMP_ROOT="$(mktemp -d 2>/dev/null || mktemp -d -t atlassian-cli)" ||
    die "failed to create temporary directory"
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
