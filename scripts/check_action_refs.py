#!/usr/bin/env python3
"""Enforce immutable GitHub Action references in workflow YAML."""

from __future__ import annotations

import re
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

STRING_TAG = "tag:yaml.org,2002:str"
ALLOWED_TAGS = {
    "tag:yaml.org,2002:bool",
    "tag:yaml.org,2002:float",
    "tag:yaml.org,2002:int",
    "tag:yaml.org,2002:map",
    "tag:yaml.org,2002:merge",
    "tag:yaml.org,2002:null",
    "tag:yaml.org,2002:seq",
    STRING_TAG,
    "tag:yaml.org,2002:timestamp",
}
REMOTE_ACTION = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*/"
    r"[A-Za-z0-9][A-Za-z0-9_.-]*"
    r"(?:/[A-Za-z0-9_.-]+)*@"
    r"[0-9a-fA-F]{40}$"
)
VERSION_COMMENT = re.compile(r"#\s*v[0-9]+(?:\.[0-9]+)*(?:\s+.*)?\s*$")


@dataclass(frozen=True)
class Use:
    """One decoded YAML `uses` value and its source line."""

    reference: str
    line: int


class PolicyError(Exception):
    """A workflow construct the policy cannot safely accept."""

    def __init__(self, message: str, line: int = 0) -> None:
        super().__init__(message)
        self.line = line


def _validate_tag(node: Node) -> None:
    if node.tag not in ALLOWED_TAGS:
        raise PolicyError(f"unsupported YAML tag {node.tag!r}", node.start_mark.line)


def _find_uses(root: Node) -> tuple[list[Use], list[tuple[int, int]]]:
    """Walk the composed graph, including nodes reached through aliases."""
    found: list[Use] = []
    scalar_spans: list[tuple[int, int]] = []
    pending = [root]
    seen: set[int] = set()

    while pending:
        node = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        _validate_tag(node)

        if isinstance(node, ScalarNode):
            scalar_spans.append((node.start_mark.index, node.end_mark.index))
        elif isinstance(node, MappingNode):
            for key, value in node.value:
                _validate_tag(key)
                _validate_tag(value)
                if not isinstance(key, ScalarNode):
                    raise PolicyError(
                        "mapping keys must be scalar values", key.start_mark.line
                    )
                if key.tag == STRING_TAG and key.value == "uses":
                    if not isinstance(value, ScalarNode) or value.tag != STRING_TAG:
                        raise PolicyError(
                            "uses value must be a string", value.start_mark.line
                        )
                    found.append(Use(value.value, key.start_mark.line))
                pending.extend((key, value))
        elif isinstance(node, SequenceNode):
            pending.extend(node.value)
        else:
            raise PolicyError(
                f"unsupported YAML node type {type(node).__name__}",
                node.start_mark.line,
            )

    return sorted(found, key=lambda use: use.line), scalar_spans


def _actual_comments(text: str, scalar_spans: list[tuple[int, int]]) -> dict[int, str]:
    """Return YAML comments, excluding `#` characters inside scalar tokens."""
    comments: dict[int, str] = {}
    offset = 0
    for line_number, line in enumerate(text.splitlines(keepends=True)):
        for match in re.finditer("#", line):
            index = offset + match.start()
            if any(start <= index < end for start, end in scalar_spans):
                continue
            comments[line_number] = line[match.start() :].rstrip("\r\n")
            break
        offset += len(line)
    return comments


def _parse(path: Path) -> tuple[dict[int, str], list[Use]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise PolicyError(f"cannot read YAML: {error}") from error

    try:
        root = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        line = mark.line if mark is not None else 0
        raise PolicyError(f"YAML parse error: {error}", line) from error

    if root is None:
        raise PolicyError("YAML document is empty")
    if not isinstance(root, MappingNode):
        raise PolicyError("YAML document root must be a mapping", root.start_mark.line)
    uses, scalar_spans = _find_uses(root)
    return _actual_comments(text, scalar_spans), uses


def _display(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _local_source(root: Path, reference: str, line: int) -> Path:
    relative = Path(reference.removeprefix("./"))
    if relative.is_absolute() or ".." in relative.parts:
        raise PolicyError(f"local reference {reference} escapes the repository", line)

    target = root / relative
    if relative.suffix in {".yml", ".yaml"}:
        if not target.is_file():
            raise PolicyError(f"{reference} does not exist", line)
        _require_inside_root(root, target, reference, line)
        return target

    action_yml = target / "action.yml"
    action_yaml = target / "action.yaml"
    manifests = [path for path in (action_yml, action_yaml) if path.is_file()]
    if not manifests:
        raise PolicyError(f"{reference} has no action.yml or action.yaml", line)
    if len(manifests) > 1:
        raise PolicyError(f"{reference} has both action.yml and action.yaml", line)
    _require_inside_root(root, manifests[0], reference, line)
    return manifests[0]


def _require_inside_root(root: Path, path: Path, reference: str, line: int) -> None:
    try:
        path.resolve().relative_to(root)
    except ValueError as error:
        raise PolicyError(
            f"local reference {reference} resolves outside the repository", line
        ) from error


def _check_remote(reference: str, comment_text: str | None, line: int) -> re.Match[str]:
    if reference.startswith("docker://"):
        raise PolicyError("Docker action references are not supported", line)
    if REMOTE_ACTION.fullmatch(reference) is None:
        raise PolicyError(f"{reference} must use an exact 40-character commit SHA", line)
    comment = (
        VERSION_COMMENT.fullmatch(comment_text) if comment_text is not None else None
    )
    if comment is None:
        raise PolicyError(
            f"{reference} needs a same-line version comment such as '# v7.0.0'",
            line,
        )
    return comment


def check(root: Path) -> int:
    """Check workflows rooted at `root`, returning a process exit status."""
    workflows = sorted((root / ".github" / "workflows").glob("*.yml"))
    workflows.extend(sorted((root / ".github" / "workflows").glob("*.yaml")))
    if not workflows:
        print(".github/workflows: no workflow YAML files found", file=sys.stderr)
        return 1

    pending = deque(workflows)
    queued = {path.resolve() for path in workflows}
    errors: list[str] = []

    while pending:
        path = pending.popleft()
        display = _display(root, path)
        try:
            comments, uses = _parse(path)
        except PolicyError as error:
            errors.append(f"{display}:{error.line + 1}: {error}")
            continue

        for use in uses:
            try:
                if use.reference.startswith("./"):
                    local = _local_source(root, use.reference, use.line)
                    resolved = local.resolve()
                    if resolved not in queued:
                        queued.add(resolved)
                        pending.append(local)
                    print(f"ok      {display}:{use.line + 1} {use.reference} (local)")
                    continue

                comment = _check_remote(use.reference, comments.get(use.line), use.line)
                print(
                    f"ok      {display}:{use.line + 1} {use.reference} {comment.group(0)}"
                )
            except PolicyError as error:
                errors.append(f"{display}:{error.line + 1}: {error}")

    for message in errors:
        print(message, file=sys.stderr)
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(check(Path.cwd().resolve()))
