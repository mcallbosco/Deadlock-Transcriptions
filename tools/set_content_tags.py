"""Set a logical transcript group's tags, including its aliases and duplicate hashes."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from .content_sync import _document_states
from .content_tags import assignment_errors, logical_tag_groups, validate_definitions
from .transcript_schema import revision_tags


def plan_group_tags(documents: dict[str, dict[str, Any]], correlations: list[list[str]], filename: str, sha256: str, tags: list[str]) -> dict[str, dict[str, Any]]:
    normalized = list(revision_tags({"tags": tags}))
    selected = {(filename, index) for index, revision in enumerate(documents.get(filename, {}).get("revisions", [])) if sha256 in revision["sha256"]}
    if not selected:
        raise ValueError(f"No recording {sha256} in {filename}")
    groups = logical_tag_groups(documents, correlations)
    by_sha: dict[str, set[tuple[str, int]]] = {}
    for name, document in documents.items():
        for index, revision in enumerate(document["revisions"]):
            for sha in revision["sha256"]:
                by_sha.setdefault(sha, set()).add((name, index))
    memberships = [set(group) for group in groups] + list(by_sha.values())
    while True:
        expanded = selected | set().union(*(group for group in memberships if selected & group))
        if expanded == selected:
            break
        selected = expanded
    changed = {}
    for name, index in sorted(selected):
        if name not in changed:
            changed[name] = copy.deepcopy(documents[name])
        document = changed[name]
        if normalized:
            document["revisions"][index]["tags"] = normalized[:]
        else:
            document["revisions"][index].pop("tags", None)
    return {name: document for name, document in changed.items() if document != documents[name]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--game", default="deadlock")
    parser.add_argument("--filename", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--tags", nargs="*", required=True, help="Complete desired set; omit values to clear")
    parser.add_argument("--apply", action="store_true", help="Write changes; default prints a dry-run report")
    args = parser.parse_args()
    repo = args.repo.resolve()
    documents = {}
    for path in sorted((repo / "transcripts").rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        _document_states(document, str(path))
        filename = path.relative_to(repo / "transcripts").as_posix()[:-5]
        if document["filename"] != filename:
            raise ValueError(f"Filename does not match path: {path}")
        documents[filename] = document
    root = repo / "config" / args.game
    definitions = validate_definitions(json.loads((root / "content-tags.json").read_text()), args.game)
    if set(args.tags) - {tag["id"] for tag in definitions}:
        raise ValueError("Requested tags are not in content-tags.json")
    correlations_path = root / "voice-line-history-correlations.json"
    correlations = json.loads(correlations_path.read_text())["correlations"] if correlations_path.exists() else []
    changed = plan_group_tags(documents, correlations, args.filename, args.sha256, args.tags)
    errors = assignment_errors({**documents, **changed}, definitions, correlations)
    if errors:
        raise ValueError("\n".join(errors))
    report = [{"path": f"transcripts/{name}.json", "before": documents[name], "after": document} for name, document in sorted(changed.items())]
    print(json.dumps({"apply": args.apply, "changedFiles": len(changed), "changes": report}, indent=2, ensure_ascii=False))
    if args.apply:
        for name, document in changed.items():
            (repo / "transcripts" / f"{name}.json").write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
