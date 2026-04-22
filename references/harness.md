# Harness Workflow

Use the bundled CLI instead of carrying Superloop state only in prose.

## Commands

Set the path once:

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export SUPERLOOP_HARNESS="$CODEX_HOME/skills/superloop/scripts/superloop_cli.sh"
```

### Resume

Run this first in the current workspace:

```bash
"$SUPERLOOP_HARNESS" resume
```

If an active run exists, use its stored contract, next round, blocker, and stop rule instead of re-inferring them from scratch.

### Init

Run `init` only when `resume` reports no active run:

```bash
"$SUPERLOOP_HARNESS" init \
  --goal "..." \
  --artifact "app|storefront|landing-page|mvp" \
  --maturity-target "demo-ready|product-shape-ready|beta-ready|production-ready" \
  --metric "..." \
  --stage-gate "..." \
  --scope "..." \
  --constraint "..."
```

If `stop-rule` is omitted, the harness writes a maturity-aware default that is stronger than "main path unblocked."

### Record

After each substantial round:

```bash
"$SUPERLOOP_HARNESS" record \
  --hypothesis "..." \
  --change "..." \
  --round-gate "..." \
  --round-gate-result "hard-pass|soft-pass|fail" \
  --stage-status "stage-complete|stage-in-progress|stage-blocked" \
  --next-round "..."
```

Optional inputs:

- `--remaining-gap "..."` may be repeated
- `--top-level-goal-met`
- `--stop-rule-satisfied`
- `--blocked-by "..."`
- `--resume-condition "..."`
- `--cannot-continue`
- `--would-exceed-contract`

The harness returns a verdict:

- `continue`
- `pause`
- `stop`

Use that verdict for loop control.

## State model

State is stored outside the product workspace by default:

- `~/.codex/state/superloop/<workspace-key>.json`

This keeps resume data across turns without dirtying the target repository.

## Guardrails

- `stop` requires either `top-level goal met` or `stop rule satisfied`
- `stop` is blocked if `remaining_gap_ledger` is not empty
- `pause` is preferred when the next move would exceed the contract or a real blocker exists
- `continue` is the default when the goal is not done and the loop can still move safely
