#!/bin/bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 "$ROOT/tools/publish.py" --dry-run "$@"
printf '%s\n' 'Review the repository name and visibility above. This uploads the project to a NEW repository only.'
printf '%s' 'Continue? [y/N] '
read -r answer
if [[ "$answer" != y && "$answer" != Y ]]; then exit 0; fi
status=0
python3 "$ROOT/tools/publish.py" "$@" || status=$?
printf '\n%s\n' 'Press Enter to close.'
read -r _ || true
exit "$status"
