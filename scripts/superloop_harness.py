#!/usr/bin/env python3
"""Stateful CLI harness for the Superloop skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_VERSION = 3
HOST_CHOICES = {"auto", "generic", "codex", "claude-code"}
HOST_ALIASES = {
    "claude": "claude-code",
    "claudecode": "claude-code",
    "claude_code": "claude-code",
    "openai": "codex",
}
TREE_EXCLUDED_DIRS = {".git", ".github", "__pycache__", ".pytest_cache"}
TREE_EXCLUDED_FILES = {".DS_Store", ".superloop-install.json"}
ROUND_GATE_RESULTS = {"hard-pass", "soft-pass", "fail"}
GATE_STATUSES = {"gate-complete", "gate-in-progress", "gate-blocked"}
LEGACY_GATE_STATUSES = {
    "stage-complete": "gate-complete",
    "stage-in-progress": "gate-in-progress",
    "stage-blocked": "gate-blocked",
}
ACCEPTED_GATE_STATUSES = GATE_STATUSES | set(LEGACY_GATE_STATUSES)
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


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def normalize_host(value: str | None) -> str:
    host = (value or "auto").strip().lower()
    host = HOST_ALIASES.get(host, host)
    if host not in HOST_CHOICES:
        raise argparse.ArgumentTypeError(
            f"host must be one of: {', '.join(sorted(HOST_CHOICES))}"
        )
    return host


def path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def claude_home() -> Path:
    return Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude")).expanduser()


def superloop_home() -> Path:
    return Path(os.environ.get("SUPERLOOP_HOME", Path.home() / ".superloop")).expanduser()


def detect_host(explicit: str | None = None) -> str:
    requested = normalize_host(explicit)
    if requested != "auto":
        return requested

    env_host = os.environ.get("SUPERLOOP_HOST")
    if env_host:
        return normalize_host(env_host)

    script_path = Path(__file__).resolve()
    if path_is_relative_to(script_path, codex_home() / "skills"):
        return "codex"
    if path_is_relative_to(script_path, claude_home() / "skills"):
        return "claude-code"
    if "CLAUDECODE" in os.environ or "CLAUDE_CODE" in os.environ:
        return "claude-code"
    return "generic"


def default_state_home(host: str) -> Path:
    explicit_state_home = os.environ.get("SUPERLOOP_STATE_HOME")
    if explicit_state_home:
        return Path(explicit_state_home).expanduser()

    explicit_home = os.environ.get("SUPERLOOP_HOME")
    if explicit_home:
        return Path(explicit_home).expanduser() / "state"

    if host == "codex":
        return codex_home() / "state" / "superloop"
    if host == "claude-code":
        return claude_home() / "state" / "superloop"
    return superloop_home() / "state"


def installed_path_for_host(host: str) -> Path:
    if host == "codex":
        return codex_home() / "skills" / "superloop"
    if host == "claude-code":
        return claude_home() / "skills" / "superloop"
    return Path(os.environ.get("SUPERLOOP_INSTALL_PATH", superloop_home() / "superloop")).expanduser()


def host_profile(host_arg: str | None = None) -> dict[str, Any]:
    host = detect_host(host_arg)
    installed_path = installed_path_for_host(host)
    host_home = {
        "codex": codex_home(),
        "claude-code": claude_home(),
        "generic": superloop_home(),
    }[host]
    metadata_files = {
        "codex": ["agents/openai.yaml", "SKILL.md"],
        "claude-code": ["SKILL.md"],
        "generic": [],
    }[host]

    return {
        "host": host,
        "host_home": str(host_home),
        "installed_path": str(installed_path),
        "harness_path": str(installed_path / "scripts" / "superloop_cli.sh"),
        "state_home": str(default_state_home(host)),
        "metadata_files": metadata_files,
    }


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


def workspace_key(workspace_root: Path) -> str:
    digest = hashlib.sha1(str(workspace_root).encode("utf-8")).hexdigest()[:10]
    return f"{slugify(workspace_root.name)}-{digest}"


def state_path_for(workspace_root: Path, host_arg: str | None = None) -> Path:
    host = detect_host(host_arg)
    return default_state_home(host) / f"{workspace_key(workspace_root)}.json"


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
    state["remaining_gap_ledger"] = normalize_remaining_gaps(state.get("remaining_gap_ledger"))
    state["rounds"] = [normalize_round_record(round_record) for round_record in state.get("rounds", [])]
    state["next_round"] = state.get("next_round")
    state["blocked_by"] = state.get("blocked_by")
    state["resume_condition"] = state.get("resume_condition")
    state["status"] = state.get("status", "active")
    state["last_verdict"] = state.get("last_verdict", "continue")
    state["stop_reason"] = state.get("stop_reason")
    state["budget_started_at"] = state.get("budget_started_at") or state.get("created_at") or now_iso()
    return state


def load_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return normalize_state(json.loads(path.read_text()))


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def emit(payload: dict[str, Any], exit_code: int = 0) -> int:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
    sys.stdout.write("\n")
    return exit_code


def emit_markdown(markdown: str, exit_code: int = 0) -> int:
    sys.stdout.write(markdown.rstrip() + "\n")
    return exit_code


def run_git(args: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return result.stdout.strip()


def git_info(path: Path) -> dict[str, Any]:
    commit = run_git(["rev-parse", "--short", "HEAD"], path)
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], path)
    status = run_git(["status", "--porcelain"], path)
    return {
        "branch": branch,
        "commit": commit,
        "dirty": bool(status),
        "status_porcelain": status.splitlines() if status else [],
    }


def iter_project_files(root: Path) -> list[Path]:
    if not root.exists():
        return []

    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in TREE_EXCLUDED_DIRS for part in rel.parts):
            continue
        if path.is_dir():
            continue
        if path.name in TREE_EXCLUDED_FILES or path.suffix == ".pyc":
            continue
        files.append(rel)
    return files


def file_digest(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_fingerprint(root: Path) -> dict[str, Any] | None:
    if not root.exists():
        return None

    files = {
        str(rel): file_digest(root / rel)
        for rel in iter_project_files(root)
    }
    payload = json.dumps(files, sort_keys=True).encode("utf-8")
    return {
        "digest": hashlib.sha1(payload).hexdigest()[:12],
        "file_count": len(files),
    }


def tree_diff_summary(source: Path, destination: Path, limit: int = 25) -> dict[str, Any]:
    if not destination.exists():
        source_count = len(iter_project_files(source))
        return {
            "status": "missing",
            "missing": [],
            "extra": [],
            "modified": [],
            "total_differences": source_count,
            "truncated": False,
        }

    source_files = set(iter_project_files(source))
    destination_files = set(iter_project_files(destination))
    missing = sorted(str(item) for item in source_files - destination_files)
    extra = sorted(str(item) for item in destination_files - source_files)
    modified = sorted(
        str(item)
        for item in source_files & destination_files
        if file_digest(source / item) != file_digest(destination / item)
    )
    total = len(missing) + len(extra) + len(modified)

    return {
        "status": "drift" if total else "clean",
        "missing": missing[:limit],
        "extra": extra[:limit],
        "modified": modified[:limit],
        "truncated": total > limit,
        "total_differences": total,
    }


def source_root(explicit: str | None = None) -> Path:
    return Path(explicit).expanduser().resolve() if explicit else repo_root()


def assert_safe_install_destination(destination: Path) -> None:
    resolved = destination.expanduser().resolve()
    if resolved == Path("/") or resolved == Path.home().resolve():
        raise ValueError(f"Refusing to install into unsafe destination: {resolved}")
    if resolved.name != "superloop":
        raise ValueError(
            f"Refusing to install into {resolved}; destination directory must be named superloop."
        )


def sync_project_tree(source: Path, destination: Path) -> None:
    source = source.resolve()
    destination = destination.expanduser().resolve()
    assert_safe_install_destination(destination)

    if source == destination:
        return

    destination.mkdir(parents=True, exist_ok=True)
    source_files = set(iter_project_files(source))
    destination_files = set(iter_project_files(destination))

    for rel in sorted(destination_files - source_files, reverse=True):
        target = destination / rel
        if target.exists():
            target.unlink()

    for rel in sorted(source_files):
        src = source / rel
        dst = destination / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    for path in sorted(destination.rglob("*"), reverse=True):
        rel = path.relative_to(destination)
        if any(part in TREE_EXCLUDED_DIRS for part in rel.parts):
            continue
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def write_install_manifest(source: Path, destination: Path, host: str) -> None:
    manifest = {
        "host": host,
        "installed_at": now_iso(),
        "source_path": str(source),
        "source_git": git_info(source),
        "source_fingerprint": tree_fingerprint(source),
        "state_home": str(default_state_home(host)),
    }
    (destination / ".superloop-install.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )


FAILURE_RULES = [
    (
        "config-missing",
        ["missing", "not set", "required variable", "secret", "env", "environment variable"],
        "Provide the missing required configuration, secret, or environment variable, then rerun the blocked step.",
    ),
    (
        "auth-permission",
        ["permission", "denied", "unauthorized", "forbidden", "authentication", "token scope"],
        "Fix authentication, token scope, or repository/service permissions before retrying.",
    ),
    (
        "workflow-config",
        ["workflow", "yaml", "yml", "syntax", "invalid config"],
        "Fix the workflow or configuration syntax, then rerun the smallest affected check.",
    ),
    (
        "external-service",
        ["cloudflare", "vercel", "deploy", "dns", "api", "service unavailable"],
        "Check the external service state and credentials; pause if the next action requires an operator decision.",
    ),
    (
        "contract-boundary",
        ["contract", "scope", "ceo", "manual", "human", "approval"],
        "Pause and ask for a contract, scope, or operator decision before continuing.",
    ),
]


def classify_failure(text: str | None) -> dict[str, str] | None:
    if not text:
        return None
    lowered = text.lower()
    for code, tokens, action in FAILURE_RULES:
        if any(token in lowered for token in tokens):
            return {"code": code, "recommended_action": action}
    return {
        "code": "unknown",
        "recommended_action": "Capture the failing command and output, then classify whether it is code, configuration, environment, or operator-blocked.",
    }


def normalize_name_list(values: list[str]) -> list[str]:
    names: list[str] = []
    for value in values:
        names.extend(part.strip() for part in value.split(",") if part.strip())
    return names


def failure_signature(classification: dict[str, str] | None, blocked_by: str | None, round_gate: str) -> str | None:
    if not classification:
        return None
    signature_input = "|".join(
        [
            classification.get("code", "unknown"),
            (blocked_by or "").strip().lower(),
            round_gate.strip().lower(),
        ]
    )
    return hashlib.sha1(signature_input.encode("utf-8")).hexdigest()[:12]


def repeated_failure_count(rounds: list[dict[str, Any]], signature: str | None) -> int:
    if not signature:
        return 0
    return 1 + sum(1 for round_record in rounds if round_record.get("failure_signature") == signature)


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
    state_path = state_path_for(workspace_root, args.host)
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

    if state and not args.reset:
        state["contract"] = merge_contract(state.get("contract", {}), incoming_contract)
        state["guidance"]["expected_gap_checks"] = expected_gap_checks(
            state["contract"]["finish_standard"]
        )
        state["updated_at"] = timestamp
        state["stop_reason"] = None
        if state.get("status") == "completed":
            state["status"] = "active"
            state["last_verdict"] = "continue"
    else:
        contract = normalize_contract(incoming_contract)
        state = {
            "version": STATE_VERSION,
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

    save_state(state_path, state)
    return emit(
        {
            "artifacts": {
                "state_path": str(state_path),
                "workspace_root": str(workspace_root),
            },
            "budget_status": budget_snapshot(state),
            "host": host_profile(args.host),
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
    state_path = state_path_for(workspace_root, args.host)
    state = load_state(state_path)
    if not state:
        return emit(
            {
                "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
                "host": host_profile(args.host),
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
    next_actions = []
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

    summary = f"Loaded Superloop harness state for {workspace_root.name}."
    if changed:
        summary = f"Loaded Superloop harness state for {workspace_root.name}; budget is exhausted."

    return emit(
        {
            "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
            "budget_status": budget,
            "host": host_profile(args.host),
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
                "stop_reason": state.get("stop_reason"),
            },
            "status": "success",
            "summary": summary,
        }
    )


def record_command(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace_root(args.workspace)
    state_path = state_path_for(workspace_root, args.host)
    state = load_state(state_path)
    if not state:
        return emit(
            {
                "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
                "host": host_profile(args.host),
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
    failure_classification = None

    if gate_status == "gate-blocked" and not blocked_by:
        blocked_by = "Gate blocked by an unresolved dependency or contract boundary."
    if blocked_by and not resume_condition:
        resume_condition = "Remove the blocker or narrow the contract, then resume the recorded next round."
    if blocked_by or args.round_gate_result == "fail":
        failure_classification = classify_failure(
            " ".join(
                item
                for item in [blocked_by, args.round_gate, args.round_gate_result, args.change]
                if item
            )
        )
    failure_sig = failure_signature(failure_classification, blocked_by, args.round_gate)
    failure_repeat_count = repeated_failure_count(state.get("rounds", []), failure_sig)

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
        "failure_classification": failure_classification,
        "failure_repeat_count": failure_repeat_count,
        "failure_signature": failure_sig,
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
    if verdict == "continue":
        next_actions.append(f"Continue with the recorded next round: {next_round}")
    elif verdict == "pause":
        next_actions.append("Resolve the blocker or narrow the contract before resuming.")
        next_actions.append(f"Resume with the recorded next round: {next_round}")
    elif stop_reason == "budget-exhausted" and next_round:
        next_actions.append(f"Budget is exhausted; if you reopen the contract, resume with: {next_round}")
    else:
        next_actions.append("The harness allows a normal stop for this run.")
    if failure_repeat_count > 1:
        next_actions.append(
            f"This failure signature has appeared {failure_repeat_count} times; avoid another identical retry until the blocker changes."
        )

    return emit(
        {
            "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
            "budget_status": budget,
            "host": host_profile(args.host),
            "next_actions": next_actions,
            "state": {
                "blocked_by": blocked_by,
                "failure_classification": failure_classification,
                "failure_repeat_count": failure_repeat_count,
                "failure_signature": failure_sig,
                "next_round": next_round,
                "remaining_gap_ledger": remaining_gap_ledger,
                "resume_condition": resume_condition,
                "status": status,
                "stop_reason": stop_reason,
            },
            "status": "success",
            "summary": f"Recorded round {round_number}; harness verdict is `{verdict}`.",
            "verdict": verdict,
        }
    )


def render_report_markdown(
    state: dict[str, Any],
    workspace_root: Path,
    state_path: Path,
    host: dict[str, Any],
    tail: int | None = None,
) -> str:
    contract = state.get("contract", {})
    budget = budget_snapshot(state)
    rounds = state.get("rounds", [])
    if tail is not None:
        rounds = rounds[-tail:]

    def item(label: str, value: Any) -> str:
        if value in (None, "", []):
            value = "none"
        if isinstance(value, list):
            value = ", ".join(str(part) for part in value) or "none"
        return f"- {label}: {value}"

    lines = [
        "# Superloop Run Report",
        "",
        "## Current State",
        item("Workspace", workspace_root),
        item("Host", host["host"]),
        item("Status", state.get("status")),
        item("Last verdict", state.get("last_verdict")),
        item("Stop reason", state.get("stop_reason")),
        item("Next round", state.get("next_round")),
        item("Blocked by", state.get("blocked_by")),
        item("Resume condition", state.get("resume_condition")),
        "",
        "## Budget",
        item("Rounds used", budget["rounds_used"]),
        item("Rounds remaining", budget["rounds_remaining"]),
        item("Elapsed minutes", budget["elapsed_minutes"]),
        item("Timebox remaining minutes", budget["timebox_remaining_minutes"]),
        "",
        "## Mission Contract",
        item("Goal", contract.get("goal")),
        item("Workstream", contract.get("workstream")),
        item("Finish standard", contract.get("finish_standard")),
        item("Success signal", contract.get("success_signal")),
        item("Success direction", contract.get("success_direction")),
        item("Current gate", contract.get("current_gate")),
        item("Scope", contract.get("scope")),
        item("Constraints", contract.get("constraints")),
        item("Stop rule", contract.get("stop_rule")),
        "",
        "## Round Ledger",
    ]

    if not rounds:
        lines.append("- No rounds recorded yet.")
    else:
        for round_record in rounds:
            classification = round_record.get("failure_classification") or {}
            lines.extend(
                [
                    "",
                    f"### Round {round_record.get('round_number')}",
                    item("Recorded at", round_record.get("recorded_at")),
                    item("Hypothesis", round_record.get("hypothesis")),
                    item("Change", round_record.get("change")),
                    item("Round gate", round_record.get("round_gate")),
                    item("Gate result", round_record.get("round_gate_result")),
                    item("Gate status", round_record.get("gate_status")),
                    item("Verdict", round_record.get("verdict")),
                    item("Remaining gaps", round_record.get("remaining_gap_ledger")),
                    item("Failure class", classification.get("code")),
                    item("Failure signature", round_record.get("failure_signature")),
                    item("Failure repeat count", round_record.get("failure_repeat_count")),
                    item("Recommended action", classification.get("recommended_action")),
                    item("Next round", round_record.get("next_round")),
                ]
            )

    lines.extend(
        [
            "",
            "## Artifacts",
            item("State path", state_path),
            item("Installed path", host.get("installed_path")),
            item("Harness path", host.get("harness_path")),
        ]
    )
    return "\n".join(lines)


def report_command(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace_root(args.workspace)
    state_path = state_path_for(workspace_root, args.host)
    state = load_state(state_path)
    host = host_profile(args.host)
    if not state:
        payload = {
            "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
            "host": host,
            "status": "warning",
            "summary": f"No Superloop harness state exists for {workspace_root.name}.",
        }
        if args.format == "json":
            return emit(payload)
        return emit_markdown(
            f"# Superloop Run Report\n\nNo Superloop harness state exists for `{workspace_root}`.\n\nState path: `{state_path}`"
        )

    changed = maybe_close_for_budget(state)
    if changed:
        save_state(state_path, state)

    if args.format == "json":
        return emit(
            {
                "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
                "budget_status": budget_snapshot(state),
                "host": host,
                "state": state,
                "status": "success",
                "summary": f"Rendered Superloop report for {workspace_root.name}.",
            }
        )

    return emit_markdown(render_report_markdown(state, workspace_root, state_path, host, args.tail))


def doctor_command(args: argparse.Namespace) -> int:
    host = host_profile(args.host)
    source = source_root(args.source)
    installed = Path(host["installed_path"]).expanduser()
    current = repo_root()
    same_tree = source.resolve() == installed.resolve() if installed.exists() else False
    diff = (
        {"status": "self", "missing": [], "extra": [], "modified": [], "total_differences": 0}
        if same_tree
        else tree_diff_summary(source, installed)
    )
    install_command = (
        f"{source / 'scripts' / 'install.sh'} --host {host['host']} --source {source}"
    )
    exit_code = 0
    status = "success"
    next_actions: list[str] = []

    if diff["status"] == "missing":
        status = "warning"
        next_actions.append(f"Install Superloop for {host['host']}: {install_command}")
    elif diff["status"] == "drift":
        status = "warning"
        next_actions.append(f"Sync the installed copy: {install_command}")
    else:
        next_actions.append("The selected host installation is in sync with the source tree.")

    if args.check and status != "success":
        exit_code = 1

    return emit(
        {
            "current_source_path": str(current),
            "diff": diff,
            "fingerprints": {
                "installed": tree_fingerprint(installed),
                "source": tree_fingerprint(source),
            },
            "git": {"source": git_info(source) if (source / ".git").exists() else None},
            "host": host,
            "next_actions": next_actions,
            "source_path": str(source),
            "status": status,
            "summary": f"Superloop doctor checked {host['host']} installation.",
        },
        exit_code=exit_code,
    )


def install_command(args: argparse.Namespace) -> int:
    host = host_profile(args.host)
    source = source_root(args.source)
    destination = Path(host["installed_path"]).expanduser()
    diff_before = tree_diff_summary(source, destination)

    if args.check:
        status = "success" if diff_before["status"] in {"clean", "self"} else "warning"
        return emit(
            {
                "diff": diff_before,
                "host": host,
                "source_path": str(source),
                "status": status,
                "summary": f"Superloop install check for {host['host']} is {diff_before['status']}.",
            },
            exit_code=0 if status == "success" else 1,
        )

    sync_project_tree(source, destination)
    write_install_manifest(source, destination, host["host"])
    diff_after = tree_diff_summary(source, destination)
    status = "success" if diff_after["status"] == "clean" else "warning"

    return emit(
        {
            "diff": {"before": diff_before, "after": diff_after},
            "host": host,
            "source_path": str(source),
            "status": status,
            "summary": f"Installed Superloop for {host['host']} at {destination}.",
        },
        exit_code=0 if status == "success" else 1,
    )


def preflight_command(args: argparse.Namespace) -> int:
    required_env = normalize_name_list(args.require_env)
    optional_env = normalize_name_list(args.optional_env)
    missing_required = [name for name in required_env if not os.environ.get(name)]
    missing_optional = [name for name in optional_env if not os.environ.get(name)]
    failure = (
        classify_failure("missing required environment variable " + ", ".join(missing_required))
        if missing_required
        else None
    )
    status = "error" if missing_required else "success"
    next_actions = []
    if missing_required:
        next_actions.append(
            "Set required environment variables before continuing: "
            + ", ".join(missing_required)
        )
    if missing_optional:
        next_actions.append(
            "Optional environment variables are unset: " + ", ".join(missing_optional)
        )
    if not next_actions:
        next_actions.append("Preflight passed; continue with the next round.")

    return emit(
        {
            "failure_classification": failure,
            "host": host_profile(args.host),
            "missing_optional_env": missing_optional,
            "missing_required_env": missing_required,
            "next_actions": next_actions,
            "required_env": required_env,
            "optional_env": optional_env,
            "status": status,
            "summary": "Superloop preflight checked required and optional environment variables.",
        },
        exit_code=1 if missing_required else 0,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Harness for the Superloop skill.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize or refresh a Superloop run.")
    init_parser.add_argument("--workspace")
    init_parser.add_argument("--host", default="auto", type=normalize_host)
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
    init_parser.add_argument("--reset", action="store_true")
    init_parser.set_defaults(func=init_command)

    resume_parser = subparsers.add_parser("resume", help="Load the current Superloop run.")
    resume_parser.add_argument("--workspace")
    resume_parser.add_argument("--host", default="auto", type=normalize_host)
    resume_parser.set_defaults(func=resume_command)

    record_parser = subparsers.add_parser(
        "record", help="Persist the latest Superloop round and compute the loop verdict."
    )
    record_parser.add_argument("--workspace")
    record_parser.add_argument("--host", default="auto", type=normalize_host)
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
    record_parser.add_argument("--resume-condition")
    record_parser.add_argument("--cannot-continue", action="store_true")
    record_parser.add_argument("--would-exceed-contract", action="store_true")
    record_parser.set_defaults(func=record_command)

    timeline_parser = subparsers.add_parser(
        "timeline", help="Render a human-readable Superloop run timeline."
    )
    timeline_parser.add_argument("--workspace")
    timeline_parser.add_argument("--host", default="auto", type=normalize_host)
    timeline_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    timeline_parser.add_argument("--tail", type=positive_int)
    timeline_parser.set_defaults(func=report_command)

    report_parser = subparsers.add_parser(
        "report", help="Render a Superloop run report. Alias-friendly companion to timeline."
    )
    report_parser.add_argument("--workspace")
    report_parser.add_argument("--host", default="auto", type=normalize_host)
    report_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    report_parser.add_argument("--tail", type=positive_int)
    report_parser.set_defaults(func=report_command)

    doctor_parser = subparsers.add_parser(
        "doctor", help="Check host adapter paths, state location, and install drift."
    )
    doctor_parser.add_argument("--host", default="auto", type=normalize_host)
    doctor_parser.add_argument("--source")
    doctor_parser.add_argument("--check", action="store_true")
    doctor_parser.set_defaults(func=doctor_command)

    install_parser = subparsers.add_parser(
        "install", help="Install or sync Superloop into a host-specific skill directory."
    )
    install_parser.add_argument("--host", default="auto", type=normalize_host)
    install_parser.add_argument("--source")
    install_parser.add_argument("--check", action="store_true")
    install_parser.set_defaults(func=install_command)

    preflight_parser = subparsers.add_parser(
        "preflight", help="Run generic preflight checks before spending a Superloop round."
    )
    preflight_parser.add_argument("--host", default="auto", type=normalize_host)
    preflight_parser.add_argument("--require-env", action="append", default=[])
    preflight_parser.add_argument("--optional-env", action="append", default=[])
    preflight_parser.set_defaults(func=preflight_command)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
