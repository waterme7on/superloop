# Mission Contract

Use this reference when the user knows the destination but has not yet turned it into a usable operating contract for the harness.

Important:

- this is primarily for the agent to construct internally
- the user does not need to fill every field by hand
- the contract should be tight enough to guide autonomous rounds without ceremony

## Fast intake mode

If the user gives only a rough goal, collect the contract with the smallest useful batch of questions.

Suggested sequence:

1. What are we trying to get done?
2. Which repo, workflow, or deliverable are we working on?
3. What absolutely must become true in this phase?
4. What hard constraints should I respect?
5. When should I stop, escalate, or hand control back?
6. How many rounds or how much time should I spend?

After that, translate the answers into:

- `Goal`
- `Success Signal`
- `Success Direction`
- `Current Gate`
- `Scope`
- `Constraints`
- `Stop Rule`
- `Max Rounds`
- `Timebox Minutes`

Once that contract is clear enough, the agent should execute the current round inside it without asking for per-step approval and continue into later rounds until the stop condition is met.

## Default inference rules

When the user does not provide all fields, prefer these defaults:

- `Success Signal`
  - use the nearest observable engineering or deliverable signal
- `Current Gate`
  - if the end goal is noisy or slow, use the nearest mechanically verifiable gate first
- `Scope`
  - infer from the named workstream and repo layout
- `Constraints`
  - infer common speed-mode constraints when the user is clearly in execution mode
- `Stop Rule`
  - if the user does not specify one, stop when the mission is materially achieved, the budget is exhausted, or the loop is blocked by a CEO-level decision
- `Budget`
  - if the user does not specify one and the mission is open-ended, infer a small default budget, usually `3 rounds` or `90 minutes`

## Required fields

- `Goal`
- `Finish Standard`
- `Success Signal`
- `Success Direction`
- `Current Gate`
- `Scope`
- `Constraints`
- `Stop Rule`

Optional but strongly recommended:

- `Max Rounds`
- `Timebox Minutes`

These fields define the boundary of autonomous action for the current round and later rounds that stay inside the same contract.

## Default framing

Convert a broad request into:

1. **Mission**
   - the actual outcome the user cares about
2. **Current gate**
   - the next thing that must become true
3. **Round hypothesis**
   - the single change this iteration is trying to prove or disprove
4. **Budget**
   - the amount of autonomy the user is granting before a check-in

## Good examples

### Repo workflow

- Goal: make the main workflow usable without manual rescue
- Finish Standard: workflow-ready
- Success Signal: a fresh run completes once and the targeted checks pass
- Current Gate: setup, execution, and smoke verification all complete end to end
- Scope: CLI, setup docs, smoke checks
- Constraints: no large refactor, no paid services, finish today
- Stop Rule: stop when the workflow is usable or after 5 rounds, whichever comes first

### Agent harness

- Goal: make the harness continue autonomously until it either succeeds or spends its agreed budget
- Finish Standard: operator-ready
- Success Signal: the harness persists state, records each round, and stops for budget or blocker reasons without ambiguity
- Current Gate: init, resume, record, and budget stop conditions all work
- Scope: skill docs, harness script, smoke tests
- Constraints: no external service dependency
- Stop Rule: stop when round and time budgets work reliably or after 90 minutes

### Docs or research deliverable

- Goal: produce a handoff document the user can immediately use
- Finish Standard: prototype-ready
- Success Signal: the document exists in the right path and format, and the major decisions are explicit
- Current Gate: first acceptable draft exists with evidence and decisions
- Scope: markdown docs only
- Constraints: no extra tooling
- Stop Rule: stop when the handoff is reviewable or after 3 rounds

## Heuristics

- prefer one primary success signal
- make the current gate easier than the final mission
- if the final outcome is slow to judge, use the nearest mechanical gate first
- if the user gives only the destination, infer a gate and a budget and say so explicitly

## Anti-patterns

- goal without a success signal
- success signal without a current gate
- one round trying to change implementation, architecture, docs, and deployment all at once
- optimization with no scope or budget
- pretending `gate complete` means `mission complete`
