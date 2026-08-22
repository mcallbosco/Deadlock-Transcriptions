#!/usr/bin/env python3
"""CLI for Phase 1 transcript/config validation, planning, and deployment."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .content_sync import (
    ContentSyncError,
    ContentSyncPlanner,
    PublicJsonStore,
    R2JsonStore,
    deploy_plan,
    load_conflict_approvals,
    require_checked_out_target,
    validate_repository,
    write_backups,
    write_reports,
)
from .pr_transcript_preview import build_preview_payload


DEFAULT_CURSOR = "deadlock/_internal/transcript-sync.json"


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--game", default="deadlock")
    parser.add_argument("--target", default="HEAD")
    parser.add_argument(
        "--repository-name",
        default="mcallbosco/Deadlock-Transcriptions",
    )
    parser.add_argument(
        "--cdn-base-url",
        default=os.environ.get("CDN_BASE_URL", "https://cdn.vlviewer.com"),
    )
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    parser.add_argument(
        "--conflict-approvals",
        type=Path,
        help="Exact, reviewed CDN conflict states that may be overwritten",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely synchronize Deadlock transcript/config changes to VLViewer R2."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="Validate the complete source repository")
    validate.add_argument("--repo", type=Path, default=Path.cwd())
    validate.add_argument("--game", default="deadlock")
    validate.add_argument("--output-json", type=Path)

    plan = commands.add_parser("plan", help="Build a credential-free public-CDN plan")
    add_common(plan)
    plan.add_argument("--base", help="Base Git commit for an incremental plan")
    plan.add_argument("--baseline", action="store_true", help="Reconcile the full target tree")
    plan.add_argument(
        "--output-preview-json",
        type=Path,
        help="Write a compact unique-recording report for the PR comment workflow",
    )

    deploy = commands.add_parser("deploy", help="Build and conditionally deploy an R2 plan")
    add_common(deploy)
    deploy.add_argument("--base", help="Override the cursor's base commit")
    deploy.add_argument(
        "--bucket",
        default=os.environ.get("R2_BUCKET", ""),
    )
    deploy.add_argument(
        "--endpoint-url",
        default=os.environ.get("R2_ENDPOINT_URL", ""),
    )
    deploy.add_argument("--cursor-key", default=DEFAULT_CURSOR)
    deploy.add_argument("--backup-dir", type=Path)
    deploy.add_argument("--result-json", type=Path)
    deploy.add_argument("--zone-id", default=os.environ.get("CLOUDFLARE_ZONE_ID", ""))
    deploy.add_argument("--initialize", action="store_true")
    deploy.add_argument(
        "--reconcile",
        action="store_true",
        help="Reconcile the complete repository against R2 instead of using the cursor range",
    )
    deploy.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the R2-backed plan without writing objects or advancing the cursor",
    )
    deploy.add_argument("--approve-baseline", action="store_true")
    return parser


def validate_command(args: argparse.Namespace) -> int:
    report = validate_repository(args.repo, args.game)
    payload = report.to_json()
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if report.valid else 1


def plan_command(args: argparse.Namespace) -> int:
    if not args.baseline and not args.base:
        raise ContentSyncError("Pass --base for an incremental plan or --baseline.")
    public = PublicJsonStore(args.cdn_base_url)
    planner = ContentSyncPlanner(
        args.repo,
        public,
        args.game,
        args.cdn_base_url,
        load_conflict_approvals(args.conflict_approvals),
    )
    plan = planner.build(
        target=args.target,
        base=args.base,
        baseline=args.baseline,
        repository_name=args.repository_name,
    )
    write_reports(plan, args.output_json, args.output_markdown)
    if args.output_preview_json:
        args.output_preview_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_preview_json.write_text(
            json.dumps(build_preview_payload(plan.to_json()), indent=2, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
    print(plan.to_markdown())
    return 0 if plan.deployable else 1


def deploy_command(args: argparse.Namespace) -> int:
    target_commit = require_checked_out_target(args.repo.resolve(), args.target)
    r2 = R2JsonStore(args.bucket, args.endpoint_url)
    cursor = r2.get_json(args.cursor_key)

    if args.initialize and args.reconcile:
        raise ContentSyncError("Choose either --initialize or --reconcile, not both.")
    if args.initialize:
        if not args.approve_baseline:
            raise ContentSyncError(
                "Initialization requires --approve-baseline after reviewing a baseline plan."
            )
        if cursor.exists:
            raise ContentSyncError(
                "The deployment cursor already exists; refuse baseline initialization."
            )
        base = None
        baseline = True
    elif args.reconcile:
        if not args.dry_run and not args.approve_baseline:
            raise ContentSyncError(
                "Writing a full reconciliation requires --approve-baseline."
            )
        base = None
        baseline = True
    else:
        if not cursor.exists:
            raise ContentSyncError(
                "The deployment cursor does not exist. Run and review a baseline plan, then initialize."
            )
        cursor_commit = cursor.value.get("lastSuccessfulCommit") if cursor.value else None
        if not isinstance(cursor_commit, str) or not cursor_commit:
            raise ContentSyncError("The deployment cursor has no lastSuccessfulCommit.")
        base = args.base or cursor_commit
        baseline = False

    public = PublicJsonStore(args.cdn_base_url)
    planner = ContentSyncPlanner(
        args.repo,
        r2,
        args.game,
        args.cdn_base_url,
        load_conflict_approvals(args.conflict_approvals),
    )
    plan = planner.build(
        target=target_commit,
        base=base,
        baseline=baseline,
        repository_name=args.repository_name,
    )
    write_reports(plan, args.output_json, args.output_markdown)
    write_backups(plan, args.backup_dir)
    print(plan.to_markdown())
    if not plan.deployable:
        if args.result_json:
            args.result_json.parent.mkdir(parents=True, exist_ok=True)
            args.result_json.write_text(
                json.dumps(
                    {"schemaVersion": 1, "status": "blocked", "targetCommit": target_commit},
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        return 1
    if args.dry_run:
        result = {
            "schemaVersion": 1,
            "status": "dry-run",
            "targetCommit": target_commit,
            "plannedWrites": len(plan.writes),
        }
        if args.result_json:
            args.result_json.parent.mkdir(parents=True, exist_ok=True)
            args.result_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0
    result = deploy_plan(
        plan,
        r2,
        public,
        cursor,
        args.cursor_key,
        zone_id=args.zone_id,
        purge_token=os.environ.get("CLOUDFLARE_API_TOKEN", "").strip(),
        result_path=args.result_json,
    )
    print(json.dumps(result, indent=2))
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = build_parser().parse_args()
    try:
        if args.command == "validate":
            return validate_command(args)
        if args.command == "plan":
            return plan_command(args)
        return deploy_command(args)
    except (ContentSyncError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
