# Workstream Gates

Use this reference when the user has named the workstream but has not given a precise current gate yet.

The rule is simple:

- pick the nearest gate that can be mechanically verified now
- prefer a working end-to-end slice before optimization
- if the mission depends on missing observability, add the observability gate before trying to optimize
- when a gate passes, promote the next gate instead of stopping the loop unless the mission is already complete

## Repo feature or code path

Default gate progression:

1. the target code path runs without crashing
2. the main change is visible or observable
3. the targeted checks pass
4. the failure path is understandable
5. only then optimize quality, speed, or polish

Good gate examples:

- `The command runs once without manual rescue`
- `The feature works on the main happy path and the targeted smoke check passes`
- `The failure mode is logged clearly enough to debug on the next round`

## Tooling or automation

Default gate progression:

1. setup succeeds
2. the tool runs once end to end
3. the output is stable and in the right place
4. the most important failure mode is visible
5. only then improve ergonomics or speed

Good gate examples:

- `A fresh machine can run the setup once without undocumented steps`
- `The automation completes once and produces the expected output`
- `The command exits with a clear message when the dependency is missing`

## Agent workflow or harness

Default gate progression:

1. init or resume works
2. one round can be recorded
3. continue or pause decisions are explicit
4. budget stop conditions work
5. only then improve delegation quality or heuristics

Good gate examples:

- `The harness can resume state from disk and choose the recorded next round`
- `A round record produces an unambiguous continue, pause, or stop verdict`
- `The loop stops when max rounds or the timebox is reached`

## Docs, research, or handoff

Default gate progression:

1. the deliverable exists in the right path and format
2. the main conclusion or handoff is explicit
3. evidence or references are attached
4. next steps or decisions are clear
5. only then optimize tone or presentation

Good gate examples:

- `The handoff doc exists and the major decisions are explicit`
- `The research note contains evidence, synthesis, and next actions`
- `The README is enough for a fresh operator to start`

## Deployment or operations

Default gate progression:

1. the service starts
2. the health check passes
3. logs or traces are visible
4. rollback or recovery is known
5. only then optimize throughput or polish

Good gate examples:

- `The service boots and the health endpoint responds`
- `A failed deploy leaves behind enough information to recover`
- `Rollback is documented and the main smoke check passes after deploy`

## Selection heuristics

If several gates are possible, prefer:

1. the one closest to the mission
2. the one with the least external dependency
3. the one that can be verified today

Avoid these mistakes:

- choosing a vague final outcome as the first gate
- optimizing polish before the main path works
- trying to improve the loop before the core workflow can be observed
- adding observability only after several opaque rounds
