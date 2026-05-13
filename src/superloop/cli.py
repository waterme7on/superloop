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
import uuid
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
STATUS_CLASSES = FAILURE_CLASSES | {"ready", "active-run", "continue", "pause", "stop"}
LOCALE_CHOICES = {"en", "zh"}
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
COMPLETION_AUDIT_CHECKLIST = [
    "Derive concrete requirements from the mission, current gate, and remaining gap ledger.",
    "Inspect authoritative current state before relying on earlier chat or intent.",
    "Verify every explicit requirement with files, command output, tests, runtime behavior, or external state.",
    "Treat missing or indirect evidence as incomplete rather than complete.",
    "Mark the mission complete only when the evidence proves no required work remains.",
]
CONTEXT_DIRECTIVES = [
    "Continue the stored Superloop mission; do not shrink the objective to fit this turn.",
    "Use the current workspace and external systems as authoritative evidence.",
    "Keep the current round focused on the next recorded gate or active in-flight round.",
    "Record the round before deciding whether to continue, pause, or stop.",
    "Do not claim mission completion without explicit completion evidence.",
]


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
    path = Path(__file__).resolve()
    for parent in path.parents:
        if (parent / "SKILL.md").exists() and (parent / "scripts").is_dir():
            return parent
    return path.parents[2]


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


def state_home(host_arg: str | None = None) -> Path:
    return default_state_home(detect_host(host_arg))


def history_dir_for(workspace_root: Path, host_arg: str | None = None) -> Path:
    return state_home(host_arg) / "history" / workspace_key(workspace_root)


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


def normalize_completion_evidence(value: Any) -> list[str]:
    if value is None:
        return []

    raw_items = value if isinstance(value, list) else [value]
    evidence: list[str] = []
    for item in raw_items:
        text = str(item).strip()
        if text:
            evidence.append(text)
    return evidence


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


def normalize_status_class(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    return normalized if normalized in STATUS_CLASSES else "unknown"


def normalize_locale(value: str | None) -> str:
    locale = (value or os.environ.get("SUPERLOOP_LOCALE") or "en").strip().lower()
    if locale.startswith("zh"):
        return "zh"
    if locale.startswith("en"):
        return "en"
    raise argparse.ArgumentTypeError("locale must be `en` or `zh`")


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
    record["completion_evidence"] = normalize_completion_evidence(record.get("completion_evidence"))
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
    state["active_round"] = state.get("active_round")
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
        "config-missing-required",
        ["missing", "not set", "required variable", "secret", "env", "environment variable"],
        "Provide the missing required configuration, secret, or environment variable, then rerun the blocked step.",
    ),
    (
        "permissions",
        ["permission", "denied", "unauthorized", "forbidden", "authentication", "token scope"],
        "Fix authentication, token scope, or repository/service permissions before retrying.",
    ),
    (
        "workflow-syntax",
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


def failure_signature(failure_class: str | None, blocked_by: str | None, round_gate: str) -> str | None:
    if not failure_class:
        return None
    signature_input = "|".join(
        [
            failure_class,
            (blocked_by or "").strip().lower(),
            round_gate.strip().lower(),
        ]
    )
    return hashlib.sha1(signature_input.encode("utf-8")).hexdigest()[:12]


def repeated_failure_signature_count(rounds: list[dict[str, Any]], signature: str | None) -> int:
    if not signature:
        return 0
    return 1 + sum(1 for round_record in rounds if round_record.get("failure_signature") == signature)


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
        "active_round": None,
        "rounds": [],
        "next_round": None,
        "blocked_by": None,
        "resume_condition": None,
    }


def archive_state(
    workspace_root: Path,
    state: dict[str, Any],
    *,
    reason: str,
    host_arg: str | None = None,
) -> Path:
    run_id = state.get("run_id") or f"legacy-{workspace_key(workspace_root)}"
    archive_dir = history_dir_for(workspace_root, host_arg)
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
    blockers: list[str] | None = None,
    can_continue: bool | None = None,
    locale: str = "en",
    platform: dict[str, Any] | None = None,
    recommended_actions: list[str] | None = None,
    repeated_failure_count: int | None = None,
) -> dict[str, Any]:
    action_list = recommended_actions or [recommended_action]
    card = {
        "classification": classification,
        "locale": locale,
        "recommended_action": recommended_action,
        "recommended_actions": action_list,
        "stage": stage,
    }
    blocking_items = blockers or ([blocker] if blocker else [])
    if blocking_items:
        card["blocking_item"] = blocker or ", ".join(blocking_items)
        card["blocking_items"] = blocking_items
    if can_continue is not None:
        card["can_continue"] = can_continue
    if platform:
        card["platform"] = platform
    if repeated_failure_count and repeated_failure_count > 1:
        card["repeated_failure_count"] = repeated_failure_count
    return card


ACTION_MESSAGES = {
    "ready": {
        "en": "Continue to the planned stage.",
        "zh": "继续执行当前计划阶段。",
    },
    "config-missing-required": {
        "en": "Set the required configuration, then rerun preflight before retrying this stage.",
        "zh": "补齐必需配置，然后重新运行 preflight 再重试该阶段。",
    },
    "config-missing-optional": {
        "en": "Review the optional configuration warning; continue only if this stage truly treats it as optional.",
        "zh": "确认可选配置告警；只有该阶段确实不依赖它时才继续。",
    },
    "permissions": {
        "en": "Fix authentication, token scope, or service permissions before retrying.",
        "zh": "先修复登录、token scope 或服务权限，再重试。",
    },
    "workflow-syntax": {
        "en": "Fix the workflow or config syntax, then rerun the smallest affected check.",
        "zh": "先修复 workflow 或配置语法，再重跑最小受影响检查。",
    },
    "external-service": {
        "en": "Check the external service state and credentials; pause if the next action requires an operator decision.",
        "zh": "检查外部服务状态和凭证；如果下一步需要操作者决策，先暂停。",
    },
    "environment": {
        "en": "Fix the local or CI environment before continuing the loop.",
        "zh": "先修复本地或 CI 环境，再继续循环。",
    },
    "contract-boundary": {
        "en": "Pause and request a scope, budget, or operator decision before continuing.",
        "zh": "先暂停并确认范围、预算或操作者决策，再继续。",
    },
    "code-regression": {
        "en": "Treat this as a code regression: inspect the failing diff, add a focused check, and rerun it.",
        "zh": "按代码回归处理：检查失败 diff，补一个聚焦验证，再重跑。",
    },
    "unknown": {
        "en": "Capture the failing command and output, then classify it before retrying.",
        "zh": "先记录失败命令和输出，完成分类后再重试。",
    },
}

STATUS_LABELS = {
    "en": {
        "blocked_by": "Blocked by",
        "can_continue": "Can continue",
        "classification": "Classification",
        "disabled": "Disabled platform refs",
        "migration": "Migration",
        "platform": "Platform",
        "recommended_actions": "Recommended actions",
        "repeat": "Repeated failure count",
        "stage": "Stage",
        "title": "Superloop Status Card",
    },
    "zh": {
        "blocked_by": "阻塞项",
        "can_continue": "是否可继续",
        "classification": "分类",
        "disabled": "已禁用平台引用",
        "migration": "迁移",
        "platform": "平台",
        "recommended_actions": "建议动作",
        "repeat": "重复失败次数",
        "stage": "阶段",
        "title": "Superloop 状态卡片",
    },
}


def default_status_action(classification: str, blockers: list[str], locale: str) -> str:
    message = ACTION_MESSAGES.get(classification, ACTION_MESSAGES["unknown"])[locale]
    if blockers and classification in {"config-missing-required", "config-missing-optional"}:
        return f"{message} ({', '.join(blockers)})"
    return message


def status_can_continue(classification: str) -> bool:
    return classification in {
        "ready",
        "config-missing-optional",
        "mission-complete",
        "stop",
    }


def build_platform_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    disabled = normalize_name_list(args.disabled_platform)
    current = args.platform or args.migration_to or os.environ.get("SUPERLOOP_PLATFORM") or "generic"
    snapshot: dict[str, Any] = {"current": current}
    if args.migration_from:
        snapshot["migration_from"] = args.migration_from
    if args.migration_to:
        snapshot["migration_to"] = args.migration_to
    if disabled:
        snapshot["disabled"] = disabled
    return snapshot


def render_status_card_markdown(card: dict[str, Any]) -> str:
    locale = normalize_locale(card.get("locale"))
    labels = STATUS_LABELS[locale]

    def value(item: Any) -> str:
        if item in (None, "", []):
            return "none"
        if isinstance(item, bool):
            return "yes" if item else "no"
        if isinstance(item, list):
            return ", ".join(str(part) for part in item) or "none"
        return str(item)

    platform = card.get("platform") or {}
    lines = [
        f"## {labels['title']}",
        "",
        f"- {labels['stage']}: `{value(card.get('stage'))}`",
        f"- {labels['classification']}: `{value(card.get('classification'))}`",
    ]
    if card.get("blocking_items"):
        lines.append(f"- {labels['blocked_by']}: {value(card.get('blocking_items'))}")
    lines.append(f"- {labels['can_continue']}: {value(card.get('can_continue'))}")
    if card.get("repeated_failure_count"):
        lines.append(f"- {labels['repeat']}: {card['repeated_failure_count']}")
    if platform:
        lines.append(f"- {labels['platform']}: `{value(platform.get('current'))}`")
        if platform.get("migration_from") or platform.get("migration_to"):
            migration = f"{value(platform.get('migration_from'))} -> {value(platform.get('migration_to'))}"
            lines.append(f"- {labels['migration']}: `{migration}`")
        if platform.get("disabled"):
            lines.append(f"- {labels['disabled']}: {value(platform.get('disabled'))}")
    lines.append("")
    lines.append(f"### {labels['recommended_actions']}")
    for action in card.get("recommended_actions", []):
        lines.append(f"- {action}")
    return "\n".join(lines)


def sync_github_comments(
    *,
    workspace_root: Path,
    repo: str | None,
    issue: int | None,
    pr: int | None,
    body: str,
    dry_run: bool,
) -> list[dict[str, Any]]:
    targets: list[tuple[str, int]] = []
    if issue is not None:
        targets.append(("issue", issue))
    if pr is not None:
        targets.append(("pr", pr))

    results: list[dict[str, Any]] = []
    for kind, number in targets:
        if dry_run:
            results.append({"number": number, "status": "dry-run", "target": kind})
            continue
        if not shutil.which("gh"):
            results.append(
                {
                    "error": "GitHub CLI `gh` was not found on PATH.",
                    "number": number,
                    "status": "error",
                    "target": kind,
                }
            )
            continue

        command = ["gh", kind, "comment", str(number), "--body", body]
        if repo:
            command.extend(["--repo", repo])
        result = subprocess.run(
            command,
            cwd=workspace_root,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            results.append({"number": number, "status": "posted", "target": kind})
        else:
            results.append(
                {
                    "error": result.stderr.strip() or result.stdout.strip(),
                    "number": number,
                    "status": "error",
                    "target": kind,
                }
            )
    return results


def status_card_command(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace_root(args.workspace)
    locale = normalize_locale(args.locale)
    required_env = normalize_env_keys(args.require_env)
    optional_env = normalize_env_keys(args.optional_env)
    missing_required_env = [name for name in required_env if not os.environ.get(name)]
    missing_optional_env = [name for name in optional_env if not os.environ.get(name)]
    blockers = normalize_name_list(args.blocked_by)
    blockers.extend(missing_required_env)

    classification = normalize_status_class(args.classification or args.failure_class)
    failure_hint = classify_failure(args.failure_text)
    inferred_action = None
    if not classification and failure_hint:
        classification = normalize_status_class(failure_hint["code"])
        inferred_action = failure_hint["recommended_action"]
    if not classification:
        if missing_required_env:
            classification = "config-missing-required"
        elif missing_optional_env:
            classification = "config-missing-optional"
        else:
            classification = "ready"

    if classification == "config-missing-optional" and not blockers:
        blockers.extend(missing_optional_env)

    recommended_actions = args.recommended_action or []
    if not recommended_actions:
        recommended_actions.append(inferred_action or default_status_action(classification, blockers, locale))
    if args.migration_from or args.migration_to:
        target = args.migration_to or args.platform or "generic"
        source = args.migration_from or "previous"
        if locale == "zh":
            recommended_actions.append(f"迁移模式：当前目标平台是 {target}；确认 {source} 的残留配置只作为禁用或兼容引用出现。")
        else:
            recommended_actions.append(
                f"Migration mode: target platform is {target}; keep {source} references disabled or compatibility-only."
            )
    if args.repeat_count and args.repeat_count > 1:
        if locale == "zh":
            recommended_actions.append("重复失败已聚合；在阻塞项变化前不要继续相同重试。")
        else:
            recommended_actions.append("Repeated failure is aggregated; do not retry the identical path until the blocker changes.")

    card = build_status_card(
        stage=args.stage,
        classification=classification,
        recommended_action=recommended_actions[0],
        blockers=blockers,
        can_continue=status_can_continue(classification),
        locale=locale,
        platform=build_platform_snapshot(args),
        recommended_actions=recommended_actions,
        repeated_failure_count=args.repeat_count,
    )
    markdown = render_status_card_markdown(card)
    github_repo = args.github_repo or os.environ.get("GITHUB_REPOSITORY")
    github_issue = args.github_issue or optional_int(os.environ.get("SUPERLOOP_GITHUB_ISSUE"))
    github_pr = args.github_pr or optional_int(os.environ.get("SUPERLOOP_GITHUB_PR"))
    github_sync = sync_github_comments(
        workspace_root=workspace_root,
        repo=github_repo,
        issue=github_issue,
        pr=github_pr,
        body=markdown,
        dry_run=args.dry_run,
    )
    sync_failed = any(item["status"] == "error" for item in github_sync)

    if args.format == "markdown":
        return emit_markdown(markdown, exit_code=1 if sync_failed else 0)

    return emit(
        {
            "artifacts": {"workspace_root": str(workspace_root)},
            "github_sync": github_sync,
            "host": host_profile(args.host),
            "next_actions": recommended_actions,
            "status": "error" if sync_failed else "success",
            "status_card": card,
            "status_card_markdown": markdown,
            "summary": f"Rendered Superloop status card for {args.stage}.",
        },
        exit_code=1 if sync_failed else 0,
    )


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


def build_runtime_context(
    state: dict[str, Any],
    workspace_root: Path,
    state_path: Path,
    host: dict[str, Any],
) -> dict[str, Any]:
    contract = state.get("contract", {})
    budget = budget_snapshot(state)
    return {
        "active_round": state.get("active_round"),
        "artifacts": {
            "harness_path": host.get("harness_path"),
            "state_path": str(state_path),
            "workspace_root": str(workspace_root),
        },
        "budget_status": budget,
        "completion_audit_checklist": COMPLETION_AUDIT_CHECKLIST,
        "contract": contract,
        "directives": CONTEXT_DIRECTIVES,
        "expected_gap_checks": state.get("guidance", {}).get("expected_gap_checks", []),
        "last_round": state.get("rounds", [])[-1] if state.get("rounds") else None,
        "last_verdict": state.get("last_verdict"),
        "next_round": state.get("next_round"),
        "remaining_gap_ledger": state.get("remaining_gap_ledger", []),
        "resume_condition": state.get("resume_condition"),
        "run_id": state.get("run_id"),
        "status": state.get("status"),
        "stop_reason": state.get("stop_reason"),
    }


def render_runtime_context_markdown(context: dict[str, Any]) -> str:
    contract = context.get("contract", {})
    budget = context.get("budget_status", {})
    active_round = context.get("active_round")

    def value(item: Any) -> str:
        if item in (None, "", []):
            return "none"
        if isinstance(item, list):
            return ", ".join(str(part) for part in item) or "none"
        return str(item)

    lines = [
        "# Superloop Runtime Context",
        "",
        "Use this as the next-round steering prompt. It is generated from persisted harness state, not chat memory.",
        "",
        "## Mission",
        f"- Goal: {value(contract.get('goal'))}",
        f"- Workstream: {value(contract.get('workstream'))}",
        f"- Finish standard: {value(contract.get('finish_standard'))}",
        f"- Success signal: {value(contract.get('success_signal'))}",
        f"- Current gate: {value(contract.get('current_gate'))}",
        f"- Stop rule: {value(contract.get('stop_rule'))}",
        "",
        "## Budget",
        f"- Rounds used: {value(budget.get('rounds_used'))}",
        f"- Rounds remaining: {value(budget.get('rounds_remaining'))}",
        f"- Elapsed minutes: {value(budget.get('elapsed_minutes'))}",
        f"- Timebox remaining minutes: {value(budget.get('timebox_remaining_minutes'))}",
        "",
        "## Next Execution Focus",
        f"- Status: {value(context.get('status'))}",
        f"- Last verdict: {value(context.get('last_verdict'))}",
        f"- Next round: {value(context.get('next_round'))}",
        f"- Resume condition: {value(context.get('resume_condition'))}",
    ]
    if active_round:
        lines.extend(
            [
                "",
                "## Active Round",
                f"- Round number: {value(active_round.get('round_number'))}",
                f"- Started at: {value(active_round.get('started_at'))}",
                f"- Hypothesis: {value(active_round.get('hypothesis'))}",
                f"- Change: {value(active_round.get('change'))}",
                f"- Round gate: {value(active_round.get('round_gate'))}",
                "",
                "Resolve this active round with `record` before starting another round.",
            ]
        )

    lines.extend(
        [
            "",
            "## Remaining Gaps",
        ]
    )
    gaps = context.get("remaining_gap_ledger") or []
    if gaps:
        lines.extend(f"- {gap}" for gap in gaps)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Completion Audit",
        ]
    )
    lines.extend(f"- {item}" for item in context.get("completion_audit_checklist", []))
    lines.extend(
        [
            "",
            "## Directives",
        ]
    )
    lines.extend(f"- {item}" for item in context.get("directives", []))
    lines.extend(
        [
            "",
            "## Artifacts",
            f"- State path: {value(context.get('artifacts', {}).get('state_path'))}",
            f"- Harness path: {value(context.get('artifacts', {}).get('harness_path'))}",
        ]
    )
    return "\n".join(lines)


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
            archive_path = archive_state(workspace_root, state, reason=archive_reason, host_arg=args.host)
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
            "host": host_profile(args.host),
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
    elif state.get("active_round"):
        next_actions.append("Resolve the active round with `record` before starting another round.")
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
            "host": host_profile(args.host),
            "freshness": freshness,
            "next_actions": next_actions,
            "state": {
                "active_round": state.get("active_round"),
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


def context_command(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace_root(args.workspace)
    state_path = state_path_for(workspace_root, args.host)
    state = load_state(state_path)
    host = host_profile(args.host)
    if not state:
        payload = {
            "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
            "host": host,
            "next_actions": ["Initialize a run with `init` before asking for runtime context."],
            "status": "warning",
            "summary": f"No Superloop harness state exists for {workspace_root.name}.",
        }
        if args.format == "json":
            return emit(payload)
        return emit_markdown(
            f"# Superloop Runtime Context\n\nNo Superloop harness state exists for `{workspace_root}`.\n\nState path: `{state_path}`"
        )

    changed = maybe_close_for_budget(state)
    if changed:
        save_state(state_path, state)

    context = build_runtime_context(state, workspace_root, state_path, host)
    if args.format == "json":
        return emit(
            {
                "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
                "context": context,
                "host": host,
                "status": "success",
                "summary": f"Rendered Superloop runtime context for {workspace_root.name}.",
            }
        )

    return emit_markdown(render_runtime_context_markdown(context))


def start_round_command(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace_root(args.workspace)
    state_path = state_path_for(workspace_root, args.host)
    state = load_state(state_path)
    if not state:
        return emit(
            {
                "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
                "host": host_profile(args.host),
                "next_actions": ["Run `init` before starting a round."],
                "status": "error",
                "summary": "Cannot start a round without an initialized Superloop harness state.",
            },
            exit_code=1,
        )

    if state.get("active_round") and not args.replace:
        return emit(
            {
                "active_round": state["active_round"],
                "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
                "host": host_profile(args.host),
                "next_actions": [
                    "Record the active round before starting another one, or rerun `start-round --replace` if the active round is stale."
                ],
                "status": "error",
                "summary": "A Superloop round is already active.",
            },
            exit_code=1,
        )

    if state.get("status") != "active":
        return emit(
            {
                "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
                "host": host_profile(args.host),
                "next_actions": [
                    "Resume or reinitialize the run before starting a new implementation round."
                ],
                "status": "error",
                "summary": f"Cannot start a round while run status is `{state.get('status')}`.",
            },
            exit_code=1,
        )

    active_round = {
        "change": args.change,
        "current_gate": args.current_gate or state.get("contract", {}).get("current_gate"),
        "hypothesis": args.hypothesis,
        "round_gate": args.round_gate,
        "round_number": len(state.get("rounds", [])) + 1,
        "started_at": now_iso(),
    }
    state["active_round"] = active_round
    state["updated_at"] = now_iso()
    save_state(state_path, state)

    return emit(
        {
            "active_round": active_round,
            "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
            "host": host_profile(args.host),
            "next_actions": [
                "Execute the focused round, verify it mechanically, then call `record` to close the active round."
            ],
            "status": "success",
            "summary": f"Started Superloop round {active_round['round_number']}.",
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
        state_home(args.host).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        state_home_error = f"Cannot prepare state home `{state_home(args.host)}`: {exc}"

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
                "state_home": str(state_home(args.host)),
                "workspace_root": str(workspace_root),
            },
            "host": host_profile(args.host),
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

    active_round = state.get("active_round") or {}
    hypothesis = args.hypothesis or active_round.get("hypothesis")
    change = args.change or active_round.get("change")
    round_gate = args.round_gate or active_round.get("round_gate")
    missing_record_fields = [
        name
        for name, value in [
            ("--hypothesis", hypothesis),
            ("--change", change),
            ("--round-gate", round_gate),
        ]
        if not value
    ]
    if missing_record_fields:
        return emit(
            {
                "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
                "host": host_profile(args.host),
                "next_actions": [
                    f"Provide {', '.join(missing_record_fields)} or start the round with `start-round` before recording it."
                ],
                "status": "error",
                "summary": "Cannot record a round without round identity fields.",
            },
            exit_code=1,
        )

    if args.round_gate_result not in ROUND_GATE_RESULTS:
        raise ValueError(f"Unexpected round gate result: {args.round_gate_result}")

    gate_status = LEGACY_GATE_STATUSES.get(args.gate_status, args.gate_status)
    if gate_status not in GATE_STATUSES:
        raise ValueError(f"Unexpected gate status: {args.gate_status}")

    remaining_gap_ledger = normalize_remaining_gaps(args.remaining_gap)
    if not args.remaining_gap:
        remaining_gap_ledger = normalize_remaining_gaps(state.get("remaining_gap_ledger", []))
    completion_evidence = normalize_completion_evidence(args.completion_evidence)
    blocked_by = args.blocked_by
    resume_condition = args.resume_condition

    if gate_status == "gate-blocked" and not blocked_by:
        blocked_by = "Gate blocked by an unresolved dependency or contract boundary."
    if blocked_by and not resume_condition:
        resume_condition = "Remove the blocker or narrow the contract, then resume the recorded next round."

    can_continue = not args.cannot_continue and not args.would_exceed_contract and not blocked_by
    mission_complete = args.mission_complete
    if mission_complete and not completion_evidence:
        return emit(
            {
                "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
                "completion_audit_checklist": COMPLETION_AUDIT_CHECKLIST,
                "host": host_profile(args.host),
                "next_actions": [
                    "Provide at least one `--completion-evidence` item before recording a mission-complete round."
                ],
                "status": "error",
                "summary": "Mission completion requires explicit completion evidence.",
            },
            exit_code=1,
        )
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
    failure_sig = failure_signature(failure_class, blocked_by, round_gate)
    failure_signature_repeats = repeated_failure_signature_count(state.get("rounds", []), failure_sig)
    round_number = len(state.get("rounds", [])) + 1
    round_record = {
        "round_number": round_number,
        "recorded_at": now_iso(),
        "hypothesis": hypothesis,
        "change": change,
        "round_gate": round_gate,
        "round_gate_result": args.round_gate_result,
        "gate_status": gate_status,
        "next_round": next_round,
        "remaining_gap_ledger": remaining_gap_ledger,
        "completion_evidence": completion_evidence,
        "mission_complete": mission_complete,
        "stop_rule_satisfied": args.stop_rule_satisfied,
        "blocked_by": blocked_by,
        "failure_class": failure_class,
        "failure_repeat_count": failure_signature_repeats,
        "failure_signature": failure_sig,
        "resume_condition": resume_condition,
        "would_exceed_contract": args.would_exceed_contract,
        "cannot_continue": args.cannot_continue,
        "verdict": verdict,
        "stop_reason": stop_reason,
    }

    state["rounds"].append(round_record)
    state["active_round"] = None
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
    if failure_signature_repeats > 1:
        next_actions.append(
            f"This failure signature has appeared {failure_signature_repeats} times; avoid another identical retry until the blocker changes."
        )

    return emit(
        {
            "artifacts": {"state_path": str(state_path), "workspace_root": str(workspace_root)},
            "budget_status": budget,
            "host": host_profile(args.host),
            "next_actions": next_actions,
            "state": {
                "active_round": state.get("active_round"),
                "blocked_by": blocked_by,
                "completion_evidence": completion_evidence,
                "failure_class": failure_class,
                "failure_repeat_count": failure_signature_repeats,
                "failure_signature": failure_sig,
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
        item("Active round", state.get("active_round")),
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
            failure_class = round_record.get("failure_class")
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
                    item("Completion evidence", round_record.get("completion_evidence")),
                    item("Failure class", failure_class),
                    item("Failure signature", round_record.get("failure_signature")),
                    item("Failure repeat count", round_record.get("failure_repeat_count")),
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
    init_parser.add_argument("--continue-existing", action="store_true")
    init_parser.add_argument("--reset", action="store_true")
    init_parser.set_defaults(func=init_command)

    preflight_parser = subparsers.add_parser(
        "preflight",
        help="Check workspace and environment prerequisites before a risky stage.",
    )
    preflight_parser.add_argument("--workspace")
    preflight_parser.add_argument("--host", default="auto", type=normalize_host)
    preflight_parser.add_argument("--stage", default="preflight")
    preflight_parser.add_argument("--require-env", action="append", default=[])
    preflight_parser.add_argument("--optional-env", action="append", default=[])
    preflight_parser.set_defaults(func=preflight_command)

    status_card_parser = subparsers.add_parser(
        "status-card",
        help="Render a deployment or workflow status card and optionally sync it to GitHub.",
    )
    status_card_parser.add_argument("--workspace")
    status_card_parser.add_argument("--host", default="auto", type=normalize_host)
    status_card_parser.add_argument("--stage", default="status")
    status_card_parser.add_argument("--classification", choices=sorted(STATUS_CLASSES))
    status_card_parser.add_argument("--failure-class", choices=sorted(FAILURE_CLASSES))
    status_card_parser.add_argument("--failure-text")
    status_card_parser.add_argument("--blocked-by", action="append", default=[])
    status_card_parser.add_argument("--require-env", action="append", default=[])
    status_card_parser.add_argument("--optional-env", action="append", default=[])
    status_card_parser.add_argument("--recommended-action", action="append", default=[])
    status_card_parser.add_argument("--repeat-count", type=positive_int)
    status_card_parser.add_argument("--platform")
    status_card_parser.add_argument("--migration-from")
    status_card_parser.add_argument("--migration-to")
    status_card_parser.add_argument("--disabled-platform", action="append", default=[])
    status_card_parser.add_argument("--locale", default=os.environ.get("SUPERLOOP_LOCALE", "en"))
    status_card_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    status_card_parser.add_argument("--github-repo")
    status_card_parser.add_argument("--github-issue", type=positive_int)
    status_card_parser.add_argument("--github-pr", type=positive_int)
    status_card_parser.add_argument("--dry-run", action="store_true")
    status_card_parser.set_defaults(func=status_card_command)

    resume_parser = subparsers.add_parser("resume", help="Load the current Superloop run.")
    resume_parser.add_argument("--workspace")
    resume_parser.add_argument("--host", default="auto", type=normalize_host)
    resume_parser.set_defaults(func=resume_command)

    context_parser = subparsers.add_parser(
        "context",
        aliases=["next-prompt"],
        help="Render next-round runtime context from persisted Superloop state.",
    )
    context_parser.add_argument("--workspace")
    context_parser.add_argument("--host", default="auto", type=normalize_host)
    context_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    context_parser.set_defaults(func=context_command)

    start_round_parser = subparsers.add_parser(
        "start-round",
        help="Persist the in-flight round before executing it.",
    )
    start_round_parser.add_argument("--workspace")
    start_round_parser.add_argument("--host", default="auto", type=normalize_host)
    start_round_parser.add_argument("--hypothesis", required=True)
    start_round_parser.add_argument("--change", required=True)
    start_round_parser.add_argument("--round-gate", required=True)
    start_round_parser.add_argument("--current-gate")
    start_round_parser.add_argument("--replace", action="store_true")
    start_round_parser.set_defaults(func=start_round_command)

    record_parser = subparsers.add_parser(
        "record", help="Persist the latest Superloop round and compute the loop verdict."
    )
    record_parser.add_argument("--workspace")
    record_parser.add_argument("--host", default="auto", type=normalize_host)
    record_parser.add_argument("--hypothesis")
    record_parser.add_argument("--change")
    record_parser.add_argument("--round-gate")
    record_parser.add_argument("--round-gate-result", required=True, choices=sorted(ROUND_GATE_RESULTS))
    record_parser.add_argument("--gate-status", "--stage-status", dest="gate_status", required=True, choices=sorted(ACCEPTED_GATE_STATUSES))
    record_parser.add_argument("--next-round")
    record_parser.add_argument("--remaining-gap", action="append", default=[])
    record_parser.add_argument("--completion-evidence", action="append", default=[])
    record_parser.add_argument("--mission-complete", "--top-level-goal-met", dest="mission_complete", action="store_true")
    record_parser.add_argument("--stop-rule-satisfied", action="store_true")
    record_parser.add_argument("--blocked-by")
    record_parser.add_argument("--failure-class", choices=sorted(FAILURE_CLASSES))
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

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
