#!/usr/bin/env bash
#
# Install the Dracula themes for Claude Code.
#
#   ./install.sh                     install Dracula and Alucard
#   ./install.sh -t dracula          install one theme
#   ./install.sh -t dracula -a       install it and make it active
#   ./install.sh -a dracula          install both, activate Dracula
#
# Also works without a clone:
#   curl -fsSL https://raw.githubusercontent.com/vishwajitsarnobat/dracula-claude-code/main/install.sh | bash -s -- -a dracula

set -euo pipefail

RAW_BASE="https://raw.githubusercontent.com/vishwajitsarnobat/dracula-claude-code/main"
ALL_THEMES=(dracula alucard)
CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
THEMES_DIR="$CONFIG_DIR/themes"
SETTINGS="$CONFIG_DIR/settings.json"
# Empty when piped into bash, so a stray themes/ in the current directory is
# never mistaken for a clone.
SOURCE_DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

selected=()
activate=""
activate_requested=0

die() { printf 'error: %s\n' "$*" >&2; exit 1; }
info() { printf '%s\n' "$*"; }

usage() {
  cat <<'USAGE'
Install the Dracula themes for Claude Code.

Usage: install.sh [options]

Options:
  -t, --theme NAME      install only this theme (repeatable)
                        one of: dracula, alucard
  -a, --activate[=NAME] set the installed theme as active in settings.json;
                        NAME is optional when exactly one theme is installed
  -d, --dir PATH        install into PATH instead of ~/.claude/themes
  -l, --list            list available themes and exit
  -h, --help            show this help

Environment:
  CLAUDE_CONFIG_DIR     Claude Code config directory (default: ~/.claude)
USAGE
}

is_theme() {
  local candidate=$1 name
  for name in "${ALL_THEMES[@]}"; do
    [ "$name" = "$candidate" ] && return 0
  done
  return 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    -t|--theme)
      [ $# -ge 2 ] || die "$1 needs a theme name"
      is_theme "$2" || die "unknown theme '$2' (want: ${ALL_THEMES[*]})"
      selected+=("$2"); shift 2 ;;
    --theme=*)
      value=${1#*=}
      is_theme "$value" || die "unknown theme '$value' (want: ${ALL_THEMES[*]})"
      selected+=("$value"); shift ;;
    -a|--activate)
      activate_requested=1
      if [ $# -ge 2 ] && is_theme "${2:-}"; then activate=$2; shift 2; else shift; fi ;;
    --activate=*)
      value=${1#*=}
      is_theme "$value" || die "unknown theme '$value' (want: ${ALL_THEMES[*]})"
      activate_requested=1; activate=$value; shift ;;
    -d|--dir)
      [ $# -ge 2 ] || die "$1 needs a path"
      THEMES_DIR=$2; shift 2 ;;
    --dir=*) THEMES_DIR=${1#*=}; shift ;;
    -l|--list)
      printf '%s\n' "${ALL_THEMES[@]}"; exit 0 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option '$1' (try --help)" ;;
  esac
done

[ ${#selected[@]} -gt 0 ] || selected=("${ALL_THEMES[@]}")

if [ "$activate_requested" = 1 ] && [ -z "$activate" ]; then
  if [ ${#selected[@]} -eq 1 ]; then
    activate=${selected[0]}
  else
    die "--activate needs a theme name when installing more than one"
  fi
fi

if [ -n "$activate" ]; then
  found=0
  for name in "${selected[@]}"; do
    [ "$name" = "$activate" ] && found=1
  done
  [ "$found" = 1 ] || die "cannot activate '$activate': it is not being installed"
fi

fetch() {
  # fetch <url> <destination>
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$1" -o "$2"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$2" "$1"
  else
    die "need curl or wget to download themes"
  fi
}

valid_json() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$1" 2>/dev/null
  elif command -v jq >/dev/null 2>&1; then
    jq -e . "$1" >/dev/null 2>&1
  else
    return 0
  fi
}

mkdir -p "$THEMES_DIR"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

installed=()
for name in "${selected[@]}"; do
  file="$name.json"
  staged="$tmp/$file"
  if [ -n "$SOURCE_DIR" ] && [ -f "$SOURCE_DIR/themes/$file" ]; then
    cp "$SOURCE_DIR/themes/$file" "$staged"
  else
    fetch "$RAW_BASE/themes/$file" "$staged" \
      || die "could not download $file"
  fi
  valid_json "$staged" || die "$file is not valid JSON -- refusing to install"
  install -m 0644 "$staged" "$THEMES_DIR/$file"
  installed+=("$name")
  info "installed  $THEMES_DIR/$file"
done

if [ -n "$activate" ]; then
  ref="custom:$activate"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$SETTINGS" "$ref" <<'PY'
import json, os, shutil, sys
# Resolve symlinks so a dotfiles-managed settings.json is written through, not
# replaced by a regular file.
path, ref = os.path.realpath(sys.argv[1]), sys.argv[2]
try:
    with open(path) as fh:
        settings = json.load(fh)
except FileNotFoundError:
    settings = {}
except ValueError as exc:
    sys.exit(f"error: {path} is not valid JSON ({exc}) -- not touching it")
if not isinstance(settings, dict):
    sys.exit(f"error: {path} is not a JSON object -- not touching it")
settings["theme"] = ref
os.makedirs(os.path.dirname(path), exist_ok=True)
tmp = path + ".tmp"
with open(tmp, "w") as fh:
    json.dump(settings, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
if os.path.exists(path):
    shutil.copymode(path, tmp)
os.replace(tmp, path)
PY
  elif command -v jq >/dev/null 2>&1; then
    mkdir -p "$(dirname "$SETTINGS")"
    [ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
    # Write back with cat rather than mv to keep symlinks and permissions intact.
    jq --arg t "$ref" '.theme = $t' "$SETTINGS" > "$tmp/settings.json" \
      || die "$SETTINGS is not valid JSON -- not touching it"
    cat "$tmp/settings.json" > "$SETTINGS"
  else
    info ""
    info "could not edit $SETTINGS (need python3 or jq)."
    info "set it by hand:  \"theme\": \"$ref\""
    activate=""
  fi
  [ -n "$activate" ] && info "activated  $ref"
fi

info ""
info "Done. ${#installed[@]} theme(s) in $THEMES_DIR"
if [ -z "$activate" ]; then
  info "Pick one with /theme inside Claude Code."
fi
info "Claude Code watches the themes directory, so a running session picks this up"
info "without a restart. Set your terminal background to match the theme"
info "(Dracula #282a36, Alucard #fffbeb)."
