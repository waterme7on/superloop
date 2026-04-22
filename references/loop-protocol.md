# Superloop Protocol

This is the execution protocol behind the skill.

Default execution mode:

- keep running rounds until a stop condition is met
- each round = `align -> plan -> execute -> verify -> decide -> record`
- persist the contract and every substantial round with the bundled harness

Producing a report does not end the loop by itself.
Passing the current gate does not end the loop by itself either. It usually means promote the next gate and continue.

## Phase 0: Align

Before starting a loop:

- inspect current state
- load or initialize harness state
- calibrate the finish standard
- identify the live gate
- check whether the fastest useful verification path exists
- confirm the workspace is safe to edit
- check the agreed budget: max rounds, timebox, or both

If the user asked for continuous looping but there is no clear gate yet, create the gate first.

## Phase 1: Plan

At the start of each round:

1. read the relevant files and current state
2. review the last result or baseline
3. identify what is still blocking the current gate
4. choose one focused hypothesis

Use this format:

- `Hypothesis`
- `Change`
- `Round Gate`
- `Current Gate`

This planning step is part of the round. It is not a separate approval stop unless the next move would exceed the existing contract.

## Phase 2: Execute

Rules:

- one focused change per round
- keep the write scope narrow
- prefer vertical slices
- avoid refactoring unrelated code
- do not bundle infrastructure work unless the current gate depends on it

If the current mission depends on missing instrumentation or missing smoke checks, adding that observability becomes the focused change.

## Phase 3: Verify

Run the minimum reliable set of checks.

Typical engineering gates:

- build or lint passes
- the command or route runs
- the main workflow completes once
- the expected file or output exists
- the targeted test or smoke check passes
- the failure path is visible and understandable

Mark evidence correctly:

- `hard-pass`
- `soft-pass`
- `fail`

Then separately decide:

- did the round pass?
- did the current gate advance?
- is the mission achieved?
- is the stop rule still open?
- is the budget still open?

## Phase 4: Keep or discard

Keep the change when:

- the round gate is met, or
- the round clearly improves the mission without breaking guardrails

Discard or revise when:

- the gate fails
- the main path regresses
- the change expands scope without earning stronger evidence

`Discard` must mean the failed round does not remain as accepted workspace state.

## Phase 5: Decide the next round

Choose from:

1. same mission, tighter implementation
2. same mission, better verification or observability
3. unblock a missing dependency
4. move to the next gate
5. escalate because the mission now needs a CEO-level decision

By default, report, record, choose the next round, and continue into it.

## Stop-condition judgment

Finish normally only when:

- the mission is materially achieved, or
- the explicit stop rule is satisfied

Stop because the budget was exhausted when:

- `max rounds` is reached, or
- `timebox minutes` is reached

Pause when:

- the next useful move would exceed the current contract, or
- the loop is blocked by missing context, tooling, or a higher-level decision

## Stop audit

Before stopping, ask:

- is this actually mission complete, or only gate complete?
- did we stop because of success, stop rule, or budget exhaustion?
- would a skeptical CEO still say the job is unfinished?
- are there still critical gaps for the chosen finish standard?

If the answer shows the mission is still open, do not report `completed`.

## Suggested cadence

### Prototype-ready

1. make one convincing slice real
2. verify it mechanically
3. document the sharpest remaining gap

### Workflow-ready

1. run the main path end to end
2. fix the most disruptive failure mode
3. add the minimum smoke coverage

### Operator-ready

1. make the loop resumable
2. make stop reasons explicit
3. make budget usage visible

### Production-ready

1. strengthen observability
2. strengthen rollback or recovery
3. tighten safety boundaries

## Reporting template

Use this summary after each substantial round:

- `Assumptions`
- `Finish Standard`
- `Mission`
- `Current Gate`
- `Hypothesis`
- `Round Gate Result`
- `Gate Status`
- `Stop Rule Status`
- `Budget Status`
- `Remaining Gap Ledger`
- `Implementation`
- `Verification`
- `Decision`
- `Next Round Chosen`

If the loop must pause, also add:

- `Blocked By`
- `Resume Condition`
