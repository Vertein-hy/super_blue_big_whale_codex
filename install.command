#!/bin/bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
status=0
bash "$ROOT/install.sh" "$@" || status=$?
printf '\n%s\n' 'Press Enter to close.'
read -r _ || true
exit "$status"
