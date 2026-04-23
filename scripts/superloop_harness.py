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
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_VERSION = 3
ROUND_GATE_RESULTS = {"hard-pass", "soft-pass", "fail"}
GATE_STATUSES = {"gate-complete", "gate-in-progress", "gate-blocked"}
LEGACY_GATE_STATUSES = {
    "stage-complete": "gate-complete",
    "stage-in-progress": "gate-in-progress",
    "stage-blocked": "gate-blocked",
}
ACCEPTED_GATE_STATUSES = GATE_STATUSES | set(LEGACY_GATE_STATUSES)
FAILURE_CLASSES = {
    "budget-exhausted",
    "code-regression",
    "config-missing-optional",
    "config-missing-required",
    "contract-boundary",
    "environment",
    "external-service",
    "mission-complete",
    "permissions",
    "stale-contract",
    "unknown",
    "workflow-syntax",
}
FINISH_STANDARDS = {
    "prototype-ready",
    "workflow-ready",
    "operator-ready",
    "production-ready",
}
LEGACY_FINISH_STANDARD_MAP = {
    "demo-ready": "prototype-ready",
    "product-shape-ready": "workflow-ready",
    "beta-ready": "workflow-ready",
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().replace(microsecond=0).isoformat()


def parse_iso(value: str | None) -> datetime:
    if not value:
        return now_utc()
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return cleaned or "workspace"


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


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


def history_dir_for(workspace_root: Path) -> Path:
    return state_home() / "history" / workspace_key(workspace_root)


def normalize_constraints(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if str(value).strip() else []


def normalize_finish_standard(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    return LEGACY_FINISH_STANDARD_MAP.get(lowered, lowered)


NO_GAP_SENTINELS = {
    "",
    "none",
    "no gaps",
    "no gap",
    "no remaining gaps",
    "no remaining gap",
    "no concrete gaps",
    "no concrete gap",
    "none remaining",
    "nothing remaining",
    "n/a",
    "na",
}


def normalize_remaining_gaps(value: Any) -> list[str]:
    if value is None:
        return []

    raw_items = value if isinstance(value, list) else [value]
    normalized: list[str] = []
    for item in raw_items:
        text = str(item).strip()
        lowered = text.lower()
        if lowered in NO_GAP_SENTINELS:
            continue
        if lowered.startswith("no ") and any(token in lowered for token in ["gap", "gaps", "remaining"]):
            continue
        normalized.append(text)
    return normalized


def normalize_env_keys(values: list[str] | None) -> list[str]:
    if not values:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in re.split(r"[\s,]+", str(value).strip()):
            if not item or item in seen:
                continue
            seen.add(item)
            normalized.append(item)
    return normalized


def normalize_failure_class(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    return normalized if normalized in FAILURE_CLASSES else "unknown"


def infer_finish_standard(goal: str | None, explicit: str | None) -> str:
    normalized = normalize_finish_standard(explicit)
    if normalized:
        return normalized

    text = (goal or "").lower()
    if any(token in text for token in ["production", "production-ready", "线上可靠", "生产可用"]):
        return "production-ready"
    if any(
        token in text
        for token in [
            "operator-ready",
            "放心让它自己跑",
            "交给 agent 自己迭代",
            "autonomous",
            "autonomy",
        ]
    ):
        return "operator-ready"
    if any(
        token in text
        for token in [
            "workflow",
            "主流程跑通",
            "stable",
            "稳定执行",
            "usable",
            "可用",
        ]
    ):
        return "workflow-ready"
    return "prototype-ready"


def infer_current_gate(workstream: str | None, explicit: str | None) -> str:
    if explicit:
        return explicit

    kind = (workstream or "").lower()
    if any(token in kind for token in ["feature", "repo", "code", "path", "workflow"]):
        return "The target workflow or code path completes once and the focused check passes."
    if any(token in kind for token in ["tool", "tooling", "automation", "cli"]):
        return "The setup and main command run once without undocumented rescue steps."
    if any(token in kind for token in ["agent", "harness", "loop"]):
        return "The harness can resume state, record a round, and produce an explicit verdict."
    if any(token in kind for token in ["docs", "research", "handoff", "readme"]):
        return "The deliverable exists in the right place, format, and level of clarity."
    if any(token in kind for token in ["deploy", "deployment", "ops", "operations"]):
        return "The service starts, the health check passes, and the failure path is visible."
    return "The nearest mechanically verifiable main-path gate works end to end."


def infer_success_signal(workstream: str | None, explicit: str | None) -> str:
    if explicit:
        return explicit

    kind = (workstream or "").lower()
    if any(token in kind for token in ["feature", "repo", "code", "path", "workflow"]):
        return "Main workflow completion rate"
    if any(token in kind for token in ["tool", "tooling", "automation", "cli"]):
        return "Fresh-run setup-to-output completion rate"
    if any(token in kind for token in ["agent", "harness", "loop"]):
        return "Successful round-to-verdict completion rate"
    if any(token in kind for token in ["docs", "research", "handoff", "readme"]):
        return "Review-ready deliverable completion rate"
    if any(token in kind for token in ["deploy", "deployment", "ops", "operations"]):
        return "Healthy deploy completion rate"
    return "Primary mission completion rate"


def infer_success_direction(explicit: str | None) -> str:
    return explicit or "higher"


def default_stop_rule(finish_standard: str) -> str:
    if finish_standard == "production-ready":
        return (
            "Stop only when the core workflow is operationally safe, observable, recoverable, "
            "and remaining gaps are non-critical."
        )
    if finish_standard == "operator-ready":
        return (
            "Stop only when the loop can resume safely across turns, stop reasons and budget usage "
            "are explicit, and remaining gaps are non-critical."
        )
    if finish_standard == "workflow-ready":
        return (
            "Stop only when the main workflow is consistently usable, the sharpest failure mode is "
            "visible, and remaining gaps are non-critical."
        )
    return (
        "Stop only when one convincing end-to-end slice is mechanically verified and the sharpest "
        "remaining gap is explicit."
    )


def expected_gap_checks(finish_standard: str) -> list[str]:
    if finish_standard == "production-ready":
        return [
            "observability and incident debugging",
            "rollback and recovery posture",
            "safety and abuse boundaries",
            "core-path automated verification",
        ]
    if finish_standard == "operator-ready":
        return [
            "resume reliability across turns",
            "explicit stop and pause reasons",
            "budget tracking visibility",
            "clear next-round handoff",
        ]
    if finish_standard == "workflow-ready":
        return [
            "main workflow repeatability",
            "smoke coverage or focused checks",
            "failure visibility on the sharpest edge",
        ]
    return [
        "one convincing end-to-end slice",
        "mechanical verification for the slice",
        "sharpest remaining gap made explicit",
    ]


def normalize_contract(contract: dict[str, Any]) -> dict[str, Any]:
    goal = contract.get("goal")
    workstream = contract.get("workstream") or contract.get("artifact")
    finish_standard = infer_finish_standard(goal, contract.get("finish_standard") or contract.get("maturity_target"))
    success_signal = infer_success_signal(workstream, contract.get("success_signal") or contract.get("metric"))
    success_direction = infer_success_direction(
        contract.get("success_direction") or contract.get("direction")
    )
    current_gate = infer_current_gate(workstream, contract.get("current_gate") or contract.get("stage_gate"))

    return {
        "goal": goal,
        "workstream": workstream,
        "finish_standard": finish_standard,
        "success_signal": success_signal,
        "success_direction": success_direction,
        "current_gate": current_gate,
        "scope": contract.get("scope"),
        "constraints": normalize_constraints(contract.get("constraints") or contract.get("constraint")),
        "stop_rule": contract.get("stop_rule") or default_stop_rule(finish_standard),
        "max_rounds": optional_int(contract.get("max_rounds")),
        "timebox_minutes": optional_int(contract.get("timebox_minutes")),
    }


def normalize_round_record(raw: dict[str, Any]) -> dict[str, Any]:
    gate_status = raw.get("gate_status") or raw.get("stage_status") or "gate-in-progress"
    gate_status = LEGACY_GATE_STATUSES.get(gate_status, gate_status)
    mission_complete = raw.get("mission_complete")
    if mission_complete is None:
        mission_complete = raw.get("top_level_goal_met", False)

    record = dict(raw)
    record["gate_status"] = gate_status
    record["failure_class"] = normalize_failure_class(record.get("failure_class"))
    record["mission_complete"] = bool(mission_complete)
    record["remaining_gap_ledger"] = normalize_remaining_gaps(record.get("remaining_gap_ledger"))
    record.pop("stage_status", None)
    record.pop("top_level_goal_met", None)
    return record


def normalize_state(raw_state: dict[str, Any]) -> dict[str, Any]:
    state = dict(raw_state)
    state["version"] = STATE_VERSION
    state["contract"] = normalize_contract(state.get("contract", {}))
    state["guidance"] = {
        "expected_gap_checks": expected_gap_checks(state["contract"]["finish_standard"])
    }
    workspace_root = Path(state.get("workspace_root") or ".").resolve()
    state["remaining_gap_ledger"] = normalize_remaining_gaps(state.get("remaining_gap_ledger"))
    state["rounds"] = [normalize_round_record(round_record) for round_record in state.get("rounds", [])]
    state["next_round"] = state.get("next_round")
    state["blocked_by"] = state.get("blocked_by")
    state["resume_condition"] = state.get("resume_condition")
    state["status"] = state.get("status", "active")
    state["last_verdict"] = state.get("last_verdict", "continue")
    state["stop_reason"] = state.get("stop_reason")
    state["budget_started_at"] = state.get("budget_started_at") or state.get("created_at") or now_iso()
    state["run_id"] = state.get("run_id") or f"legacy-{workspace_key(workspace_root)}"
    state["parent_run_id"] = state.get("parent_run_id")
    return state


def load_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return normalize_state(json.loads(path.read_text()))


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def emit(payload: dict[str, Any]) -> int:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def new_run_id(workspace_root: Path) -> str:
    timestamp = now_utc().strftime("%Y%m%dT%H%M%SZ")
    seed = f"{workspace_root}:{now_iso()}:{uuid.uuid4().hex}"
    return f"{timestamp}-{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:8]}"


def build_state(
    workspace_root: Path,
    contract: dict[str, Any],
    *,
    timestamp: str,
    parent_run_id: str | None = None,
) -> dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "run_id": new_run_id(workspace_root),
        "parent_run_id": parent_run_id,
        "workspace_root": str(workspace_root),
        "workspace_key": workspace_key(workspace_root),
        "created_at": timestamp,
        "updated_at": timestamp,
        "budget_started_at": timestamp,
        "status": "active",
        "last_verdict": "continue",
        "stop_reason": None,
        "contract": contract,
        "guidance": {"expected_gap_checks": expected_gap_checks(contract["finish_standard"])},
        "remaining_gap_ledger": [],
        "rounds": [],
        "next_round": None,
        "blocked_by": None,
        "resume_condition": None,
    }


def archive_state(workspace_root: Path, state: dict[str, Any], *, reason: str) -> Path:
    run_id = state.get("run_id") or f"legacy-{workspace_key(workspace_root)}"
    archive_dir = history_dir_for(workspace_root)
    archive_dir.mkdir(parents=True, exist_ok=True)

    archive_base = slugify(run_id)
    archive_path = archive_dir / f"{archive_base}.json"
    suffix = 1
    while archive_path.exists():
        archive_path = archive_dir / f"{archive_base}-{suffix}.json"
        suffix += 1

    archived_state = dict(state)
    archived_state["archived_at"] = now_iso()
    archived_state["archive_reason"] = reason
    save_state(archive_path, archived_state)
    return archive_path


def minutes_since(value: str | None) -> int:
    return max(0, int((now_utc() - parse_iso(value)).total_seconds() // 60))


def freshness_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    last_round = state.get("rounds", [])[-1] if state.get("rounds") else None
    last_round_at = last_round.get("recorded_at") if last_round else None
    return {
        "contract_age_minutes": minutes_since(state.get("created_at")),
        "created_at": state.get("created_at"),
        "idle_minutes": minutes_since(state.get("updated_at")),
        "last_round_at": last_round_at,
        "rounds_recorded": len(state.get("rounds", [])),
        "run_id": state.get("run_id"),
        "updated_at": state.get("updated_at"),
    }


def build_status_card(
    *,
    stage: str,
    classification: str,
    recommended_action: str,
    blocker: str | None = None,
    can_continue: bool | None = None,
    repeated_failure_count: int | None = None,
) -> dict[str, Any]:
    card = {
        "classification": classification,
        "recommended_action": recommended_action,
        "stage": stage,
    }
    if blocker:
        card["blocking_item"] = blocker
    if can_continue is not None:
        card["can_continue"] = can_continue
    if repeated_failure_count and repeated_failure_count > 1:
        card["repeated_failure_count"] = repeated_failure_count
    return card


def infer_failure_class(
    explicit: str | None,
    *,
    blocked_by: str | None = None,
    round_gate_result: str | None = None,
    gate_status: str | None = None,
    stop_reason: str | None = None,
) -> str | None:
    normalized = normalize_failure_class(explicit)
    if normalized:
        return normalized
    if stop_reason == "mission-complete":
        return "mission-complete"
    if stop_reason == "budget-exhausted":
        return "budget-exhausted"

    text = (blocked_by or "").lower()
    if any(token in text for token in ["secret", "credential", "token", "env", "environment variable", "config"]):
        if any(token in text for token in ["missing", "unset", "not set", "required", "absent"]):
            return "config-missing-required"
        return "environment"
    if any(token in text for token in ["permission", "forbidden", "denied", "auth"]):
        return "permissions"
    if any(token in text for token in ["workflow", "yaml", "syntax"]):
        return "workflow-syntax"
    if any(token in text for token in ["external", "network", "vercel", "cloudflare", "deploy"]):
        return "external-service"
    if gate_status == "gate-blocked":
        return "contract-boundary"
    if round_gate_result == "fail":
        return "code-regression"
    return None


def repeated_failure_count(state: dict[str, Any], failure_class: str | None) -> int:
    if not failure_class:
        return 0

    count = 0
    for round_record in reversed(state.get("rounds", [])):
        if normalize_failure_class(round_record.get("failure_class")) != failure_class:
            break
        count += 1
    return count


def new_mission_hint() -> str:
    return (
        "If the ask changed in this workspace, run `init` without `--continue-existing` to archive "
        "the loaded run and start a fresh mission."
    )


def budget_snapshot(state: dict[str, Any], additional_rounds: int = 0) -> dict[str, Any]:
    contract = state.get("contract", {})
    rounds_used = len(state.get("rounds", [])) + additional_rounds
    max_rounds = contract.get("max_rounds")
    rounds_remaining = None if max_rounds is None else max(max_rounds - rounds_used, 0)
    rounds_exhausted = max_rounds is not None and rounds_used >= max_rounds

    started_at = parse_iso(state.get("budget_started_at") or state.get("created_at"))
    elapsed_minutes = max(0, int((now_utc() - started_at).total_seconds() // 60))
    timebox_minutes = contract.get("timebox_minutes")
    timebox_remaining_minutes = (
        None if timebox_minutes is None else max(timebox_minutes - elapsed_minutes, 0)
    )
    timebox_exhausted = timebox_minutes is not None and elapsed_minutes >= timebox_minutes

    return {
        "elapsed_minutes": elapsed_minutes,
        "max_rounds": max_rounds,
        "rounds_exhausted": rounds_exhausted,
        "rounds_remaining": rounds_remaining,
        "rounds_used": rounds_used,
        "timebox_exhausted": timebox_exhausted,
        "timebox_minutes": timebox_minutes,
        "timebox_remaining_minutes": timebox_remaining_minutes,
    }


def merge_contract(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue
        merged[key] = value
    return normalize_contract(merged)


def maybe_close_for_budget(state: dict[str, Any]) -> bool:
    if state.get("status") != "active":
        return False

    budget = budget_snapshot(state)
    if not budget["rounds_exhausted"] and not budget["timebox_exhausted"]:
        return False

    state["status"] = "completed"
    state["last_verdict"] = "stop"
    state["stop_reason"] = "budget-exhausted"
    state["updated_at"] = now_iso()
    return True


def init_command(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace_root(args.workspace)
    state_path = state_path_for(workspace_root)
    state = load_state(state_path)
    timestamp = now_iso()

    incoming_contract = {
        "goal": args.goal,
        "workstream": args.workstream,
        "finish_standard": args.finish_standard,
        "success_signal": args.success_signal,
        "success_direction": args.success_direction,
        "current_gate": args.current_gate,
        "scope": args.scope,
        "constraints": args.constraint,
        "stop_rule": args.stop_rule,
        "max_rounds": args.max_rounds,
        "timebox_minutes": args.timebox_minutes,
    }

    archived_previous_run = None
    init_mode = "fresh-workspace"

    if state and args.continue_existing and not args.reset:
        state["contract"] = merge_contract(state.get("contract", {}), incoming_contract)
        state["guidance"]["expected_gap_checks"] = expected_gap_checks(
            state["contract"]["finish_standard"]
        )
        state["updated_at"] = timestamp
        state["stop_reason"] = None
        if state.get("status") == "completed":
            state["status"] = "active"
            state["last_verdict"] = "continue"
        init_mode = "continue-existing"
    else:
        contract = normalize_contract(incoming_contract)
        parent_run_id = None
        if state:
            archive_reason = "reset" if args.reset else "new-mission"
            archive_path = archive_state(workspace_root, state, reason=archive_reason)
            parent_run_id = state.get("run_id")
            archived_previous_run = {
                "archive_path": str(archive_path),
                "reason": archive_reason,
                "run_id": parent_run_id,
            }
            init_mode = "new-mission"
        state = build_state(
            workspace_root,
            contract,
            timestamp=timestamp,
            parent_run_id=parent_run_id,
        )

    save_state(state_path, state)
    next_actions = [
        "Run the next implementation round inside the stored contract.",
        "After the round, call `record` before deciding whether to continue or stop.",
    ]
    if init_mode == "continue-existing":
        next_actions.insert(
            0,
            "The current run stayed active because `--continue-existing` was explicit.",
        )
    elif archived_previous_run:
        next_actions.insert(
            0,
            f"Archived the previous run to {archived_previous_run['archive_path']} before starting the new mission.",
        )
    return emit(
        {
            "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
            "archived_previous_run": archived_previous_run,
            "budget_status": budget_snapshot(state),
            "next_actions": next_actions,
            "state": {
                "contract": state["contract"],
                "expected_gap_checks": state["guidance"]["expected_gap_checks"],
                "parent_run_id": state.get("parent_run_id"),
                "run_id": state["run_id"],
                "status": state["status"],
            },
            "status_card": build_status_card(
                stage="init",
                classification=init_mode,
                recommended_action="Run the next implementation round inside the stored contract.",
                can_continue=True,
            ),
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

    changed = maybe_close_for_budget(state)
    save_state(state_path, state)

    last_round = state["rounds"][-1] if state.get("rounds") else None
    budget = budget_snapshot(state)
    next_actions = [new_mission_hint()]
    if state.get("status") == "active":
        next_actions.append(
            "Use `init --continue-existing` only when you intentionally want to keep the current mission and budget."
        )
    if state.get("status") == "completed":
        if state.get("stop_reason") == "budget-exhausted":
            next_actions.append("The recorded budget is exhausted; reset or widen the contract before continuing.")
        else:
            next_actions.append("The recorded run is already complete. Start a new run only if the mission or contract changed.")
    elif state.get("status") == "paused":
        next_actions.append("Resolve the blocker or narrow the contract before resuming.")
    elif state.get("next_round"):
        next_actions.append(f"Resume with the recorded next round: {state['next_round']}")
    else:
        next_actions.append("Choose the next round before continuing.")

    freshness = freshness_snapshot(state)
    status_classification = state.get("stop_reason") or "active-run"
    repeated_failures = 0
    if last_round:
        last_failure_class = normalize_failure_class(last_round.get("failure_class"))
        if last_failure_class:
            status_classification = last_failure_class
            repeated_failures = repeated_failure_count(state, last_failure_class)
    if freshness["idle_minutes"] >= 30 and status_classification == "active-run":
        status_classification = "stale-contract"

    recommended_action = next_actions[-1]
    summary = (
        f"Loaded Superloop harness state for {workspace_root.name} "
        f"(run {state['run_id']}, idle {freshness['idle_minutes']}m)."
    )
    if changed:
        summary = f"Loaded Superloop harness state for {workspace_root.name}; budget is exhausted."

    return emit(
        {
            "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
            "budget_status": budget,
            "freshness": freshness,
            "next_actions": next_actions,
            "state": {
                "blocked_by": state.get("blocked_by"),
                "contract": state.get("contract"),
                "expected_gap_checks": state.get("guidance", {}).get("expected_gap_checks", []),
                "last_round": last_round,
                "last_verdict": state.get("last_verdict"),
                "next_round": state.get("next_round"),
                "parent_run_id": state.get("parent_run_id"),
                "remaining_gap_ledger": state.get("remaining_gap_ledger", []),
                "resume_condition": state.get("resume_condition"),
                "run_id": state.get("run_id"),
                "status": state.get("status"),
                "stop_reason": state.get("stop_reason"),
            },
            "status_card": build_status_card(
                stage="resume",
                classification=status_classification,
                recommended_action=recommended_action,
                blocker=state.get("blocked_by"),
                can_continue=state.get("status") == "active",
                repeated_failure_count=repeated_failures,
            ),
            "status": "success",
            "summary": summary,
        }
    )


def preflight_command(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace_root(args.workspace)
    required_env = normalize_env_keys(args.require_env)
    optional_env = normalize_env_keys(args.optional_env)
    missing_required_env = [name for name in required_env if not os.environ.get(name)]
    missing_optional_env = [name for name in optional_env if not os.environ.get(name)]

    status = "success"
    classification = "ready"
    next_actions: list[str] = []
    blocker = None

    workspace_issue = None
    if not workspace_root.exists():
        workspace_issue = f"Workspace does not exist: {workspace_root}"
    elif not workspace_root.is_dir():
        workspace_issue = f"Workspace is not a directory: {workspace_root}"

    state_home_error = None
    try:
        state_home().mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        state_home_error = f"Cannot prepare state home `{state_home()}`: {exc}"

    if workspace_issue or state_home_error:
        status = "error"
        classification = "environment"
        blocker = workspace_issue or state_home_error
        next_actions.append("Fix the workspace or state-home path before continuing the loop.")
    elif missing_required_env:
        status = "error"
        classification = "config-missing-required"
        blocker = f"Missing required environment variables: {', '.join(missing_required_env)}"
        next_actions.append(f"Set required environment variables: {', '.join(missing_required_env)}")
        next_actions.append("Rerun `preflight` before resuming the next stage.")
    elif missing_optional_env:
        status = "warning"
        classification = "config-missing-optional"
        next_actions.append(f"Optional environment variables are missing: {', '.join(missing_optional_env)}")
        next_actions.append("Continue only if the current stage truly treats them as optional.")
    else:
        next_actions.append("Preflight is clean. Continue to the planned stage.")

    return emit(
        {
            "artifacts": {
                "state_home": str(state_home()),
                "workspace_root": str(workspace_root),
            },
            "next_actions": next_actions,
            "preflight": {
                "missing_optional_env": missing_optional_env,
                "missing_required_env": missing_required_env,
                "optional_env": optional_env,
                "required_env": required_env,
                "stage": args.stage,
            },
            "status": status,
            "status_card": build_status_card(
                stage=args.stage,
                classification=classification,
                recommended_action=next_actions[-1],
                blocker=blocker,
                can_continue=status != "error",
            ),
            "summary": f"Preflight completed for {workspace_root.name}.",
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

    gate_status = LEGACY_GATE_STATUSES.get(args.gate_status, args.gate_status)
    if gate_status not in GATE_STATUSES:
        raise ValueError(f"Unexpected gate status: {args.gate_status}")

    remaining_gap_ledger = normalize_remaining_gaps(args.remaining_gap)
    if not remaining_gap_ledger:
        remaining_gap_ledger = normalize_remaining_gaps(state.get("remaining_gap_ledger", []))
    blocked_by = args.blocked_by
    resume_condition = args.resume_condition

    if gate_status == "gate-blocked" and not blocked_by:
        blocked_by = "Gate blocked by an unresolved dependency or contract boundary."
    if blocked_by and not resume_condition:
        resume_condition = "Remove the blocker or narrow the contract, then resume the recorded next round."

    can_continue = not args.cannot_continue and not args.would_exceed_contract and not blocked_by
    mission_complete = args.mission_complete
    success_stop = (mission_complete or args.stop_rule_satisfied) and not remaining_gap_ledger
    projected_budget = budget_snapshot(state, additional_rounds=1)
    budget_exhausted = projected_budget["rounds_exhausted"] or projected_budget["timebox_exhausted"]

    if success_stop:
        verdict = "stop"
        status = "completed"
        stop_reason = "mission-complete" if mission_complete else "stop-rule-satisfied"
        next_round = None
        blocked_by = None
        resume_condition = None
    elif budget_exhausted:
        verdict = "stop"
        status = "completed"
        stop_reason = "budget-exhausted"
        next_round = args.next_round
    elif can_continue and gate_status != "gate-blocked":
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
        stop_reason = None
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
        stop_reason = None
        next_round = args.next_round

    failure_class = infer_failure_class(
        args.failure_class,
        blocked_by=blocked_by,
        round_gate_result=args.round_gate_result,
        gate_status=gate_status,
        stop_reason=stop_reason,
    )
    repeated_failures = repeated_failure_count(state, failure_class) + (1 if failure_class else 0)
    round_number = len(state.get("rounds", [])) + 1
    round_record = {
        "round_number": round_number,
        "recorded_at": now_iso(),
        "hypothesis": args.hypothesis,
        "change": args.change,
        "round_gate": args.round_gate,
        "round_gate_result": args.round_gate_result,
        "gate_status": gate_status,
        "next_round": next_round,
        "remaining_gap_ledger": remaining_gap_ledger,
        "mission_complete": mission_complete,
        "stop_rule_satisfied": args.stop_rule_satisfied,
        "blocked_by": blocked_by,
        "failure_class": failure_class,
        "resume_condition": resume_condition,
        "would_exceed_contract": args.would_exceed_contract,
        "cannot_continue": args.cannot_continue,
        "verdict": verdict,
        "stop_reason": stop_reason,
    }

    state["rounds"].append(round_record)
    state["remaining_gap_ledger"] = remaining_gap_ledger
    state["next_round"] = next_round
    state["blocked_by"] = blocked_by
    state["resume_condition"] = resume_condition
    state["status"] = status
    state["last_verdict"] = verdict
    state["stop_reason"] = stop_reason
    state["updated_at"] = now_iso()
    save_state(state_path, state)

    budget = budget_snapshot(state)
    next_actions = []
    if repeated_failures >= 2 and failure_class not in {"mission-complete", "budget-exhausted"}:
        next_actions.append(
            f"Failure class `{failure_class}` has repeated for {repeated_failures} consecutive rounds; change strategy or escalate instead of retrying blindly."
        )
    if verdict == "continue":
        next_actions.append(f"Continue with the recorded next round: {next_round}")
    elif verdict == "pause":
        next_actions.append("Resolve the blocker or narrow the contract before resuming.")
        next_actions.append(f"Resume with the recorded next round: {next_round}")
    elif stop_reason == "budget-exhausted" and next_round:
        next_actions.append(f"Budget is exhausted; if you reopen the contract, resume with: {next_round}")
    else:
        next_actions.append("The harness allows a normal stop for this run.")

    return emit(
        {
            "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
            "budget_status": budget,
            "next_actions": next_actions,
            "state": {
                "blocked_by": blocked_by,
                "failure_class": failure_class,
                "next_round": next_round,
                "remaining_gap_ledger": remaining_gap_ledger,
                "resume_condition": resume_condition,
                "status": status,
                "stop_reason": stop_reason,
            },
            "status_card": build_status_card(
                stage="record",
                classification=failure_class or verdict,
                recommended_action=next_actions[-1],
                blocker=blocked_by,
                can_continue=verdict == "continue",
                repeated_failure_count=repeated_failures,
            ),
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
    init_parser.add_argument("--workstream", "--artifact", dest="workstream")
    init_parser.add_argument("--finish-standard", "--maturity-target", dest="finish_standard")
    init_parser.add_argument("--success-signal", "--metric", dest="success_signal")
    init_parser.add_argument("--success-direction", "--direction", dest="success_direction")
    init_parser.add_argument("--current-gate", "--stage-gate", dest="current_gate")
    init_parser.add_argument("--scope")
    init_parser.add_argument("--constraint", action="append", default=[])
    init_parser.add_argument("--stop-rule")
    init_parser.add_argument("--max-rounds", type=positive_int)
    init_parser.add_argument("--timebox-minutes", type=positive_int)
    init_parser.add_argument("--continue-existing", action="store_true")
    init_parser.add_argument("--reset", action="store_true")
    init_parser.set_defaults(func=init_command)

    preflight_parser = subparsers.add_parser(
        "preflight",
        help="Check workspace and environment prerequisites before a risky stage.",
    )
    preflight_parser.add_argument("--workspace")
    preflight_parser.add_argument("--stage", default="preflight")
    preflight_parser.add_argument("--require-env", action="append", default=[])
    preflight_parser.add_argument("--optional-env", action="append", default=[])
    preflight_parser.set_defaults(func=preflight_command)

    resume_parser = subparsers.add_parser("resume", help="Load the current Superloop run.")
    resume_parser.add_argument("--workspace")
    resume_parser.set_defaults(func=resume_command)

    record_parser = subparsers.add_parser(
        "record", help="Persist the latest Superloop round and compute the loop verdict."
    )
    record_parser.add_argument("--workspace")
    record_parser.add_argument("--hypothesis", required=True)
    record_parser.add_argument("--change", required=True)
    record_parser.add_argument("--round-gate", required=True)
    record_parser.add_argument("--round-gate-result", required=True, choices=sorted(ROUND_GATE_RESULTS))
    record_parser.add_argument("--gate-status", "--stage-status", dest="gate_status", required=True, choices=sorted(ACCEPTED_GATE_STATUSES))
    record_parser.add_argument("--next-round")
    record_parser.add_argument("--remaining-gap", action="append", default=[])
    record_parser.add_argument("--mission-complete", "--top-level-goal-met", dest="mission_complete", action="store_true")
    record_parser.add_argument("--stop-rule-satisfied", action="store_true")
    record_parser.add_argument("--blocked-by")
    record_parser.add_argument("--failure-class", choices=sorted(FAILURE_CLASSES))
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
