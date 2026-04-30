# Harness Workflow

Use the bundled CLI instead of carrying Superloop state only in prose.

## Commands

Set the path once:

```bash
export SUPERLOOP_HARNESS="${SUPERLOOP_HARNESS:-$HOME/.superloop/superloop/scripts/superloop_cli.sh}"
```

Installed host paths are also valid:

- Codex: `$CODEX_HOME/skills/superloop/scripts/superloop_cli.sh`
- Claude Code: `$CLAUDE_HOME/skills/superloop/scripts/superloop_cli.sh`
- Generic CLI: `$SUPERLOOP_HOME/superloop/scripts/superloop_cli.sh`

### Resume

Run this first in the current workspace:

```bash
"$SUPERLOOP_HARNESS" resume
```

If an active run exists, use its stored contract, next round, blocker, budget, and stop rule instead of re-inferring them from scratch.

### Init

Run `init` only when `resume` reports no active run:

```bash
"$SUPERLOOP_HARNESS" init \
  --goal "..." \
  --workstream "repo workflow|feature|tooling|docs|agent harness|deploy" \
  --finish-standard "prototype-ready|workflow-ready|operator-ready|production-ready" \
  --success-signal "..." \
  --success-direction "higher|lower" \
  --current-gate "..." \
  --scope "..." \
  --constraint "..." \
  --max-rounds 5 \
  --timebox-minutes 90
```

Legacy compatibility:

- `--artifact` still maps to `--workstream`
- `--maturity-target` still maps to `--finish-standard`
- `--metric` still maps to `--success-signal`
- `--stage-gate` still maps to `--current-gate`

If `stop-rule` is omitted, the harness writes a budget-aware default that is stronger than "do one round and stop."

### Record

After each substantial round:

```bash
"$SUPERLOOP_HARNESS" record \
  --hypothesis "..." \
  --change "..." \
  --round-gate "..." \
  --round-gate-result "hard-pass|soft-pass|fail" \
  --gate-status "gate-complete|gate-in-progress|gate-blocked" \
  --next-round "..."
```

Optional inputs:

- `--remaining-gap "..."` may be repeated
- `--mission-complete`
- `--stop-rule-satisfied`
- `--blocked-by "..."`
- `--resume-condition "..."`
- `--cannot-continue`
- `--would-exceed-contract`

If a round is actually complete, omit `--remaining-gap` or use a no-gap sentinel such as
`--remaining-gap "none"`. The harness normalizes common no-gap strings so a human-style
completion note does not accidentally force an extra round.

The harness returns a verdict:

- `continue`
- `pause`
- `stop`

Use that verdict for loop control.

It also returns a `budget_status` object so the caller can see elapsed time, rounds used, remaining budget, and whether the loop has hit a round or time cap.

### Timeline / Report

Render a human-readable ledger without relying on chat history:

```bash
"$SUPERLOOP_HARNESS" timeline --workspace /path/to/repo
"$SUPERLOOP_HARNESS" report --workspace /path/to/repo --format json
```

The markdown report includes the mission contract, budget, round ledger, blockers,
resume condition, stop reason, state path, installed path, and harness path.

### Doctor

Check which host adapter is active and whether an installed copy has drifted:

```bash
"$SUPERLOOP_HARNESS" doctor --host codex --source /path/to/superloop
"$SUPERLOOP_HARNESS" doctor --host claude-code --source /path/to/superloop
"$SUPERLOOP_HARNESS" doctor --host generic --source /path/to/superloop
```

Use `--check` when the command should return non-zero on missing or drifted installs.

### Preflight

Check required and optional environment variables before spending a deploy or
external-service round:

```bash
"$SUPERLOOP_HARNESS" preflight \
  --require-env CLOUDFLARE_API_TOKEN \
  --require-env CLOUDFLARE_ACCOUNT_ID \
  --optional-env SENTRY_DSN
```

Missing required variables return a non-zero exit code and include a
`config-missing` failure classification plus a concrete next action.

When `record` captures a blocked or failed round, the harness also stores a
stable `failure_signature` and `failure_repeat_count`. If the same failure
appears again, the returned next actions warn against another identical retry.

## State model

State is stored outside the target workspace by default:

- explicit: `$SUPERLOOP_STATE_HOME/<workspace-key>.json`
- neutral runtime: `$SUPERLOOP_HOME/state/<workspace-key>.json`
- Codex adapter: `$CODEX_HOME/state/superloop/<workspace-key>.json`
- Claude Code adapter: `$CLAUDE_HOME/state/superloop/<workspace-key>.json`
- generic CLI: `~/.superloop/state/<workspace-key>.json`

This keeps resume data across turns without dirtying the target repo or deliverable folder.

## Guardrails

- `stop` can mean either mission complete or budget exhausted; say which one
- `pause` is preferred when the next move would exceed the contract or a real blocker exists
- `continue` is the default when the mission is not done, the budget is still open, and the loop can still move safely
- if the loop stops because the budget was exhausted, preserve the next-round hint when one exists
