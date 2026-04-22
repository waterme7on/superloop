# Superloop Protocol

This is the full execution protocol behind the skill.

Default execution mode:

- keep running rounds until a stop condition is met
- each round = `plan -> build -> verify -> report`
- persist the contract and every substantial round with the bundled harness

Producing a report does not end the loop by itself.

Passing the current stage gate does not end the loop by itself either. It usually means promote the next stage gate and continue.

`Gate passed?` should be judged against the explicit round gate, not by freeform taste alone.

Before the first round, calibrate the maturity target of the whole request:

- `demo-ready`
- `product-shape-ready`
- `beta-ready`
- `production-ready`

If the requested maturity is higher than the current stop rule implies, tighten the stop rule and treat the weaker threshold as only a stage gate.

## Phase 0: Preconditions

Before starting a loop:

- inspect current state
- load or initialize harness state
- calibrate requested maturity
- identify the live phase goal
- check whether instrumentation exists
- identify the fastest reliable verification method
- confirm the workspace is safe to edit

If the user asks for continuous looping but no measurable gate exists yet, create the gate first.

Before making a risky or hard-to-revert round, checkpoint the pre-round state so discard is mechanically possible.

## Phase 1: Review

At the start of each round:

1. read relevant files and current product state
2. review the last result or baseline
3. identify what is still blocking the stage gate
4. choose one focused hypothesis

Use this format:

- `Hypothesis`: what should improve
- `Change`: what will be modified
- `Round Gate`: how the round passes or fails
- `Stage Gate`: what phase threshold this round is trying to advance

This planning step is part of the round. It is not a separate approval stop unless the next move would exceed the existing goal contract.

## Phase 2: Implement

Rules:

- one focused change per round
- keep the write scope narrow
- prefer vertical slices
- avoid refactoring unrelated code
- do not bundle infrastructure work unless the current gate depends on it

If the round is meant to optimize a product metric but the instrumentation needed to judge that metric is missing, instrumentation becomes the focused change.

## Phase 3: Verify

Run the minimum reliable set of checks.

Typical inner-loop gates:

- build passes
- route renders
- browser interaction works
- event fires
- checkout or primary action completes
- lighthouse or performance proxy reaches threshold

Typical outer-loop evidence:

- click-through rate
- signup rate
- activation rate
- add-to-cart rate
- checkout start rate

Mark evidence correctly:

- `hard pass`: mechanically verified now
- `soft pass`: likely improved, needs live traffic or more samples
- `fail`: gate not met

Judgment rule:

- compare the observed evidence to the current `Round Gate`
- use mechanical checks and direct assertions first
- use proxy or noisy product evidence second
- let the model summarize ambiguity, but never let it invent a pass without evidence

Then separately decide:

- did the round pass?
- did the stage advance?
- is the stop rule still open?

## Phase 4: Keep or discard

Keep the change when:

- the round gate is met, or
- the proxy metric clearly improves without breaking guardrails

Discard or revise when:

- the gate fails
- the main flow regresses
- the change expands scope without earning better evidence

`Discard` must mean the failed round does not remain as accepted workspace state.

If the change was already applied, revert it before ending the round unless the user explicitly wants to inspect the failed attempt.

## Phase 5: Decide the next round

Choose from:

1. same goal, tighter implementation
2. same goal, clearer messaging or UX
3. add missing instrumentation
4. move to the next stage gate
5. escalate because the current goal is blocked by a higher-level product issue

By default, report, choose the next round, and continue into it.
Record the round through the harness before calling it `continue`, `pause`, or `stop`.

Finish only when:

- the top-level goal is met
- the stop rule is hit

If the current stage gate is met but the top-level goal is not, advance to the next stage gate and continue.

Before stopping, run a stop audit:

- is this really `goal complete`, or only `stage complete`?
- does the requested maturity target still have critical gaps?
- was the current stop rule inferred too weakly?

If the stop audit fails, tighten the contract and continue.

If the next move would exceed the current contract, or the loop is blocked by missing context, tooling, or a higher-level product decision, treat that as a forced pause, not a completed stop. Report the blocker and the resume condition, then continue once the blocker is resolved.

## Suggested cadence

### Night-one MVP

1. core journey live
2. primary action works end to end
3. minimal trust and clarity in place
4. analytics wired

### First traffic round

1. verify top-of-funnel promise matches the page
2. check funnel drops
3. improve the biggest drop only

### Later rounds

1. separate message tests from UX tests
2. separate pricing tests from design tests
3. expand only after a stable baseline exists

## Reporting template

Use this summary after each substantial round:

- `Assumptions`
- `Maturity Target`
- `Phase Goal`
- `Hypothesis`
- `Round Gate Result`
- `Stage Gate Status`
- `Stop Rule Status`
- `Remaining Gap Ledger`
- `Implementation`
- `Verification`
- `Decision`
- `Next Round Chosen`

`Next Round Chosen` means the loop will move into that round automatically unless an explicit stop condition is met or a forced pause is required right after reporting.

Do not replace this with `Next Suggested Round` during normal continuous execution.

If the loop must pause because it cannot continue safely right now, keep `Next Round Chosen` and add:

- `Blocked By`
- `Resume Condition`
