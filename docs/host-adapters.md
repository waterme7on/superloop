# Host Adapters

Superloop supports three host modes:

- `codex`
- `claude-code`
- `generic`

Use `auto` when the harness should infer the host from the installed script path.

```bash
./scripts/superloop_cli.sh doctor --host auto
./scripts/superloop_cli.sh doctor --host codex
./scripts/superloop_cli.sh doctor --host claude-code
./scripts/superloop_cli.sh doctor --host generic
```

## Codex

- Home: `$CODEX_HOME`, defaulting to `~/.codex`
- Install path: `$CODEX_HOME/skills/superloop`
- State path: `$CODEX_HOME/state/superloop`
- Metadata: `agents/openai.yaml` and `SKILL.md`

## Claude Code

- Home: `$CLAUDE_HOME`, defaulting to `~/.claude`
- Install path: `$CLAUDE_HOME/skills/superloop`
- State path: `$CLAUDE_HOME/state/superloop`
- Metadata: `SKILL.md`

## Generic CLI

- Home: `$SUPERLOOP_HOME`, defaulting to `~/.superloop`
- Install path: `$SUPERLOOP_HOME/superloop`
- State path: `$SUPERLOOP_HOME/state`
- Metadata: none required

## Compatibility

Existing Codex commands continue to work. New documentation should prefer
`SUPERLOOP_HOME`, `SUPERLOOP_STATE_HOME`, or the selected host adapter instead of
presenting `CODEX_HOME` as the universal default.
