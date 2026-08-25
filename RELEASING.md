# Releasing

The release workflow refuses to publish if the documentation does not match the
tag, so the order below matters: everything is edited and committed first, and
the tag goes on that commit.

## Once, before the first release

1. **Set up Trusted Publishing.** On PyPI, add a pending publisher for
   `spokenid` pointing at `kuangc/spokenid`, workflow `release.yml`,
   environment `pypi`. Nothing can be published until this exists, and this way
   there is no API token to store or leak.
2. **Create the `pypi` environment** in the repository settings, so the publish
   job has somewhere to run.
3. **Require full-length commit SHAs for Actions after these pinned workflows
   are on `main`.** In Settings > Actions > General, enable the SHA-pinning
   policy. Enabling it before the pinned workflow commit reaches `main` would
   block the workflows that are still there.

## Every release

Do all the edits, then commit, then tag. The tag has to point at the commit
that contains the edits, or the workflow will check the wrong tree.

1. **Set the version** in `src/spokenid/__init__.py`. It is the only place it
   lives; `pyproject.toml` reads it from there.

2. **Date the changelog.** For `v0.1.0`, add the release date to the existing
   `## [0.1.0]` section; do not create a second section. For later releases, move
   everything under `## [Unreleased]` into a new
   `## [x.y.z] - YYYY-MM-DD` section. Leave `## [Unreleased]` in place, empty,
   and add the comparison link at the bottom of the file.

3. **First release only: fix the install section** of `README.md`. Replace

   ```text
   Not on PyPI yet. Install the current repository with:
   ```

   ```bash
   pip install git+https://github.com/kuangc/spokenid
   ```

   with:

   ```bash
   pip install spokenid
   ```

   The README is what renders on the PyPI page, so it cannot say the package is
   not on PyPI.

4. **Check it all passes.**

   ```bash
   bash scripts/check_action_refs.sh
   uv sync --locked
   uv run --locked pytest -q
   uv run --locked mypy
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   uv run --locked python benchmarks/evaluate.py --profile full --check benchmarks/results/v0.1.json
   uv build --no-build-isolation
   uv run --locked twine check --strict dist/*
   sdist_root=$(mktemp -d)
   tar -xzf dist/spokenid-*.tar.gz -C "$sdist_root"
   (cd "$sdist_root"/spokenid-* && uv run --locked pytest -q)
   ```

5. **Commit the edits and push.**

   ```bash
   git add -A && git commit -m "chore: release v0.1.0" && git push
   ```

6. **Wait for CI to pass on that commit**, then tag it and push the tag.

   ```bash
   git tag -a v0.1.0 -m "v0.1.0"
   git push origin v0.1.0
   ```

`release.yml` then runs the whole suite on every supported Python, checks the
tagged commit is on `main`, checks the changelog and README against the tag,
builds, installs the wheel into a clean environment and uses it, checks the tag
matches the package version, and publishes through PyPI Trusted Publishing.

## If the publish fails

The build artifacts are attached to the workflow run, so nothing needs
rebuilding. Fix the cause, delete the tag locally and on the remote, and tag
again:

```bash
git tag -d v0.1.0 && git push origin :refs/tags/v0.1.0
```

A version that reached PyPI cannot be reused. If the upload itself succeeded
and something else was wrong, bump the patch number instead of retrying.
