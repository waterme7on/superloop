---
name: superloop
description: Use when the user wants a goal-driven iterative coding harness where the user acts as CEO, defines the mission and budget, and the coding agent executes, verifies, decides, and keeps iterating until the goal is achieved or the agreed round or time limit is reached.
---

# Superloop

Use this skill when the user wants a harnessed execution loop, not a one-off edit.

This skill adapts the `autoresearch` pattern to general vibe coding:

- the user acts as CEO and sets the mission
- the coding agent acts as the operator and executes rounds
- each round is narrow enough to judge honestly
- state lives in the harness, not only in prose
- the loop stops only when the mission is achieved, the explicit stop rule is hit, or the agreed budget is exhausted

This repo includes one ready-to-run implementation for local skill environments today, but the operating model itself is tool-agnostic.

## Trigger cues

This skill is a strong match when the user says things like:

- `用 $superloop 持续迭代这个 repo，直到目标达成`
- `把我当 CEO，你当执行者，边做边判断`
- `不要只改一轮，按 harness 一直跑下去`
- `keep iterating for 5 rounds or 90 minutes`
- `run this like an autonomous coding harness`

Do not use this skill when the user only wants:

- a trivial one-off fix
- a pure brainstorm with no execution loop
- a task that is mostly repeated manual human work each round

## Harness preflight

Before running the first round in a workspace:

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export SUPERLOOP_HARNESS="$CODEX_HOME/skills/superloop/scripts/superloop_cli.sh"
```

Then:

1. run `"$SUPERLOOP_HARNESS" resume`
2. if `resume` loads an old run but the ask changed, call `init` without `--continue-existing` so the previous run is archived and the new mission starts cleanly
3. use `init --continue-existing` only when you intentionally want to keep the same mission and budget while refreshing contract fields
4. before risky stages such as deploy or external-service hops, call `preflight` with required/optional env keys when they matter
5. after every substantial round, call `record`
6. use the harness verdict `continue`, `pause`, or `stop` instead of inventing one from prose alone

Minimal init example:

```bash
"$SUPERLOOP_HARNESS" init \
  --goal "Ship the first usable version of this workflow" \
  --workstream "repo workflow" \
  --finish-standard "workflow-ready" \
  --success-signal "The main workflow runs end to end with targeted checks passing" \
  --current-gate "The next high-leverage change lands cleanly and can be verified" \
  --scope "code, docs, smoke checks" \
  --max-rounds 5 \
  --timebox-minutes 90
```

Minimal preflight example:

```bash
"$SUPERLOOP_HARNESS" preflight \
  --workspace /path/to/repo \
  --stage deploy \
  --require-env VERCEL_TOKEN \
  --optional-env SENTRY_AUTH_TOKEN
```

Minimal round record example:

```bash
"$SUPERLOOP_HARNESS" record \
  --hypothesis "Removing setup friction will unblock the main path" \
  --change "simplify the setup sequence and update the smoke check" \
  --round-gate "A fresh run completes once without manual rescue" \
  --round-gate-result "hard-pass" \
  --gate-status "gate-complete" \
  --next-round "tighten failure handling and verify the fallback path"
```

## First-turn behavior

On the first response after this skill triggers:

1. load harness state with `resume`; if none exists, initialize it with `init`
   - if `resume` loads a stale or wrong mission for the current ask, start a fresh run with `init` and do **not** silently inherit the old contract
2. restate the mission in one sentence
3. state the current gate
4. list explicit assumptions if the user did not provide a full contract
5. say what this round will change
6. say how this round will be verified
7. say what budget remains if max rounds or a timebox is active

If key information is missing, ask the smallest useful batch of questions. If safe defaults exist, state them, initialize the harness with those defaults, start with the first round, and keep going until a stop condition is met. If they do not, stop after the questions and wait.

## Default execution mode

The default mode is a continuing loop:

- `align -> plan -> execute -> verify -> decide -> record -> continue`

That means:

- the agent should plan the current round in a compact way
- the agent should then execute that round without asking for per-step approval
- the agent should verify the result mechanically
- the agent should record the round through the harness, report the keep or discard decision, choose the next round, and continue unless an explicit stop condition has been met

Do not stop after one round just because a report was produced.
Do not claim `pause` or `stop` without a corresponding harness record.

Unless the user says to stop, keep iterating automatically while all of these remain true:

- the mission has not been achieved
- the explicit stop rule has not been reached
- the next move still fits inside the stated contract
- the agreed round or time budget has not been exhausted
- the loop is not blocked by missing context, tooling, or a CEO-level decision

Treat the current gate as a milestone, not a stop signal.

## CEO / Agent split

The operating model is explicit:

- the user as CEO owns `goal`, `scope`, `constraints`, `budget`, and `stop rule`
- the coding agent owns `round selection`, `execution`, `verification`, `keep or discard`, and `next-round recommendation`
- the harness owns `persisted state`, `budget tracking`, and `continue / pause / stop` verdicts

The user is steering the company.
The agent is running the current operating loop.
This is intentionally closer to a CEO and execution-worker setup than a normal assistant chat.

## Setup gate

The user does **not** need to provide the full contract up front.

The true minimum is usually just:

- what they want done
- which repo, workflow, or deliverable this applies to
- any obvious hard constraint

Prefer this order when you need to ask:

1. `Goal`: what outcome matters most right now
2. `Workstream`: repo feature, workflow, tooling, docs, agent harness, deployment, or other execution surface
3. `Current Gate`: what must become true before this round counts as a win
4. `Constraints`: hard limits such as no refactor, no deploy, no paid services, today only
5. `Stop Rule`: when to stop, escalate, or hand control back
6. `Budget`: how many rounds or how much time to spend

If the user gives only a rough target, guide with a compact batch like:

- `这轮最重要的是先跑通主路径，还是先提高稳定性？`
- `对象是 repo 功能、工具链、agent workflow，还是文档交付物？`
- `有什么硬限制吗，比如不重构、不上线、只做 3 轮或 90 分钟？`

Then turn the answers into the contract internally and persist it with the harness.

## Core model

Treat this as two linked loops:

1. **Inner loop: execution**
   - code, config, scripts, docs, tests, browser actions, deploy steps, instrumentation
   - fast feedback
   - the agent can drive this end to end

2. **Outer loop: steering**
   - mission alignment
   - budget usage
   - keep or discard decisions
   - continue, pause, stop, or escalate

Never optimize a vague target like "make it better." Convert it into a mission contract first.

## Finish standards

Before locking the contract, classify the requested finish standard.

Use these default bands:

- `prototype-ready`: one convincing end-to-end slice is real
- `workflow-ready`: the main workflow works consistently enough to use
- `operator-ready`: the user can hand the goal to the harness with bounded oversight
- `production-ready`: the workflow is operationally durable, observable, and safe

If the user's words imply a higher bar, do not silently downgrade it.

Examples:

- `先做出来` usually implies `prototype-ready`
- `先把主流程跑通` usually implies `workflow-ready`
- `我希望以后可以放心让它自己迭代` usually implies `operator-ready`
- `生产可用` or `production-ready` implies `production-ready`

If the inferred stop rule is weaker than the requested finish standard:

- downgrade the weak rule to a `Current Gate`
- define a stronger `Stop Rule`
- continue looping

## Mission contract

Before implementation, define:

- `Goal`: the outcome that matters
- `Finish Standard`: `prototype-ready`, `workflow-ready`, `operator-ready`, or `production-ready`
- `Success Signal`: what observable signal means the mission is moving
- `Success Direction`: which way that signal should move when rounds are working
- `Current Gate`: what counts as success for this phase
- `Scope`: which files, systems, or deliverables may change
- `Constraints`: time, risk, tooling, legal, budget, or staffing boundaries
- `Stop Rule`: when to stop, escalate, or hand back control
- `Max Rounds`: optional round budget
- `Timebox Minutes`: optional time budget

If these are missing, gather them or infer the smallest safe version and state the assumptions.

Within that contract, the agent is authorized to execute the current round and later rounds that stay inside the same contract without asking again for each step.

## Round judgment

Judge the current round against the explicit `Round Gate`, not vibes.

Use honest labels:

- `hard pass`: the gate is mechanically met now
- `soft pass`: the round is directionally good but still needs another step or more evidence
- `fail`: the gate is missed, contradicted, or the main path regressed

Then separately label the phase:

- `gate-complete`
- `gate-in-progress`
- `gate-blocked`

## Keep or discard

The keep or discard decision must be reflected in the workspace, not just in prose.

- `Keep`: leave the verified change in place
- `Discard`: revert the round's change before ending the round, or avoid applying it if verification already failed

Do not say `discard` while leaving the failed experiment sitting in the working tree.

## Stop audit

Before stopping, ask:

- was the mission actually achieved, or did we only finish the current gate?
- did the explicit stop rule fire?
- did we hit the agreed round or time budget?
- are we blocked by a CEO-level decision or a real dependency?

If stopping because the budget was exhausted, say that explicitly.
Budget exhaustion is a valid stop reason.
It is not the same thing as mission complete.

## Boundaries

- do not confuse activity with progress
- do not widen scope silently
- do not stop just because one test passed once if the stated mission is broader
- do not burn budget on repeated identical attempts
- do not let the loop drift into a different mission without a CEO check-in

## References

- For turning a vague request into a mission contract: [references/goal-contract.md](references/goal-contract.md)
- For the execution loop and decision rules: [references/loop-protocol.md](references/loop-protocol.md)
- For default gates by workstream: [references/artifact-gates.md](references/artifact-gates.md)
- For calibrating finish standards: [references/maturity-ladders.md](references/maturity-ladders.md)
- For the harness workflow and CLI contract: [references/harness.md](references/harness.md)
- For the visual model of the skill: [references/visual-map.md](references/visual-map.md)
