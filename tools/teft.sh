#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Teft development commands
Usage: tools/teft.sh [status|prepare|doctor|build|help]

  status   Show the local branch, HEAD, upstream URL, and submodules.
  prepare  Initialize and update all submodules.
  doctor   Check build dependencies.
  build    Build Development into build/teft.
           Save output to tmp/teft-build.log.
  help     Show this help.
USAGE
}

if [[ $# -gt 1 ]]; then
    printf 'Error: expected at most one command.\n' >&2
    usage >&2
    exit 2
fi

command="${1:-help}"
case "$command" in
    help|--help)
        usage
        exit 0
        ;;
    status|prepare|doctor|build)
        ;;
    *)
        printf 'Error: unknown command: %s\n' "$command" >&2
        usage >&2
        exit 2
        ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
cd "$ROOT"

case "$command" in
    status)
        branch="$(git branch --show-current)"
        head="$(git rev-parse HEAD)"
        upstream="$(git remote get-url upstream)"
        printf 'Project: Teft\nBranch: %s\nHEAD: %s\nUpstream: %s\n\nSubmodules:\n' \
            "${branch:-(detached)}" "$head" "$upstream"
        git submodule status --recursive
        ;;
    prepare)
        git submodule update --init --recursive --jobs 8
        ;;
    doctor)
        make doctor BUILD_DIR="$ROOT/build/teft"
        ;;
    build)
        mkdir -p "$ROOT/tmp"
        make Development BUILD_DIR="$ROOT/build/teft" 2>&1 \
            | tee "$ROOT/tmp/teft-build.log"
        ;;
esac
