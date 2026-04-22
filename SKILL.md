---
name: superloop
description: Use when the user wants Codex to run a goal-driven product validation loop for an app, storefront, landing page, or MVP. This skill turns a product goal into staged iteration with measurable gates, minimal code changes, mechanical verification, keep-or-discard decisions, and the next best experiment. Best for rapid validation, MVP shipping, and autoresearch-style execution adapted to products instead of only code quality.
---

# Superloop

Use this skill when the user wants a product loop, not just a code change.

This skill adapts the `autoresearch` pattern to product work:

- Human sets the target, constraints, and stop rules
- Codex chooses the next best path within those bounds
- Each round starts with a small plan, then builds
- Each iteration makes one focused change
- Every change must be verified
- Keep wins, discard regressions, repeat

## Trigger cues

This skill is a strong match when the user says things like:

- `用 $superloop 帮我把这个 storefront 做到今晚能验证`
- `帮我一轮一轮把这个 landing page 调到能投流`
- `不要只改代码，按产品验证循环往前推`
- `ship the MVP and keep iterating until the main path works`

Do not use this skill when the user only wants:

- a narrow bug fix with no product decision loop
- a pure design brainstorm with no execution gate
- a one-off refactor unrelated to product validation

## First-turn behavior

On the first response after this skill triggers:

1. restate the working goal in one sentence
2. state the current stage gate
3. list explicit assumptions if the user did not provide a full contract
4. say what this round will change
5. say how this round will be verified

If key information is missing, ask the smallest useful batch of questions. If safe defaults exist, state them, start with the first round, and keep going until a stop condition is met. If they do not, stop after the questions and wait.

## Default execution mode

The default mode is a continuing loop:

- `plan -> build -> verify -> report`

That means:

- Codex should plan the current round in a compact way
- Codex should then execute that round without asking for per-step approval
- Codex should verify the result mechanically
- Codex should report the keep/discard decision, choose the next round, and continue unless an explicit stop condition has been met

Do not stop after one round just because a report was produced.

Unless the user says to stop, keep iterating automatically while all of these remain true:

- the top-level goal has not been met
- the user-defined stop rule has not been reached
- the next move still fits inside the stated goal contract
- the loop is not blocked by missing context, tooling, or a higher-level product decision

Treat the current stage gate as a milestone, not a stop signal.

When a stage gate passes:

- keep the successful change
- promote the next stage gate
- continue the loop unless the top-level goal or stop rule says otherwise

`Gate passed?` is not a freeform taste call.

Judge the current `Round Gate` against the best available evidence in this order:

- mechanical checks and direct assertions first
- proxy product evidence second
- inferred judgment only to summarize ambiguous evidence, never to invent a pass

Use honest labels:

- `hard pass`: the current gate is mechanically met now
- `soft pass`: the change is directionally good but still needs real traffic or more samples
- `fail`: the gate threshold is not met or the main flow regressed

## Interactive Setup Gate

The user does **not** need to provide the full goal contract up front.

Default interaction rule:

- If the user provides a full contract, use it
- If the user provides only a rough target, guide them with short questions
- If some fields are still missing after that, infer the smallest safe defaults and state them explicitly

Do not force the user to fill a long template unless they clearly want that style.

### Minimum input

The true minimum is usually just:

- what they want to validate
- what artifact they are working on
- any obvious hard constraint

Example:

- `用 $superloop 帮我把这个 storefront 做到今晚能投流验证`
- `用 $superloop 帮我把这个 app 做到可以验证 first activation`

From there, gather or infer the rest.

### Questioning style

Ask only what is needed to unblock the loop.

Prefer this order:

1. `Goal`: what outcome matters most right now
2. `Artifact`: storefront, app, landing page, onboarding flow, checkout flow, etc.
3. `Current stage gate`: what must work before anything else
4. `Constraints`: hard limits such as no CMS, no redesign, tonight only, no backend, no paid tools
5. `Stop rule`: when to stop optimizing and just unblock the main path

If the metric is not yet clear, do not block on the final business metric. Propose a mechanical proxy gate first.

Do not ask for approval of the round's individual code changes when they fit inside the stated goal, scope, constraints, and stop rule.

### When to infer instead of asking

Infer reasonable defaults when:

- the repo structure makes scope obvious
- the stage gate is implied by the user's wording
- the constraint is a common MVP constraint
- asking would only add ceremony, not clarity

State the assumptions before acting.

### Recommended short prompts

If the user gives only a rough goal, guide with a compact batch like:

- `这轮最重要的是先跑通主路径，还是先优化转化？`
- `对象是 storefront、landing page，还是 app 主流程？`
- `有什么硬限制吗，比如今晚内完成、不接 CMS、不做大改版？`

Then turn the answers into the goal contract internally.

## Core Model

Treat product work as two linked loops:

1. **Inner loop: mechanical**
   - Code, config, deploy, browser flow, analytics wiring, build health
   - Fast feedback
   - Codex can drive this end to end

2. **Outer loop: product**
   - Activation, signup rate, checkout rate, add-to-cart rate, retention, CPA, or other business signals
   - Slower and noisier feedback
   - Codex may choose tactics, but only inside explicit user-set goals and constraints

Never optimize a vague target like "make it successful." Convert it into a goal contract first.

## Goal Calibration Gate

Before locking the goal contract, classify the requested target by maturity.

Use these default bands:

- `demo-ready`: one convincing happy-path demo
- `product-shape-ready`: clear product form, usable main flow, credible cross-surface experience
- `beta-ready`: real users can use it across sessions or devices with acceptable reliability
- `production-ready`: the product is operationally safe to run, monitor, and support

If the user's words imply a higher bar, do not silently downgrade it.

Examples:

- `展示一下` usually implies `demo-ready`
- `像一个真正的商业产品` usually implies at least `beta-ready`
- `生产可用` or `production-ready` implies `production-ready`

If the inferred stop rule is weaker than the requested maturity:

- downgrade the weak rule to a `Stage Gate`
- define a stronger `Stop Rule`
- continue looping

Codex may tighten an inferred contract during execution.
Codex should not weaken an explicit user stop rule just to stop the loop earlier.

## Goal Contract

Before implementation, define:

- `Goal`: the north-star outcome
- `Maturity Target`: `demo-ready`, `product-shape-ready`, `beta-ready`, or `production-ready`
- `Metric`: the number to improve
- `Direction`: whether higher or lower is better
- `Stage Gate`: the current threshold for this phase
- `Scope`: which files or surfaces may change
- `Constraints`: budget, time, brand, legal, tooling, or UX boundaries
- `Stop Rule`: when to stop, pivot, or escalate

If these are missing, gather them or infer the smallest safe version and state the assumptions.

The goal contract is an **internal working contract**, not a form the user must always fill by hand.

Within that contract, Codex is authorized to execute the current round and the later rounds that stay inside the same contract without asking again for each step.

The stage gate is a milestone inside that contract, not the boundary of autonomous action by itself.

The gate stack is:

- `Round Gate`: what the current experiment must prove to be kept
- `Stage Gate`: what the current phase must achieve before promotion
- `Stop Rule`: what ends the whole loop

Never collapse these three into one label.

Ask again only when the next move would exceed the current contract, such as:

- expanding scope beyond the named artifact or agreed scope boundary
- introducing a new external dependency or paid tool not already implied
- changing deployment, data, or infra posture in a meaningful way
- taking a destructive action the user did not already authorize

Read [references/goal-contract.md](references/goal-contract.md) when the goal is still fuzzy or the metric is not mechanical enough.
Read [references/artifact-gates.md](references/artifact-gates.md) when the artifact is clear but the right stage gate is not.
Read [references/maturity-ladders.md](references/maturity-ladders.md) when the user is asking for something like a real product, a beta, or production readiness.

## Default Workflow

### Phase 1: Frame the loop

State:

- assumptions
- maturity target
- success criteria
- current phase goal
- current round gate
- current stage gate
- what will be changed this round
- how this round will be verified

If the user's target is too large, shrink it to the smallest phase that can be verified in one loop.

This is the planning step for the round, not a separate approval gate by default.

Examples:

- Not `launch a winning store`
- Use `get a storefront live with product view -> add to cart -> checkout working`

- Not `build a successful app`
- Use `ship the first usable workflow and confirm the primary action completes`

### Phase 2: Pick the next best experiment

Choose one focused change only.

Prioritize in this order:

1. unblock the core journey
2. add the measurement needed for this phase or the next outer-loop decision
3. make the primary value proposition clearer
4. reduce steps to the main action
5. improve trust and clarity near conversion

If the current round is meant to optimize a business metric and the required instrumentation is missing, add instrumentation before trying to optimize the metric.

Avoid multi-variable changes unless the user explicitly asks for a broader swing.

### Phase 3: Implement minimally

Make the minimum code or config change needed to test the hypothesis.

Default bias:

- prefer existing patterns
- avoid speculative abstractions
- prefer one vertical slice over platform work
- defer CMS, automation, and generalization unless they are on the critical path

### Phase 4: Verify mechanically

Run the fastest relevant checks available, such as:

- build
- lint
- targeted tests
- browser flow checks
- network or API assertions
- analytics/pixel/event confirmation

If the current phase is product-facing but the product metric is slow, use a proxy gate first:

- page loads
- CTA visible
- form submits
- product visible
- cart works
- checkout works
- event fires

Read [references/loop-protocol.md](references/loop-protocol.md) for the full keep-or-discard loop.

### Gate judgment

For every round, evaluate the gate stack in this order:

1. `Round Gate passed?`
2. `Stage Gate advanced?`
3. `Stop Rule satisfied?`

Use this rule:

- if the explicit `Round Gate` is met by mechanical verification, mark `hard pass`
- if the round looks directionally good but still lacks enough evidence for the full gate, mark `soft pass`
- if the round gate is missed, contradicted, or the flow regresses, mark `fail`

Then separately label the stage:

- `stage complete`: the current `Stage Gate` is now met
- `stage in progress`: the round was useful, but the stage is still open
- `stage blocked`: the stage cannot advance without a blocker being removed

The model may synthesize the evidence, but it should not replace the gate stack with vibes.

### Phase 5: Keep or discard

- If the round passes its gate, keep it and summarize what improved
- If the round fails or regresses, discard the approach and say why
- Then choose the next best experiment

By default, continue into the next round after reporting, unless a stop condition has been met.

Do not pretend noisy product signals are conclusive. Mark them as:

- `mechanically verified`
- `needs real traffic`
- `needs more sample`

### Stop-condition judgment

Evaluate `Stop condition hit?` against the explicit goal contract, not against a vague sense that the current round feels complete.

Default rule:

- `stop`: the top-level goal is met or the user-defined `Stop Rule` has been satisfied
- `continue`: the stop rule is not yet met and the next round still fits inside the contract
- `pause and escalate`: the goal is not done, but the loop cannot safely continue because the next move would exceed the contract or a real blocker is present

The model may summarize the result, but it should be applying the preset rule, not inventing a new one.

Before stopping, run a `Stop Audit`:

- Is the current stop claim really about the whole goal, or only the current stage?
- Would a skeptical PM or engineer still say the top-level goal is obviously incomplete?
- Is the current stop rule inferred and obviously weaker than the requested maturity target?
- Are there still critical gaps for the chosen maturity target?

If the answer to any of these is yes, do not stop normally.
Promote the current result to a stage completion, tighten the contract if needed, and continue.

### Remaining Gap Ledger

For targets that imply `beta-ready` or `production-ready`, maintain a lightweight gap ledger before every stop decision.

At minimum, check:

- accounts or identity
- server-side persistence
- cross-device or cross-session continuity
- import or data reliability
- observability and error reporting
- analytics or event visibility
- security and abuse boundaries
- automated verification for the main path

If any of these are still critical to the requested maturity target, the loop is not `goal complete` yet unless the user explicitly narrowed the scope.

## Outer-Loop Rules

When optimizing toward product metrics:

- let Codex pick the path, not the goal
- keep the goal stable long enough to learn
- change one main variable per round
- prefer stage gates over final business outcomes
- use real product metrics only after the inner loop is healthy

Good outer-loop targets:

- `Primary action completion rate`
- `Landing page to signup conversion`
- `Product page to add-to-cart rate`
- `Cart to checkout click-through`

Weak targets:

- `make it good`
- `make it viral`
- `make money fast`

## Storefront vs App

Use the same loop shape for both:

- **Storefront**: hero clarity, product structure, cart, checkout, trust, pricing presentation, event tracking
- **App**: onboarding, first-run success, core action completion, habit loop, activation, retention proxy

If both are possible, prefer the one with fewer external dependencies and cleaner feedback.

## Default first-round outputs

When the user asks for a loop but has not specified the exact round format, respond with:

- `Working Goal`
- `Maturity Target`
- `Current Round Gate`
- `Current Stage Gate`
- `Top-level Stop Rule`
- `Assumptions`
- `This Round`
- `Verification Plan`

This is the start-of-round output, not a pause for approval by default. After that, build immediately, verify, report the result, and continue unless a stop condition has been met.

## Deliverables Per Round

Unless the user asks otherwise, end each substantial round with:

- assumptions
- maturity target
- phase goal
- round plan
- round gate result
- stage gate status
- stop rule status
- remaining gap ledger
- change made
- verification result
- keep/discard decision
- next round chosen

In a continuing run, `next round chosen` means the loop will move into that round automatically unless an explicit stop condition is met or a forced pause is required.

Do not use `next suggested round` as the normal end state of a healthy continuing loop.

If the loop cannot continue right now because of a real blocker or contract boundary, keep `next round chosen` and add:

- `blocked by`
- `resume condition`

## Keep/discard rules

The keep/discard decision must be reflected in the workspace, not just in prose.

- `Keep`: leave the verified change in place
- `Discard`: revert the round's change before ending the round, or avoid applying it if verification failed before the write should be kept

When possible, make the round easy to revert:

- keep the write scope narrow
- avoid bundling unrelated edits
- checkpoint the pre-round state if the change is risky or hard to unwind

Do not say `discard` while leaving the failed experiment sitting in the working tree.

## Round control

Default behavior:

- run a round
- report the outcome
- move into the next round automatically if the stop conditions are not met

Keep looping until one of these happens:

- the top-level goal is met
- the user-defined stop rule is reached

If the next useful move would exceed the stated constraints, or the loop is blocked by missing context, tooling, or a higher-level product decision, do not pretend the goal is done. Pause, report the blocker, and preserve the chosen next round for resumption.

If the current stage gate passes but the top-level goal has not, promote the next stage gate and continue.

If the current stage gate passes but the inferred stop rule was too weak for the requested maturity target, rewrite the stop rule, treat the result as `stage complete`, and continue.

When finishing a continuous run, say which explicit stop condition was satisfied and why the result is `goal complete`, not only `stage complete`.
When pausing a continuous run, say what blocked continuation and what would allow resumption.

## Boundaries

- Do not equate passing tests with product success
- Do not optimize a business metric without instrumentation
- Do not mix large redesigns with fine-grained conversion experiments in the same round
- Do not let the loop expand scope on its own; expand only if the current phase is blocked

## References

- For turning a vague idea into a measurable target: [references/goal-contract.md](references/goal-contract.md)
- For the execution loop and decision rules: [references/loop-protocol.md](references/loop-protocol.md)
- For picking default stage gates by artifact: [references/artifact-gates.md](references/artifact-gates.md)
- For calibrating demo vs beta vs production ambitions: [references/maturity-ladders.md](references/maturity-ladders.md)
- For the visual model of the skill: [references/visual-map.md](references/visual-map.md)
