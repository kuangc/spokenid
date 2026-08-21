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

## Every release

Do all the edits, then commit, then tag. The tag has to point at the commit
that contains the edits, or the workflow will check the wrong tree.

1. **Set the version** in `src/spokenid/__init__.py`. It is the only place it
   lives; `pyproject.toml` reads it from there.

2. **Move the changelog.** Everything under `## [Unreleased]` becomes a new
   `## [x.y.z] - YYYY-MM-DD` section. Leave `## [Unreleased]` in place, empty,
   and add the comparison link at the bottom of the file.

3. **First release only: fix the install section** of `README.md`. Replace

   ```
   Not on PyPI yet. Until it is:

   pip install git+https://github.com/kuangc/spokenid
   ```

   with `pip install spokenid`. The README is what renders on the PyPI page, so
   it cannot say the package is not on PyPI.

4. **Check it all passes.**

   ```bash
   uv run pytest && uv run mypy && uv run ruff check . && uv run ruff format --check . && uv build
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
changelog and README against the tag, builds, installs the wheel into a clean
environment and uses it, checks the tag matches the package version, and
publishes with attestations.

## If the publish fails

The build artifacts are attached to the workflow run, so nothing needs
rebuilding. Fix the cause, delete the tag locally and on the remote, and tag
again:

```bash
git tag -d v0.1.0 && git push origin :refs/tags/v0.1.0
```

A version that reached PyPI cannot be reused. If the upload itself succeeded
and something else was wrong, bump the patch number instead of retrying.
