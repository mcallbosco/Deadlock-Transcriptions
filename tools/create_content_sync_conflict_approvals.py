#!/usr/bin/env python3
"""Create exact, reviewable overwrite approvals from a content-sync plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


IDENTITY_FIELDS = ("version", "key", "jsonPath", "sha256")


def published_state(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or "text" not in value:
        raise ValueError(f"{label} must be a transcript state")
    official = value.get("officialtranscription")
    if not isinstance(official, bool):
        raise ValueError(f"{label}.officialtranscription must be boolean")
    return {"text": value["text"], "officialtranscription": official}


def approval_from_change(value: Any, index: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"recordChanges[{index}] must be an object")
    missing = [field for field in IDENTITY_FIELDS if not value.get(field)]
    if missing:
        raise ValueError(f"recordChanges[{index}] is missing {', '.join(missing)}")
    return {
        **{field: value[field] for field in IDENTITY_FIELDS},
        "current": published_state(value.get("current"), f"recordChanges[{index}].current"),
        "desired": published_state(value.get("desired"), f"recordChanges[{index}].desired"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-count", type=int, required=True)
    parser.add_argument("--source-run-url", required=True)
    parser.add_argument(
        "--append-existing",
        type=Path,
        help="Preserve and combine approvals from an existing approval file",
    )
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    changes = plan.get("recordChanges")
    if not isinstance(changes, list):
        raise ValueError("Plan has no recordChanges array")
    approvals = [
        approval_from_change(change, index)
        for index, change in enumerate(changes)
        if isinstance(change, dict) and change.get("status") == "conflict"
    ]
    approvals.sort(
        key=lambda item: tuple(str(item[field]) for field in IDENTITY_FIELDS)
    )
    encoded = [json.dumps(item, sort_keys=True, ensure_ascii=False) for item in approvals]
    if len(set(encoded)) != len(encoded):
        raise ValueError("Plan contains duplicate conflict identities/states")
    if len(approvals) != args.expected_count:
        raise ValueError(
            f"Expected {args.expected_count} conflicts, found {len(approvals)}"
        )

    source_plans: list[dict[str, Any]] = []
    existing_approvals: list[dict[str, Any]] = []
    if args.append_existing:
        existing = json.loads(args.append_existing.read_text(encoding="utf-8"))
        if existing.get("schemaVersion") != 1 or not isinstance(existing.get("approvals"), list):
            raise ValueError("Existing approvals must use schemaVersion 1 and contain approvals")
        existing_approvals = existing["approvals"]
        if isinstance(existing.get("sourcePlans"), list):
            source_plans.extend(existing["sourcePlans"])
        elif isinstance(existing.get("sourcePlan"), dict):
            source_plans.append(existing["sourcePlan"])
    source_plans.append(
        {
            "baseCommit": plan.get("baseCommit"),
            "targetCommit": plan.get("targetCommit"),
            "runUrl": args.source_run_url,
        }
    )
    combined = {
        json.dumps(item, sort_keys=True, ensure_ascii=False): item
        for item in [*existing_approvals, *approvals]
    }
    combined_approvals = sorted(
        combined.values(),
        key=lambda item: tuple(str(item[field]) for field in IDENTITY_FIELDS),
    )
    result = {
        "schemaVersion": 1,
        "description": (
            "Exact CDN record states explicitly approved for overwrite. "
            "A changed location, hash, current state, or desired state is not approved."
        ),
        "sourcePlans": source_plans,
        "approvalCount": len(combined_approvals),
        "approvals": combined_approvals,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(combined_approvals)} exact conflict approvals to {args.output} "
        f"({len(approvals)} from the current plan)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
