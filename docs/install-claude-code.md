# Install for Claude Code

From the Superloop source checkout:

```bash
./scripts/install.sh --host claude-code
```

Windows PowerShell:

```powershell
.\scripts\install.ps1 --host claude-code
```

The installer syncs the source tree into:

```text
$CLAUDE_HOME/skills/superloop
```

If `CLAUDE_HOME` is unset, it defaults to `~/.claude`.

Check the install:

```bash
./scripts/superloop_cli.sh doctor --host claude-code --source "$(pwd)"
./scripts/install.sh --host claude-code --source "$(pwd)" --check
```

```powershell
.\scripts\superloop_cli.ps1 doctor --host claude-code --source $PWD
.\scripts\install.ps1 --host claude-code --source $PWD --check
```

Use the installed harness:

```bash
export CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
export SUPERLOOP_HARNESS="$CLAUDE_HOME/skills/superloop/scripts/superloop_cli.sh"
"$SUPERLOOP_HARNESS" resume --workspace /path/to/repo
```

```powershell
$env:CLAUDE_HOME = if ($env:CLAUDE_HOME) { $env:CLAUDE_HOME } else { Join-Path $HOME ".claude" }
$env:SUPERLOOP_HARNESS = Join-Path $env:CLAUDE_HOME "skills\superloop\scripts\superloop_cli.ps1"
& $env:SUPERLOOP_HARNESS resume --workspace C:\path\to\repo
```

Claude Code state is host-specific:

```text
$CLAUDE_HOME/state/superloop/<workspace-key>.json
```

The same `SKILL.md`, `docs/`, `references/`, `src/`, and `scripts/` are used.
The Claude adapter does not depend on Codex-specific `agents/openai.yaml`
metadata.
