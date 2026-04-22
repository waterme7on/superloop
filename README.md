# Superloop

`superloop` is a Codex skill for product-validation loops.

It is meant for work like:

- storefront conversion loops
- landing-page validation
- app onboarding and activation work
- MVP shipping where "done" should be tied to stage gates and stop rules, not vibes

This version is harness-backed. In addition to the skill prompt, it includes a local CLI that persists goal-contract state, round outcomes, blockers, and `continue|pause|stop` verdicts across turns.

## What is in this repo

- `SKILL.md`: the main skill contract and operating model
- `agents/openai.yaml`: UI metadata for the skill picker
- `references/`: supporting docs for goal contracts, loop protocol, maturity ladders, artifact gates, and harness usage
- `scripts/superloop_cli.sh`: shell entrypoint for the harness
- `scripts/superloop_harness.py`: stateful harness implementation

## Install

Clone the repo, then copy or sync it into your Codex skills directory:

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$CODEX_HOME/skills/superloop"
rsync -a --delete ./ "$CODEX_HOME/skills/superloop/"
```

After that, the skill is available as `$superloop`.

## Quick start

Set the harness path:

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export SUPERLOOP_HARNESS="$CODEX_HOME/skills/superloop/scripts/superloop_cli.sh"
```

Resume an existing run:

```bash
"$SUPERLOOP_HARNESS" resume --workspace /path/to/repo
```

Initialize a new run:

```bash
"$SUPERLOOP_HARNESS" init \
  --workspace /path/to/repo \
  --goal "Validate whether users complete the first useful action" \
  --artifact app \
  --maturity-target product-shape-ready \
  --scope "onboarding, primary action, analytics"
```

Record a round:

```bash
"$SUPERLOOP_HARNESS" record \
  --workspace /path/to/repo \
  --hypothesis "Reducing setup friction increases first-session completion" \
  --change "remove one blocking onboarding field" \
  --round-gate "A new user reaches the primary action in one session" \
  --round-gate-result hard-pass \
  --stage-status stage-complete \
  --next-round "wire and verify the activation event"
```

## State model

By default, the harness stores state outside the product repo:

```text
~/.codex/state/superloop/<workspace-key>.json
```

That lets the loop resume across turns without dirtying the target workspace.

## When to use Superloop

Use `superloop` when you want Codex to:

- keep a product goal stable across rounds
- separate `Round Gate`, `Stage Gate`, and `Stop Rule`
- verify each round mechanically
- keep or discard changes based on evidence
- continue until the explicit stop condition is actually met

Do not use it for:

- narrow one-off bug fixes
- pure brainstorming with no execution gate
- refactors that have no product-validation loop

## Development

Useful checks while editing this repo:

```bash
python3 -m py_compile scripts/superloop_harness.py
./scripts/superloop_cli.sh resume --workspace "$(pwd)"
```

If the second command returns a warning about missing state, that is expected for a fresh workspace.
