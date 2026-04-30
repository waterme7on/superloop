# Superloop Core

Superloop core is independent of the agent host that invokes it.

Core responsibilities:

- normalize the mission contract
- persist run state outside the target workspace
- record rounds and compute `continue`, `pause`, or `stop`
- track round and time budgets
- render timeline and report output
- classify blocked rounds enough to route the next action
- preflight required and optional environment variables before external-service rounds

Host adapters are intentionally thin. They choose install paths, metadata files, and
invocation docs. They should not fork the loop semantics.

State path precedence:

1. `$SUPERLOOP_STATE_HOME`
2. `$SUPERLOOP_HOME/state`
3. host default state path
4. generic fallback `~/.superloop/state`

The Codex adapter keeps legacy `CODEX_HOME` state compatibility. Claude Code uses
`CLAUDE_HOME` instead of silently writing to `.codex`.
