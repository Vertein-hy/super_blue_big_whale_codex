#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' 'Python 3.10+ is required for the installer. Alternatively copy the three folders under pets/ into ~/.codex/pets/.' >&2
  exit 1
fi
exec python3 "$ROOT/tools/petctl.py" install "$@"
