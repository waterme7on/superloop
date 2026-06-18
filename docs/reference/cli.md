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

Windows PowerShell uses the `.ps1` wrapper instead:

```powershell
$env:SUPERLOOP_HARNESS = Join-Path $env:SUPERLOOP_HOME "superloop\scripts\superloop_cli.ps1"
```

Installed host paths are also valid on Windows:

- Codex: `$env:CODEX_HOME\skills\superloop\scripts\superloop_cli.ps1`
- Claude Code: `$env:CLAUDE_HOME\skills\superloop\scripts\superloop_cli.ps1`
- Generic CLI: `$env:SUPERLOOP_HOME\superloop\scripts\superloop_cli.ps1`

### Resume

Run this first in the current workspace:

```bash
"$SUPERLOOP_HARNESS" resume
```

```powershell
& $env:SUPERLOOP_HARNESS resume
```

If an active run exists, use its stored contract, next round, blocker, budget, and stop rule
instead of re-inferring them from scratch.

If `resume` loads a run but the user ask has clearly changed, do not silently inherit the old
contract. Start a fresh mission with `init` and reserve `init --continue-existing` for cases
where the mission is intentionally the same.

### Context

Render the next-round runtime context before continuing a long-running mission:

```bash
"$SUPERLOOP_HARNESS" context --workspace /path/to/repo
"$SUPERLOOP_HARNESS" context --workspace /path/to/repo --format json
```

`context` is the Superloop equivalent of a runtime goal injection. It turns the
persisted contract, budget, active round, next round, remaining gaps, and
completion audit checklist into a prompt-shaped artifact. Use it when a resumed
agent needs the current mission state without relying on chat memory.

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
  --required-evidence "check" \
  --max-rounds 5 \
  --timebox-minutes 90
```

Safe same-workspace reset:

- plain `init` now starts a fresh mission and archives the previously active run for auditability
- `--continue-existing` is required before `init` will merge into the currently loaded run
- `--reset` still starts a fresh mission, but now archives the previous run before replacing it

Legacy compatibility:

- `--artifact` still maps to `--workstream`
- `--maturity-target` still maps to `--finish-standard`
- `--metric` still maps to `--success-signal`
- `--stage-gate` still maps to `--current-gate`

If `stop-rule` is omitted, the harness writes a budget-aware default that is stronger than "do one round and stop."

Use `--required-evidence` when a mission should not record a hard-pass,
gate-complete, or mission-complete round unless named verification evidence exists.
That evidence must be created by `verify`, not by prose.

### Preflight

For stages that depend on environment configuration, run a lightweight preflight first:

```bash
"$SUPERLOOP_HARNESS" preflight \
  --stage deploy \
  --require-env VERCEL_TOKEN \
  --optional-env SENTRY_AUTH_TOKEN
```

The harness will:

- fail fast on missing required env vars
- warn on missing optional env vars
- return a small status card with classification, blocker, and recommended next action

### Verify

Run verification commands through the harness when the next `record` should prove
that tests, builds, smoke checks, or browser checks actually executed:

```bash
"$SUPERLOOP_HARNESS" verify \
  --workspace /path/to/repo \
  --name check \
  -- npm run check
```

`verify` stores machine evidence in Superloop state:

- evidence id and name
- command and working directory
- started and ended timestamps
- exit code and success/failure status
- git branch, commit, and dirty status before and after the command
- stdout/stderr tails plus an output hash

If the command fails, the failure is still recorded as evidence, but it cannot
satisfy `record --require-evidence`.

### Status Card

Render a PR/Issue-ready status card for plan, build, test, deploy, or migration stages:

```bash
"$SUPERLOOP_HARNESS" status-card \
  --stage deploy \
  --platform cloudflare \
  --migration-from vercel \
  --migration-to cloudflare \
  --require-env CLOUDFLARE_API_TOKEN \
  --optional-env SENTRY_AUTH_TOKEN \
  --format markdown
```

The status card includes:

- current stage
- failure classification code
- blocking items
- platform and migration context
- recommended next actions
- repeated failure count when provided

To sync the same card to GitHub, provide an issue or PR target:

```bash
"$SUPERLOOP_HARNESS" status-card \
  --stage deploy \
  --platform cloudflare \
  --classification external-service \
  --github-repo owner/repo \
  --github-pr 12
```

Use `--dry-run` to verify the target without posting. Use `--locale zh` or
`--locale en` to render operator-facing text consistently instead of mixing
languages in the same status card.

In CI, `status-card` also reads `GITHUB_REPOSITORY`,
`SUPERLOOP_GITHUB_ISSUE`, and `SUPERLOOP_GITHUB_PR`, so a workflow can sync
the latest deploy or failure card without repeating those flags each step.

### Record

For interruptible work, start the round before editing:

```bash
"$SUPERLOOP_HARNESS" start-round \
  --hypothesis "..." \
  --change "..." \
  --round-gate "..."
```

`start-round` stores an in-flight round. If the session is interrupted, `resume`
and `context` will show that active round so the next agent can finish or replace
it deliberately. After `start-round`, `record` may omit `--hypothesis`,
`--change`, and `--round-gate`; the harness will use the active round values.

After each substantial round:

```bash
"$SUPERLOOP_HARNESS" record \
  --hypothesis "..." \
  --change "..." \
  --round-gate "..." \
  --round-gate-result "hard-pass|soft-pass|fail" \
  --gate-status "gate-complete|gate-in-progress|gate-blocked" \
  --require-evidence "check" \
  --next-round "..."
```

Optional inputs:

- `--remaining-gap "..."` may be repeated
- `--completion-evidence "..."` may be repeated
- `--require-evidence "..."` may be repeated
- `--mission-complete`
- `--stop-rule-satisfied`
- `--blocked-by "..."`
- `--resume-condition "..."`
- `--cannot-continue`
- `--would-exceed-contract`

If a round is actually complete, omit `--remaining-gap` or use a no-gap sentinel such as
`--remaining-gap "none"`. The harness normalizes common no-gap strings so a human-style
completion note does not accidentally force an extra round.

When using `--mission-complete`, provide at least one `--completion-evidence`
item. The harness rejects mission completion without evidence so a loop cannot
turn partial progress into a completed mission by assertion alone.

When using `--require-evidence`, the harness rejects the record unless the latest
matching evidence id or evidence name exists and has status `success`. Contract-level
requirements from `init --required-evidence` are enforced automatically for hard-pass,
gate-complete, and mission-complete records.

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

```powershell
& $env:SUPERLOOP_HARNESS doctor --host codex --source C:\path\to\superloop
& $env:SUPERLOOP_HARNESS doctor --host claude-code --source C:\path\to\superloop
& $env:SUPERLOOP_HARNESS doctor --host generic --source C:\path\to\superloop
```

Use `--check` when the command should return non-zero on missing or drifted installs.

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
- archived prior runs: `<state-home>/history/<workspace-key>/`

This keeps resume data across turns without dirtying the target repo or deliverable folder.

## Guardrails

- `stop` can mean either mission complete or budget exhausted; say which one
- `pause` is preferred when the next move would exceed the contract or a real blocker exists
- `continue` is the default when the mission is not done, the budget is still open, and the loop can still move safely
- if the loop stops because the budget was exhausted, preserve the next-round hint when one exists
