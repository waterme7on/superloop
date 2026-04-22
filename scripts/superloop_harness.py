#!/usr/bin/env python3
"""Stateful CLI harness for the Superloop skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROUND_GATE_RESULTS = {"hard-pass", "soft-pass", "fail"}
STAGE_STATUSES = {"stage-complete", "stage-in-progress", "stage-blocked"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return cleaned or "workspace"


def resolve_workspace_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
        git_root = result.stdout.strip()
        if git_root:
            return Path(git_root).resolve()
    except Exception:
        pass

    return Path.cwd().resolve()


def state_home() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    return Path(os.environ.get("SUPERLOOP_STATE_HOME", codex_home / "state" / "superloop")).expanduser()


def workspace_key(workspace_root: Path) -> str:
    digest = hashlib.sha1(str(workspace_root).encode("utf-8")).hexdigest()[:10]
    return f"{slugify(workspace_root.name)}-{digest}"


def state_path_for(workspace_root: Path) -> Path:
    return state_home() / f"{workspace_key(workspace_root)}.json"


def infer_maturity_target(goal: str, explicit: str | None) -> str:
    if explicit:
        return explicit

    text = goal.lower()
    if any(token in text for token in ["production", "production-ready", "线上可靠", "生产可用"]):
        return "production-ready"
    if any(token in text for token in ["beta", "真实用户", "给用户用", "可用"]):
        return "beta-ready"
    if any(token in text for token in ["商业产品", "真正的产品", "可售卖", "real product"]):
        return "product-shape-ready"
    return "demo-ready"


def infer_stage_gate(artifact: str | None, explicit: str | None) -> str:
    if explicit:
        return explicit

    kind = (artifact or "").lower()
    if any(token in kind for token in ["store", "storefront", "product", "shop"]):
        return "The primary commerce path works end to end and key commerce events can be verified."
    if "landing" in kind:
        return "The primary CTA and submission path work end to end on the current landing page."
    if any(token in kind for token in ["app", "onboarding", "activation"]):
        return "A new user can reach the primary action and see a success state in one session."
    return "The nearest mechanically verifiable main-path gate works end to end."


def infer_metric(artifact: str | None, explicit: str | None) -> str:
    if explicit:
        return explicit

    kind = (artifact or "").lower()
    if any(token in kind for token in ["store", "storefront", "product", "shop"]):
        return "Product-page-to-primary-action completion rate"
    if "landing" in kind:
        return "Primary CTA to successful submission rate"
    if any(token in kind for token in ["app", "onboarding", "activation"]):
        return "First-session primary-action completion rate"
    return "Primary path completion rate"


def infer_direction(explicit: str | None) -> str:
    return explicit or "higher"


def default_stop_rule(maturity_target: str) -> str:
    if maturity_target == "production-ready":
        return (
            "Stop only when the core journey is operationally safe, observable, recoverable, "
            "and remaining gaps are non-critical."
        )
    if maturity_target == "beta-ready":
        return (
            "Stop only when the core journey works for limited real users across sessions, analytics "
            "or error visibility exists, and remaining gaps are non-critical."
        )
    if maturity_target == "product-shape-ready":
        return (
            "Stop only when the main journey works on the named surface, trust and clarity gaps are "
            "non-critical, and the next highest-risk gap is either closed or explicitly blocked."
        )
    return (
        "Stop only when the happy-path demo is mechanically verified, the current stage is advanced "
        "or explicitly blocked, and stage completion is not being mistaken for goal completion."
    )


def expected_gap_checks(maturity_target: str) -> list[str]:
    if maturity_target == "production-ready":
        return [
            "observability and incident debugging",
            "rollback and recovery posture",
            "security and abuse boundaries",
            "core-path automated verification",
        ]
    if maturity_target == "beta-ready":
        return [
            "identity or account continuity",
            "server-side persistence",
            "analytics or error visibility",
            "core-path smoke coverage",
        ]
    if maturity_target == "product-shape-ready":
        return [
            "main-journey clarity",
            "trust-signaling on the target surface",
            "basic event visibility for the main path",
        ]
    return [
        "happy-path demo verification",
        "highest-risk visible gap closed or explicitly blocked",
    ]


def load_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def emit(payload: dict[str, Any]) -> int:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def init_command(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace_root(args.workspace)
    state_path = state_path_for(workspace_root)
    state = load_state(state_path)
    maturity_target = infer_maturity_target(args.goal, args.maturity_target)
    stage_gate = infer_stage_gate(args.artifact, args.stage_gate)
    metric = infer_metric(args.artifact, args.metric)
    direction = infer_direction(args.direction)
    stop_rule = args.stop_rule or default_stop_rule(maturity_target)
    timestamp = now_iso()

    if state and not args.reset:
        existing_contract = state.get("contract", {})
        contract = {
            "goal": args.goal or existing_contract.get("goal"),
            "artifact": args.artifact or existing_contract.get("artifact"),
            "maturity_target": maturity_target or existing_contract.get("maturity_target"),
            "metric": metric or existing_contract.get("metric"),
            "direction": direction or existing_contract.get("direction"),
            "stage_gate": stage_gate or existing_contract.get("stage_gate"),
            "scope": args.scope or existing_contract.get("scope"),
            "constraints": args.constraint or existing_contract.get("constraints", []),
            "stop_rule": stop_rule or existing_contract.get("stop_rule"),
        }
        state["contract"] = contract
        state["guidance"]["expected_gap_checks"] = expected_gap_checks(maturity_target)
        state["updated_at"] = timestamp
        if state.get("status") == "completed":
            state["status"] = "active"
            state["last_verdict"] = "continue"
    else:
        contract = {
            "goal": args.goal,
            "artifact": args.artifact,
            "maturity_target": maturity_target,
            "metric": metric,
            "direction": direction,
            "stage_gate": stage_gate,
            "scope": args.scope,
            "constraints": args.constraint,
            "stop_rule": stop_rule,
        }
        state = {
            "version": 1,
            "workspace_root": str(workspace_root),
            "workspace_key": workspace_key(workspace_root),
            "created_at": timestamp,
            "updated_at": timestamp,
            "status": "active",
            "last_verdict": "continue",
            "contract": contract,
            "guidance": {"expected_gap_checks": expected_gap_checks(maturity_target)},
            "remaining_gap_ledger": [],
            "rounds": [],
            "next_round": None,
            "blocked_by": None,
            "resume_condition": None,
        }

    save_state(state_path, state)
    return emit(
        {
            "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
            "next_actions": [
                "Run the next implementation round inside the stored contract.",
                "After the round, call `record` before deciding whether to continue or stop.",
            ],
            "state": {
                "contract": state["contract"],
                "expected_gap_checks": state["guidance"]["expected_gap_checks"],
                "status": state["status"],
            },
            "status": "success",
            "summary": f"Initialized Superloop harness for {workspace_root.name}.",
        }
    )


def resume_command(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace_root(args.workspace)
    state_path = state_path_for(workspace_root)
    state = load_state(state_path)
    if not state:
        return emit(
            {
                "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
                "next_actions": [
                    "Initialize a new run with `init` before trying to continue the loop."
                ],
                "status": "warning",
                "summary": f"No Superloop harness state exists for {workspace_root.name}.",
            }
        )

    last_round = state["rounds"][-1] if state.get("rounds") else None
    next_actions = []
    if state.get("status") == "paused":
        next_actions.append("Resolve the blocker or narrow the contract before resuming.")
    if state.get("next_round"):
        next_actions.append(f"Resume with the recorded next round: {state['next_round']}")
    else:
        next_actions.append("Choose the next round before continuing.")

    return emit(
        {
            "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
            "next_actions": next_actions,
            "state": {
                "blocked_by": state.get("blocked_by"),
                "contract": state.get("contract"),
                "expected_gap_checks": state.get("guidance", {}).get("expected_gap_checks", []),
                "last_round": last_round,
                "last_verdict": state.get("last_verdict"),
                "next_round": state.get("next_round"),
                "remaining_gap_ledger": state.get("remaining_gap_ledger", []),
                "resume_condition": state.get("resume_condition"),
                "status": state.get("status"),
            },
            "status": "success",
            "summary": f"Loaded Superloop harness state for {workspace_root.name}.",
        }
    )


def record_command(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace_root(args.workspace)
    state_path = state_path_for(workspace_root)
    state = load_state(state_path)
    if not state:
        return emit(
            {
                "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
                "next_actions": ["Run `init` before recording a round."],
                "status": "error",
                "summary": "Cannot record a round without an initialized Superloop harness state.",
            }
        )

    if args.round_gate_result not in ROUND_GATE_RESULTS:
        raise ValueError(f"Unexpected round gate result: {args.round_gate_result}")
    if args.stage_status not in STAGE_STATUSES:
        raise ValueError(f"Unexpected stage status: {args.stage_status}")

    remaining_gap_ledger = args.remaining_gap or state.get("remaining_gap_ledger", [])
    blocked_by = args.blocked_by
    resume_condition = args.resume_condition

    if args.stage_status == "stage-blocked" and not blocked_by:
        blocked_by = "Stage blocked by an unresolved dependency or contract boundary."
    if blocked_by and not resume_condition:
        resume_condition = "Remove the blocker or narrow the contract, then resume the recorded next round."

    can_continue = not args.cannot_continue and not args.would_exceed_contract and not blocked_by

    if (args.top_level_goal_met or args.stop_rule_satisfied) and not remaining_gap_ledger:
        verdict = "stop"
        status = "completed"
        next_round = None
        blocked_by = None
        resume_condition = None
    elif can_continue and args.stage_status != "stage-blocked":
        if not args.next_round:
            return emit(
                {
                    "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
                    "next_actions": [
                        "Provide `--next-round` when the harness should continue after this round."
                    ],
                    "status": "error",
                    "summary": "Missing `--next-round` for a continuing Superloop run.",
                }
            )
        verdict = "continue"
        status = "active"
        next_round = args.next_round
    else:
        if not args.next_round:
            return emit(
                {
                    "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
                    "next_actions": [
                        "Provide `--next-round` so the paused run has a concrete resume target."
                    ],
                    "status": "error",
                    "summary": "Missing `--next-round` for a paused Superloop run.",
                }
            )
        verdict = "pause"
        status = "paused"
        next_round = args.next_round

    round_number = len(state.get("rounds", [])) + 1
    round_record = {
        "round_number": round_number,
        "recorded_at": now_iso(),
        "hypothesis": args.hypothesis,
        "change": args.change,
        "round_gate": args.round_gate,
        "round_gate_result": args.round_gate_result,
        "stage_status": args.stage_status,
        "next_round": next_round,
        "remaining_gap_ledger": remaining_gap_ledger,
        "top_level_goal_met": args.top_level_goal_met,
        "stop_rule_satisfied": args.stop_rule_satisfied,
        "blocked_by": blocked_by,
        "resume_condition": resume_condition,
        "would_exceed_contract": args.would_exceed_contract,
        "cannot_continue": args.cannot_continue,
    }

    state["rounds"].append(round_record)
    state["remaining_gap_ledger"] = remaining_gap_ledger
    state["next_round"] = next_round
    state["blocked_by"] = blocked_by
    state["resume_condition"] = resume_condition
    state["status"] = status
    state["last_verdict"] = verdict
    state["updated_at"] = now_iso()
    save_state(state_path, state)

    next_actions = []
    if verdict == "continue":
        next_actions.append(f"Continue with the recorded next round: {next_round}")
    elif verdict == "pause":
        next_actions.append("Resolve the blocker or narrow the contract before resuming.")
        next_actions.append(f"Resume with the recorded next round: {next_round}")
    else:
        next_actions.append("The harness allows a normal stop for this run.")

    return emit(
        {
            "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
            "next_actions": next_actions,
            "state": {
                "blocked_by": blocked_by,
                "next_round": next_round,
                "remaining_gap_ledger": remaining_gap_ledger,
                "resume_condition": resume_condition,
                "status": status,
            },
            "status": "success",
            "summary": f"Recorded round {round_number}; harness verdict is `{verdict}`.",
            "verdict": verdict,
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Harness for the Superloop skill.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize or refresh a Superloop run.")
    init_parser.add_argument("--workspace")
    init_parser.add_argument("--goal", required=True)
    init_parser.add_argument("--artifact")
    init_parser.add_argument("--maturity-target")
    init_parser.add_argument("--metric")
    init_parser.add_argument("--direction")
    init_parser.add_argument("--stage-gate")
    init_parser.add_argument("--scope")
    init_parser.add_argument("--constraint", action="append", default=[])
    init_parser.add_argument("--stop-rule")
    init_parser.add_argument("--reset", action="store_true")
    init_parser.set_defaults(func=init_command)

    resume_parser = subparsers.add_parser("resume", help="Load the current Superloop run.")
    resume_parser.add_argument("--workspace")
    resume_parser.set_defaults(func=resume_command)

    record_parser = subparsers.add_parser("record", help="Persist the latest Superloop round and compute the loop verdict.")
    record_parser.add_argument("--workspace")
    record_parser.add_argument("--hypothesis", required=True)
    record_parser.add_argument("--change", required=True)
    record_parser.add_argument("--round-gate", required=True)
    record_parser.add_argument("--round-gate-result", required=True, choices=sorted(ROUND_GATE_RESULTS))
    record_parser.add_argument("--stage-status", required=True, choices=sorted(STAGE_STATUSES))
    record_parser.add_argument("--next-round")
    record_parser.add_argument("--remaining-gap", action="append", default=[])
    record_parser.add_argument("--top-level-goal-met", action="store_true")
    record_parser.add_argument("--stop-rule-satisfied", action="store_true")
    record_parser.add_argument("--blocked-by")
    record_parser.add_argument("--resume-condition")
    record_parser.add_argument("--cannot-continue", action="store_true")
    record_parser.add_argument("--would-exceed-contract", action="store_true")
    record_parser.set_defaults(func=record_command)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
