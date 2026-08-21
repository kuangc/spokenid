# Releasing

Most of this is checked for you: the suite refuses to pass if the changelog or
the README disagrees with the tags. The steps below are the ones a person has
to take.

## Once, before the first release

1. **Claim the name and set up Trusted Publishing.** On PyPI, add a pending
   publisher for `spokenid` pointing at `kuangc/spokenid`, workflow
   `release.yml`, environment `pypi`. Nothing is published until this exists,
   and doing it this way means there is no API token to store or leak.
2. **Create the `pypi` environment** in the repository settings, so the publish
   job has something to run in.

## Every release

1. Move everything under `## [Unreleased]` in `CHANGELOG.md` into a new
   `## [x.y.z] - YYYY-MM-DD` section, and add the link at the bottom.
   `tests/test_readme_figures.py` fails if a tag exists with no section.
2. Set the version in `src/spokenid/__init__.py`. It is the only place it
   lives; `pyproject.toml` reads it from there.
3. If this is the first release, change the **Install** section of `README.md`
   from `pip install git+https://...` to `pip install spokenid`. The README is
   what renders on the PyPI page, so it cannot say the package is not on PyPI.
   The suite enforces this once a tag exists.
4. Check everything passes:

   ```bash
   uv run pytest && uv run mypy && uv run ruff check . && uv build
   ```

5. Tag and push:

   ```bash
   git tag -a v0.1.0 -m "v0.1.0" && git push --follow-tags
   ```

`release.yml` then runs the full suite on every supported Python, builds,
installs the wheel into a clean environment and uses it, checks the tag matches
the package version, and publishes with attestations.

## If the publish fails

The build artifacts are attached to the workflow run, so nothing needs
rebuilding. Fix the cause, delete the tag locally and remotely, and tag again.
A version that reached PyPI cannot be reused, so bump the patch number rather
than retrying the same one.
