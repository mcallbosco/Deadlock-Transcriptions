"""Render and publish a bounded transcript preview for a pull request.

The privileged workflow that invokes this module runs trusted default-branch
code. Plan artifacts and transcript strings are treated only as untrusted data:
they are schema-checked, escaped, bounded, and never executed.
"""

from __future__ import annotations

import argparse
import html
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


COMMENT_MARKER = "<!-- vlviewer-transcript-preview -->"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
ARTIFACT_RE = re.compile(r"^content-sync-plan-(\d+)$")
GAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
MAX_ARTIFACT_BYTES = 25 * 1024 * 1024
MAX_REPORT_BYTES = 20 * 1024 * 1024
MAX_COMMENT_CHARS = 50_000
SMALL_CHANGE_LIMIT = 25
MEDIUM_CHANGE_LIMIT = 200
MEDIUM_DETAIL_LIMIT = 50
LARGE_DETAIL_LIMIT = 25
MAX_STATE_CHARS = 500


class PreviewError(RuntimeError):
    """Raised for a safe, user-facing preview failure."""


def _json_key(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _safe_inline(value: Any, limit: int = MAX_STATE_CHARS) -> str:
    text = str(value if value is not None else "")
    text = " ".join(text.replace("\x00", "").split())
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    # Prevent bot-authored transcript data from notifying GitHub users or teams.
    text = text.replace("@", "@\u200b")
    return html.escape(text, quote=True)


def _state_label(state: dict[str, Any]) -> str:
    text = state.get("text")
    rendered = "<em>No speech</em>" if text in {None, ""} else f"<code>{_safe_inline(text)}</code>"
    qualifiers: list[str] = []
    source = state.get("source")
    if isinstance(source, str) and source:
        qualifiers.append(_safe_inline(source, 80))
    if state.get("officialtranscription") is True and source != "official":
        qualifiers.append("official")
    if qualifiers:
        rendered += " (" + ", ".join(qualifiers) + ")"
    return rendered


def _valid_states(values: Iterable[Any]) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for value in values:
        if not isinstance(value, dict):
            continue
        text = value.get("text")
        official = value.get("officialtranscription")
        source = value.get("source")
        if text is not None and not isinstance(text, str):
            continue
        if official is not None and not isinstance(official, bool):
            continue
        if source is not None and not isinstance(source, str):
            continue
        normalized = {
            "text": text,
            "officialtranscription": official is True,
        }
        if source:
            normalized["source"] = source
        result[_json_key(normalized)] = normalized
    return [result[key] for key in sorted(result)]


def aggregate_record_changes(plan: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    changes = plan.get("recordChanges")
    if not isinstance(changes, list):
        return []
    for change in changes:
        if not isinstance(change, dict):
            continue
        sha = change.get("sha256")
        if not isinstance(sha, str) or not SHA256_RE.fullmatch(sha):
            continue
        item = grouped.setdefault(
            sha,
            {
                "sha256": sha,
                "paths": set(),
                "versions": set(),
                "statuses": set(),
                "before": {},
                "current": {},
                "desired": {},
            },
        )
        for path in change.get("sourcePaths") or []:
            if isinstance(path, str) and path.startswith("transcripts/"):
                item["paths"].add(path)
        version = change.get("version")
        if isinstance(version, str) and version:
            item["versions"].add(version)
        status = change.get("status")
        if isinstance(status, str) and status:
            item["statuses"].add(status)
        before_values = change.get("expectedOldStates")
        if not isinstance(before_values, list):
            before_values = [change.get("expectedOld")]
        for state in _valid_states(before_values):
            item["before"][_json_key(state)] = state
        for state in _valid_states([change.get("current")]):
            item["current"][_json_key(state)] = state
        for state in _valid_states([change.get("desired")]):
            item["desired"][_json_key(state)] = state

    result: list[dict[str, Any]] = []
    for item in grouped.values():
        item["paths"] = sorted(item["paths"])
        item["versions"] = sorted(item["versions"])
        item["statuses"] = sorted(item["statuses"])
        item["before"] = list(item["before"].values()) or list(item["current"].values())
        item["current"] = list(item["current"].values())
        item["desired"] = list(item["desired"].values())
        result.append(item)
    return sorted(result, key=lambda item: (item["paths"][:1], item["sha256"]))


def validate_preview_changes(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, dict):
            continue
        sha = value.get("sha256")
        if not isinstance(sha, str) or not SHA256_RE.fullmatch(sha) or sha in seen:
            continue
        seen.add(sha)
        paths = sorted(
            {
                path
                for path in value.get("paths") or []
                if isinstance(path, str) and path.startswith("transcripts/")
            }
        )
        versions = sorted(
            {
                version
                for version in value.get("versions") or []
                if isinstance(version, str) and version
            }
        )
        statuses = sorted(
            {
                status
                for status in value.get("statuses") or []
                if isinstance(status, str) and status
            }
        )
        result.append(
            {
                "sha256": sha,
                "paths": paths,
                "versions": versions,
                "statuses": statuses,
                "before": _valid_states(value.get("before") or []),
                "current": _valid_states(value.get("current") or []),
                "desired": _valid_states(value.get("desired") or []),
            }
        )
    return sorted(result, key=lambda item: (item["paths"][:1], item["sha256"]))


def build_preview_payload(plan: dict[str, Any]) -> dict[str, Any]:
    validation = plan.get("validation")
    return {
        "schemaVersion": 1,
        "targetCommit": plan.get("targetCommit"),
        "deployable": plan.get("deployable") is True,
        "errors": [item for item in plan.get("errors", []) if isinstance(item, str)],
        "validation": {
            "valid": validation.get("valid") is True,
            "errors": [
                item for item in validation.get("errors", []) if isinstance(item, str)
            ],
        }
        if isinstance(validation, dict)
        else {"valid": False, "errors": ["Plan has no validation report"]},
        "unmatchedHashes": [
            item
            for item in plan.get("unmatchedHashes", [])
            if isinstance(item, str) and SHA256_RE.fullmatch(item)
        ],
        "previewChanges": aggregate_record_changes(plan),
    }


def _character_counts(changes: Iterable[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for change in changes:
        paths = change.get("paths") or []
        path = paths[0] if paths else ""
        parts = path.split("/")
        counts[parts[1] if len(parts) > 2 else "unknown"] += 1
    return counts


def _state_lines(label: str, states: list[dict[str, Any]]) -> list[str]:
    if not states:
        return [f"- **{label}:** <em>Unknown</em>"]
    if len(states) == 1:
        return [f"- **{label}:** {_state_label(states[0])}"]
    lines = [f"- **{label}:** multiple states"]
    lines.extend(f"  - {_state_label(state)}" for state in states[:5])
    if len(states) > 5:
        lines.append(f"  - …and {len(states) - 5:,} more")
    return lines


def _change_block(
    change: dict[str, Any],
    *,
    cdn_base_url: str,
    game: str,
    expanded: bool,
) -> str:
    sha = change["sha256"]
    paths = change.get("paths") or []
    location = paths[0] if paths else f"recording {sha[:12]}…"
    aliases = len(paths) - 1
    summary = f"<code>{_safe_inline(location, 300)}</code> · <code>{sha[:12]}…</code>"
    if aliases > 0:
        summary += f" · {aliases:,} more path{'s' if aliases != 1 else ''}"
    lines = ["<details" + (" open" if expanded else "") + ">", f"<summary>{summary}</summary>", ""]
    lines.extend(_state_lines("Before", change.get("before") or []))
    if change.get("current") and {
        _json_key(item) for item in change["current"]
    } != {_json_key(item) for item in change.get("before") or []}:
        lines.extend(_state_lines("Live CDN", change["current"]))
    lines.extend(_state_lines("After", change.get("desired") or []))
    versions = change.get("versions") or []
    if versions:
        version_text = ", ".join(_safe_inline(item, 80) for item in versions[:8])
        if len(versions) > 8:
            version_text += f", …and {len(versions) - 8:,} more"
        lines.append(f"- **Published versions:** {version_text}")
    statuses = change.get("statuses") or []
    if "conflict" in statuses:
        lines.append("- **Status:** ⚠️ CDN conflict; this change is blocked")
    audio_url = (
        f"{cdn_base_url.rstrip('/')}/{urllib.parse.quote(game, safe='')}/audio/sha256/"
        f"{sha[:2]}/{sha}.mp3"
    )
    lines.extend(["", f'<a href="{html.escape(audio_url, quote=True)}"><kbd>▶ Play audio</kbd></a>', "", "</details>"])
    return "\n".join(lines)


def build_comment(
    plan: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    *,
    run_url: str,
    head_sha: str,
    cdn_base_url: str = "https://cdn.vlviewer.com",
    game: str = "deadlock",
    workflow_conclusion: str = "success",
) -> str:
    if not GAME_RE.fullmatch(game):
        raise PreviewError("Invalid trusted game identifier")
    if isinstance(plan, dict) and isinstance(plan.get("previewChanges"), list):
        changes = validate_preview_changes(plan["previewChanges"])
    else:
        changes = aggregate_record_changes(plan or {})
    errors: list[str] = []
    if isinstance(validation, dict):
        errors.extend(item for item in validation.get("errors", []) if isinstance(item, str))
    if isinstance(plan, dict):
        errors.extend(item for item in plan.get("errors", []) if isinstance(item, str))
        plan_validation = plan.get("validation")
        if isinstance(plan_validation, dict):
            errors.extend(
                item for item in plan_validation.get("errors", []) if isinstance(item, str)
            )
    errors = list(dict.fromkeys(errors))
    conflicts = sum("conflict" in change["statuses"] for change in changes)
    noops = sum(set(change["statuses"]) == {"noop"} for change in changes)
    deployable = isinstance(plan, dict) and plan.get("deployable") is True
    unmatched = plan.get("unmatchedHashes", []) if isinstance(plan, dict) else []
    unmatched_count = sum(
        isinstance(item, str) and SHA256_RE.fullmatch(item) is not None
        for item in (unmatched if isinstance(unmatched, list) else [])
    )

    if plan is None:
        status = "⚠️ Preview unavailable"
    elif workflow_conclusion == "success" and deployable:
        status = "✅ Deployable"
    elif errors or conflicts or isinstance(plan, dict):
        status = "❌ Blocked"

    lines = [
        COMMENT_MARKER,
        "## Transcript preview",
        "",
        f"**{status}** for `{_safe_inline(head_sha[:12], 12)}`",
        "",
    ]
    if plan is None:
        lines.extend(
            [
                "The content-sync plan was not produced. Check the workflow run for the validation or setup failure.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"- Unique recordings changed: **{len(changes):,}**",
                f"- CDN conflicts: **{conflicts:,}**",
                f"- Already-current CDN recordings: **{noops:,}**",
                f"- Changed hashes not referenced by a published version: **{unmatched_count:,}**",
                "",
            ]
        )

    if errors:
        lines.extend(["### Validation errors", ""])
        for error in errors[:10]:
            lines.append(f"- {_safe_inline(error, 400)}")
        if len(errors) > 10:
            lines.append(f"- …and {len(errors) - 10:,} more")
        lines.append("")

    if len(changes) > SMALL_CHANGE_LIMIT:
        lines.extend(["### Largest character groups", ""])
        for character, count in _character_counts(changes).most_common(10):
            lines.append(f"- `{_safe_inline(character, 80)}`: **{count:,}** recordings")
        lines.append("")

    if changes:
        if len(changes) <= SMALL_CHANGE_LIMIT:
            requested_limit = len(changes)
            expanded = True
        elif len(changes) <= MEDIUM_CHANGE_LIMIT:
            requested_limit = MEDIUM_DETAIL_LIMIT
            expanded = False
        else:
            requested_limit = LARGE_DETAIL_LIMIT
            expanded = False
        lines.extend(["### Recording changes", ""])
        footer = (
            f"\n[View the complete CI report]({run_url})\n\n"
            f"<sub>Analyzed commit <code>{_safe_inline(head_sha[:12], 12)}</code>. "
            "This comment is updated after each PR run.</sub>\n"
        )
        rendered = 0
        for change in changes[:requested_limit]:
            block = _change_block(
                change,
                cdn_base_url=cdn_base_url,
                game=game,
                expanded=expanded,
            )
            candidate = "\n".join([*lines, block, ""]) + footer
            if len(candidate) > MAX_COMMENT_CHARS:
                break
            lines.extend([block, ""])
            rendered += 1
        omitted = len(changes) - rendered
        if omitted:
            lines.extend(
                [
                    f"> Showing {rendered:,} of {len(changes):,} recording changes. "
                    f"The complete report contains the remaining {omitted:,}.",
                    "",
                ]
            )

    lines.extend(
        [
            f"[View the complete CI report]({run_url})",
            "",
            f"<sub>Analyzed commit <code>{_safe_inline(head_sha[:12], 12)}</code>. "
            "This comment is updated after each PR run.</sub>",
        ]
    )
    body = "\n".join(lines).rstrip() + "\n"
    if len(body) > MAX_COMMENT_CHARS:
        raise PreviewError("Generated preview exceeded the bounded comment size")
    return body


def _api_request(
    method: str,
    url: str,
    token: str,
    body: dict[str, Any] | None = None,
    *,
    accept: str = "application/vnd.github+json",
    decode_json: bool = True,
) -> tuple[Any, dict[str, str]]:
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        method=method,
        data=payload,
        headers={
            "Accept": accept,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Deadlock-Transcriptions-preview",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
            redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
            if redirected is not None:
                old = urllib.parse.urlsplit(req.full_url)
                new = urllib.parse.urlsplit(newurl)
                if (old.scheme, old.netloc) != (new.scheme, new.netloc):
                    redirected.remove_header("Authorization")
            return redirected

    try:
        opener = urllib.request.build_opener(SafeRedirectHandler())
        with opener.open(request, timeout=30) as response:
            data = response.read(MAX_ARTIFACT_BYTES + 1)
            headers = {key.lower(): value for key, value in response.headers.items()}
    except (urllib.error.URLError, TimeoutError) as exc:
        raise PreviewError(f"GitHub API request failed: {method} {url}: {exc}") from exc
    if len(data) > MAX_ARTIFACT_BYTES:
        raise PreviewError("GitHub API response exceeded the safety limit")
    if decode_json:
        try:
            return json.loads(data.decode("utf-8")) if data else None, headers
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PreviewError(f"GitHub API returned invalid JSON for {url}") from exc
    return data, headers


def _repository_url(api_url: str, repository: str, suffix: str) -> str:
    owner_repo = repository.split("/", 1)
    if len(owner_repo) != 2 or not all(owner_repo):
        raise PreviewError("GITHUB_REPOSITORY must be owner/name")
    encoded = "/".join(urllib.parse.quote(item, safe="") for item in owner_repo)
    return f"{api_url.rstrip('/')}/repos/{encoded}/{suffix.lstrip('/')}"


def _resolve_pr_number(
    event: dict[str, Any],
    artifacts: list[dict[str, Any]],
    *,
    api_url: str,
    repository: str,
    token: str,
) -> int:
    run = event.get("workflow_run") if isinstance(event, dict) else None
    if not isinstance(run, dict):
        raise PreviewError("Event has no workflow_run object")
    pull_requests = run.get("pull_requests")
    if isinstance(pull_requests, list):
        for pull in pull_requests:
            number = pull.get("number") if isinstance(pull, dict) else None
            if isinstance(number, int) and number > 0:
                return number
    artifact_numbers = {
        int(match.group(1))
        for artifact in artifacts
        if isinstance(artifact, dict)
        and isinstance(artifact.get("name"), str)
        and (match := ARTIFACT_RE.fullmatch(artifact["name"]))
    }
    if len(artifact_numbers) == 1:
        return artifact_numbers.pop()
    head_sha = run.get("head_sha")
    if isinstance(head_sha, str) and GIT_SHA_RE.fullmatch(head_sha):
        pulls, _ = _api_request(
            "GET",
            _repository_url(api_url, repository, f"commits/{head_sha}/pulls"),
            token,
        )
        candidates = [
            item.get("number")
            for item in pulls or []
            if isinstance(item, dict)
            and item.get("state") == "open"
            and isinstance(item.get("number"), int)
        ]
        if len(candidates) == 1:
            return candidates[0]
    raise PreviewError("Could not uniquely associate the workflow run with a pull request")


def _load_artifact_reports(data: bytes) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if len(data) > MAX_ARTIFACT_BYTES:
        raise PreviewError("Artifact archive exceeded the safety limit")
    report_infos: dict[str, zipfile.ZipInfo] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for info in archive.infolist():
                name = Path(info.filename).name
                if name not in {"plan.json", "preview.json", "validation.json"}:
                    continue
                if name in report_infos:
                    raise PreviewError(f"Artifact contains an invalid {name}")
                report_infos[name] = info
            selected_names = [
                name
                for name in (
                    "preview.json" if "preview.json" in report_infos else "plan.json",
                    "validation.json",
                )
                if name in report_infos
            ]
            if sum(report_infos[name].file_size for name in selected_names) > MAX_ARTIFACT_BYTES:
                raise PreviewError("Artifact reports exceeded the safety limit")
            found: dict[str, dict[str, Any]] = {}
            for name in selected_names:
                info = report_infos[name]
                if info.file_size > MAX_REPORT_BYTES:
                    raise PreviewError(f"Artifact contains an invalid {name}")
                raw = archive.read(info)
                try:
                    value = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise PreviewError(f"Artifact contains invalid {name}") from exc
                if not isinstance(value, dict):
                    raise PreviewError(f"Artifact {name} must contain an object")
                found[name] = value
    except zipfile.BadZipFile as exc:
        raise PreviewError("Artifact is not a valid ZIP archive") from exc
    return found.get("preview.json") or found.get("plan.json"), found.get("validation.json")


def _list_artifacts(
    api_url: str, repository: str, run_id: int, token: str
) -> list[dict[str, Any]]:
    value, _ = _api_request(
        "GET",
        _repository_url(api_url, repository, f"actions/runs/{run_id}/artifacts?per_page=100"),
        token,
    )
    artifacts = value.get("artifacts") if isinstance(value, dict) else None
    return [item for item in artifacts or [] if isinstance(item, dict)]


def _download_reports(
    artifacts: list[dict[str, Any]], pr_number: int, token: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    expected = f"content-sync-plan-{pr_number}"
    candidates = [item for item in artifacts if item.get("name") == expected and not item.get("expired")]
    if len(candidates) != 1:
        return None, None
    artifact = candidates[0]
    size = artifact.get("size_in_bytes")
    url = artifact.get("archive_download_url")
    if not isinstance(size, int) or size > MAX_ARTIFACT_BYTES or not isinstance(url, str):
        raise PreviewError("Plan artifact metadata failed validation")
    data, _ = _api_request("GET", url, token, decode_json=False)
    if not isinstance(data, bytes):
        raise PreviewError("Plan artifact download was not binary")
    return _load_artifact_reports(data)


def _upsert_comment(
    *,
    api_url: str,
    repository: str,
    pr_number: int,
    token: str,
    body: str,
) -> None:
    comments: list[dict[str, Any]] = []
    for page in range(1, 11):
        comments_url = _repository_url(
            api_url,
            repository,
            f"issues/{pr_number}/comments?per_page=100&page={page}",
        )
        page_comments, _ = _api_request("GET", comments_url, token)
        if not isinstance(page_comments, list):
            raise PreviewError("GitHub returned an invalid PR comment list")
        comments.extend(item for item in page_comments if isinstance(item, dict))
        if len(page_comments) < 100:
            break
    existing = next(
        (
            item
            for item in comments or []
            if isinstance(item, dict)
            and COMMENT_MARKER in str(item.get("body") or "")
            and isinstance(item.get("user"), dict)
            and item["user"].get("type") == "Bot"
            and isinstance(item.get("id"), int)
        ),
        None,
    )
    if existing:
        url = _repository_url(api_url, repository, f"issues/comments/{existing['id']}")
        _api_request("PATCH", url, token, {"body": body})
    else:
        url = _repository_url(api_url, repository, f"issues/{pr_number}/comments")
        _api_request("POST", url, token, {"body": body})


def comment_from_workflow_run(args: argparse.Namespace) -> int:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise PreviewError("GITHUB_TOKEN is required")
    event = json.loads(args.event.read_text(encoding="utf-8"))
    run = event.get("workflow_run")
    if not isinstance(run, dict) or run.get("event") != "pull_request":
        print("Workflow run is not associated with a pull_request event; skipping.")
        return 0
    run_id = run.get("id")
    head_sha = run.get("head_sha")
    if not isinstance(run_id, int) or not isinstance(head_sha, str) or not GIT_SHA_RE.fullmatch(head_sha):
        raise PreviewError("Workflow run has invalid id or head SHA")
    artifacts = _list_artifacts(args.api_url, args.repository, run_id, token)
    pr_number = _resolve_pr_number(
        event,
        artifacts,
        api_url=args.api_url,
        repository=args.repository,
        token=token,
    )
    pull, _ = _api_request(
        "GET", _repository_url(args.api_url, args.repository, f"pulls/{pr_number}"), token
    )
    pull_head = ((pull or {}).get("head") or {}).get("sha")
    if (pull or {}).get("state") != "open" or pull_head != head_sha:
        print(f"PR #{pr_number} no longer points at {head_sha}; skipping stale preview.")
        return 0
    plan, validation = _download_reports(artifacts, pr_number, token)
    if isinstance(plan, dict) and plan.get("targetCommit") != head_sha:
        plan = None
    server_url = args.server_url.rstrip("/")
    run_url = f"{server_url}/{args.repository}/actions/runs/{run_id}"
    body = build_comment(
        plan,
        validation,
        run_url=run_url,
        head_sha=head_sha,
        cdn_base_url=args.cdn_base_url,
        game=args.game,
        workflow_conclusion=str(run.get("conclusion") or "failure"),
    )
    _upsert_comment(
        api_url=args.api_url,
        repository=args.repository,
        pr_number=pr_number,
        token=token,
        body=body,
    )
    print(f"Updated transcript preview on PR #{pr_number}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--api-url", default="https://api.github.com")
    parser.add_argument("--server-url", default="https://github.com")
    parser.add_argument("--cdn-base-url", default="https://cdn.vlviewer.com")
    parser.add_argument("--game", default="deadlock")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        return comment_from_workflow_run(build_parser().parse_args(argv))
    except (PreviewError, OSError, json.JSONDecodeError) as exc:
        print(f"Transcript preview failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
