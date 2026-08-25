#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_root"
exec uv run --project "$project_root" --locked \
  python "$project_root/scripts/check_action_refs.py"
