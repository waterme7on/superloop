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

Windows PowerShell:

```powershell
.\scripts\superloop_cli.ps1 doctor --host auto
.\scripts\superloop_cli.ps1 doctor --host codex
.\scripts\superloop_cli.ps1 doctor --host claude-code
.\scripts\superloop_cli.ps1 doctor --host generic
```

## Codex

- Home: `$CODEX_HOME`, defaulting to `~/.codex`
- Install path: `$CODEX_HOME/skills/superloop`
- State path: `$CODEX_HOME/state/superloop`
- Metadata: `agents/openai.yaml` and `SKILL.md`

`agents/openai.yaml` is intentionally kept as root-level Codex metadata because
Codex skill discovery expects that shape. It is host metadata, not core loop
logic.

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

The implementation is shared through `src/superloop/`; host adapters select
paths and metadata only.

On Windows, use `scripts\superloop_cli.ps1` and `scripts\install.ps1`. The host
paths and state paths are the same logical locations under `%USERPROFILE%`, but
the PowerShell wrappers avoid any dependency on Bash, Git Bash, or WSL.
