# Install for Codex

From the Superloop source checkout:

```bash
./scripts/install.sh --host codex
```

Windows PowerShell:

```powershell
.\scripts\install.ps1 --host codex
```

The installer syncs the source tree into:

```text
$CODEX_HOME/skills/superloop
```

If `CODEX_HOME` is unset, it defaults to `~/.codex`.

Check the install:

```bash
./scripts/superloop_cli.sh doctor --host codex --source "$(pwd)"
./scripts/install.sh --host codex --source "$(pwd)" --check
```

```powershell
.\scripts\superloop_cli.ps1 doctor --host codex --source $PWD
.\scripts\install.ps1 --host codex --source $PWD --check
```

Use the installed harness:

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export SUPERLOOP_HARNESS="$CODEX_HOME/skills/superloop/scripts/superloop_cli.sh"
"$SUPERLOOP_HARNESS" resume --workspace /path/to/repo
```

```powershell
$env:CODEX_HOME = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
$env:SUPERLOOP_HARNESS = Join-Path $env:CODEX_HOME "skills\superloop\scripts\superloop_cli.ps1"
& $env:SUPERLOOP_HARNESS resume --workspace C:\path\to\repo
```

Codex state remains backwards compatible at:

```text
$CODEX_HOME/state/superloop/<workspace-key>.json
```
