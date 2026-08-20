#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  run_headless_check.sh [options]

Options:
  --project <path>          Godot project root (default: current directory)
  --godot-bin <path>        Godot binary path (default: $GODOT_BIN, then godot on PATH, then ~/Documents/Godot.app/...)
  --scene <res://...>       Scene path to run in headless mode
  --quit-after <frames>     Frame limit when --scene is set (default: 180)
  --allow-error <pattern>   Ignore log lines containing this text (repeatable)
  --no-strict-errors        Do not fail on ERROR/SCRIPT ERROR log lines if process exits 0
  --no-isolate-home         Do not isolate HOME during run
  --extra-arg <arg>         Pass one extra argument to Godot (repeatable)
  --help                    Show this help text

Examples:
  run_headless_check.sh --project /path/to/project
  run_headless_check.sh --project /path/to/project --scene res://main.tscn --quit-after 240
  run_headless_check.sh --scene res://tscn/tween_preview.tscn \
    --allow-error "Cannot open file 'res://poem/assets/poem.en.translation'."
USAGE
}

if command -v godot >/dev/null 2>&1; then
  GODOT_BIN_DEFAULT="$(command -v godot)"
else
  GODOT_BIN_DEFAULT="$HOME/Documents/Godot.app/Contents/MacOS/Godot"
fi

GODOT_BIN="${GODOT_BIN:-$GODOT_BIN_DEFAULT}"
PROJECT_PATH="${PROJECT_PATH:-$PWD}"
SCENE_PATH="${SCENE_PATH:-}"
QUIT_AFTER_FRAMES="${QUIT_AFTER_FRAMES:-180}"
STRICT_ERRORS="${STRICT_ERRORS:-1}"
ISOLATE_HOME="${ISOLATE_HOME:-1}"

# macOS headless runs with isolated HOME can emit this harmless CA lookup error.
declare -a DEFAULT_ALLOW_PATTERNS=(
  "ERROR: Condition \"ret != noErr\" is true. Returning: \"\""
)

declare -a ALLOW_PATTERNS=()
declare -a EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)
      PROJECT_PATH="$2"
      shift 2
      ;;
    --godot-bin)
      GODOT_BIN="$2"
      shift 2
      ;;
    --scene)
      SCENE_PATH="$2"
      shift 2
      ;;
    --quit-after)
      QUIT_AFTER_FRAMES="$2"
      shift 2
      ;;
    --allow-error)
      ALLOW_PATTERNS+=("$2")
      shift 2
      ;;
    --no-strict-errors)
      STRICT_ERRORS=0
      shift
      ;;
    --no-isolate-home)
      ISOLATE_HOME=0
      shift
      ;;
    --extra-arg)
      EXTRA_ARGS+=("$2")
      shift 2
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -x "$GODOT_BIN" ]]; then
  echo "Godot binary not found or not executable: $GODOT_BIN" >&2
  exit 2
fi

if [[ ! -f "$PROJECT_PATH/project.godot" ]]; then
  echo "No project.godot found under: $PROJECT_PATH" >&2
  exit 2
fi

if ! [[ "$QUIT_AFTER_FRAMES" =~ ^[0-9]+$ ]]; then
  echo "--quit-after must be a non-negative integer, got: $QUIT_AFTER_FRAMES" >&2
  exit 2
fi

echo "[godot-headless] bin: $GODOT_BIN"
echo "[godot-headless] project: $PROJECT_PATH"
if [[ -n "$SCENE_PATH" ]]; then
  echo "[godot-headless] scene: $SCENE_PATH"
  echo "[godot-headless] quit-after: $QUIT_AFTER_FRAMES"
else
  echo "[godot-headless] mode: startup-check (--quit)"
fi

tmp_log="$(mktemp -t godot-headless.XXXXXX.log)"
tmp_home=""
cleanup() {
  rm -f "$tmp_log"
  if [[ -n "$tmp_home" ]]; then
    rm -rf "$tmp_home"
  fi
}
trap cleanup EXIT

if [[ "$ISOLATE_HOME" == "1" ]]; then
  tmp_home="$(mktemp -d /tmp/godot-headless-home.XXXXXX)"
  mkdir -p "$tmp_home/Library/Application Support/Godot"
  echo "[godot-headless] isolated HOME: $tmp_home"
fi

cmd=("$GODOT_BIN" --path "$PROJECT_PATH" --headless)
if [[ -n "$SCENE_PATH" ]]; then
  cmd+=(--quit-after "$QUIT_AFTER_FRAMES" "$SCENE_PATH")
else
  cmd+=(--quit)
fi
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  cmd+=("${EXTRA_ARGS[@]}")
fi

set +e
if [[ -n "$tmp_home" ]]; then
  HOME="$tmp_home" "${cmd[@]}" >"$tmp_log" 2>&1
else
  "${cmd[@]}" >"$tmp_log" 2>&1
fi
godot_exit=$?
set -e

cat "$tmp_log"

if [[ $godot_exit -ne 0 ]]; then
  echo "[godot-headless] Godot process exited with code $godot_exit" >&2
  exit "$godot_exit"
fi

if [[ "$STRICT_ERRORS" != "1" ]]; then
  echo "[godot-headless] OK (non-strict error scanning disabled)"
  exit 0
fi

unexpected_errors=0
while IFS= read -r line; do
  if [[ "$line" != *"ERROR:"* && "$line" != *"SCRIPT ERROR:"* ]]; then
    continue
  fi

  ignored=0

  for pattern in "${DEFAULT_ALLOW_PATTERNS[@]}"; do
    if [[ "$line" == *"$pattern"* ]]; then
      ignored=1
      break
    fi
  done

  if [[ $ignored -eq 0 ]]; then
    for pattern in "${ALLOW_PATTERNS[@]}"; do
      if [[ "$line" == *"$pattern"* ]]; then
        ignored=1
        break
      fi
    done
  fi

  if [[ $ignored -eq 0 ]]; then
    echo "[godot-headless] Unexpected error: $line" >&2
    unexpected_errors=1
  fi
done < "$tmp_log"

if [[ $unexpected_errors -ne 0 ]]; then
  echo "[godot-headless] Validation failed: unexpected errors found." >&2
  exit 1
fi

echo "[godot-headless] OK"
