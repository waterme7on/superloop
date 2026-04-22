# Finish Standards

Use this reference when the user's goal sounds broader than a single round and you need to calibrate what "done" should mean.

The rule is simple:

- do not collapse a higher finish standard into a weaker current gate
- if the user did not specify a finish standard, infer the nearest one from their wording
- if the inferred stop rule is weaker than the implied finish standard, tighten it

## Standard bands

### Prototype-ready

This usually means:

- one convincing end-to-end slice is real
- manual setup is acceptable
- local-only state is acceptable
- rough edges are acceptable if the mission is demonstrated clearly

This does not mean:

- stable repeated execution
- safe unattended looping
- operational durability

### Workflow-ready

This usually means:

- the main workflow works consistently enough to use
- the critical checks or smoke coverage exist
- the next operator can understand what to run
- the biggest failure mode is visible

This does not mean:

- safe unattended autonomy
- production-grade observability

### Operator-ready

This usually means:

- the user can hand a bounded mission to the harness with limited oversight
- state survives across turns
- stop reasons are explicit
- budget usage is visible
- the main loop is understandable to another operator

### Production-ready

This usually means:

- the operator-ready requirements are met
- observability is credible
- recovery or rollback is credible
- safety boundaries are explicit
- operational ownership is believable

## Heuristics by wording

- `先做出来`, `先给我一个能看的版本` usually imply `prototype-ready`
- `先把主流程跑通`, `能稳定执行` usually imply `workflow-ready`
- `我希望以后可以放心让它自己跑`, `能交给 agent 自己迭代` usually imply `operator-ready`
- `生产可用`, `production`, `线上可靠` imply `production-ready`

When in doubt, prefer the higher finish standard unless the user has also given hard constraints that clearly force a lower one.

## Stop-audit shortcut

Before stopping, ask:

1. Did we only finish the current gate, or the full finish standard?
2. Are critical gaps still open for this band?
3. Would a skeptical CEO still say the job is unfinished?

If yes, it is not `mission complete` yet.
