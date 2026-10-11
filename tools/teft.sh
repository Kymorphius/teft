#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Teft development commands
Usage: tools/teft.sh [status|prepare|doctor|deps|build|run|help]

  status   Show the local branch, HEAD, upstream URL, and submodules.
  prepare  Initialize and update all submodules.
  doctor   Check build dependencies.
  deps     Rebuild native dependencies for the selected Xcode.
  build    Build Development into build/teft.
           Stage a signed Teft.app in a new version directory.
           Save logs and the latest artifact path in tmp/.
  run      Start the latest staged app with this checkout’s suite.
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
    status|prepare|doctor|deps|build|run)
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

run_make() {
    # Xcode prints its environment in build logs. Pass only build inputs.
    local -a build_env=(
        "HOME=$HOME" "PATH=$PATH" "USER=${USER:-}" "LOGNAME=${LOGNAME:-}"
        "TMPDIR=${TMPDIR:-/tmp}" "LANG=${LANG:-en_US.UTF-8}"
    )
    if [[ -n "${DEVELOPER_DIR:-}" ]]; then
        build_env+=("DEVELOPER_DIR=$DEVELOPER_DIR")
    fi
    env -i "${build_env[@]}" /usr/bin/make "$@" BUILD_DIR="$ROOT/build/teft"
}

case "$command" in
    status)
        branch="$(git branch --show-current)"
        head="$(git rev-parse HEAD)"
        if ! upstream="$(git remote get-url upstream 2>/dev/null)"; then
            upstream="(not configured)"
        fi
        printf 'Project: Teft\nBranch: %s\nHEAD: %s\nUpstream: %s\n\nSubmodules:\n' \
            "${branch:-(detached)}" "$head" "$upstream"
        git submodule status --recursive
        ;;
    prepare)
        git submodule update --init --recursive --jobs 8
        ;;
    doctor)
        run_make doctor
        ;;
    deps)
        mkdir -p "$ROOT/tmp"
        printf 'Rebuilding dependencies. Log: %s\n' "$ROOT/tmp/teft-deps.log"
        run_make -j2 paranoid-deps > "$ROOT/tmp/teft-deps.log" 2>&1
        ;;
    build)
        mkdir -p "$ROOT/tmp"
        printf 'Building Teft. Log: %s\n' "$ROOT/tmp/teft-build.log"
        run_make Development > "$ROOT/tmp/teft-build.log" 2>&1
        stage_record="$(mktemp "$ROOT/tmp/teft-stage.XXXXXX")"
        if python3 "$ROOT/tools/stage_teft.py" \
            --source-app "$ROOT/build/teft/Development/iTerm2.app" \
            --output-dir "$ROOT/build/teft/staged" \
            --suite "$(basename "$ROOT")" > "$stage_record"; then
            mv -f "$stage_record" "$ROOT/tmp/teft-stage.json"
            cat "$ROOT/tmp/teft-stage.json"
        else
            rm -f "$stage_record"
            exit 1
        fi
        ;;
    run)
        app="$(python3 - "$ROOT" <<'PY'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
sys.path.insert(0, str(root / "tools"))
from stage_teft import BUNDLE_IDENTIFIER, EXECUTABLE_NAME, read_plist

record = json.loads((root / "tmp/teft-stage.json").read_text())
if record.get("bundle_identifier") != BUNDLE_IDENTIFIER:
    raise SystemExit("Build the current Teft identity first: tools/teft.sh build")
executable = Path(record["executable_path"]).resolve(strict=True)
executable.relative_to((root / "build/teft/staged").resolve())
info = read_plist(executable.parent.parent / "Info.plist")
if info.get("CFBundleIdentifier") != BUNDLE_IDENTIFIER:
    raise SystemExit("The staged app does not have the expected Teft identity")
if info.get("CFBundleExecutable") != EXECUTABLE_NAME or executable.name != EXECUTABLE_NAME:
    raise SystemExit("Build the current Teft executable first: tools/teft.sh build")
print(executable.parent.parent.parent)
PY
        )"
        # A new terminal must not inherit this agent's session identity or tokens.
        # Launch the app bundle through Launch Services, as Finder does.
        exec env -i \
            "HOME=$HOME" "PATH=$PATH" "USER=${USER:-}" "LOGNAME=${LOGNAME:-}" \
            "TMPDIR=${TMPDIR:-/tmp}" "LANG=${LANG:-en_US.UTF-8}" \
            "SHELL=${SHELL:-/bin/zsh}" \
            /usr/bin/open -a "$app" --args -suite "$(basename "$ROOT")"
        ;;
esac
