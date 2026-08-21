#!/usr/bin/env bash
# Every `uses:` in a workflow has to resolve to a real tag.
# A floating major tag is not guaranteed to exist just because a release does:
# astral-sh/setup-uv publishes v10.0.1 but no v10, which broke CI once.
set -euo pipefail

status=0
while read -r ref; do
  repo="${ref%@*}"
  tag="${ref#*@}"
  if gh api "repos/$repo/git/ref/tags/$tag" --jq .ref >/dev/null 2>&1; then
    echo "ok      $ref"
  else
    echo "MISSING $ref" >&2
    status=1
  fi
done < <(grep -rhoE 'uses: [^ ]+' .github/workflows/*.yml | sed 's/uses: //' | sort -u)
exit "$status"
