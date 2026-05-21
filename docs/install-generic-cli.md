# Install for Generic CLI

Superloop can run directly from the source checkout:

```bash
./scripts/superloop_cli.sh resume --workspace /path/to/repo
```

Windows PowerShell:

```powershell
.\scripts\superloop_cli.ps1 resume --workspace C:\path\to\repo
```

To install a generic copy under `~/.superloop/superloop`:

```bash
./scripts/install.sh --host generic
```

```powershell
.\scripts\install.ps1 --host generic
```

Check the install:

```bash
./scripts/superloop_cli.sh doctor --host generic --source "$(pwd)"
./scripts/install.sh --host generic --source "$(pwd)" --check
```

```powershell
.\scripts\superloop_cli.ps1 doctor --host generic --source $PWD
.\scripts\install.ps1 --host generic --source $PWD --check
```

Use the installed harness:

```bash
export SUPERLOOP_HOME="${SUPERLOOP_HOME:-$HOME/.superloop}"
export SUPERLOOP_HARNESS="$SUPERLOOP_HOME/superloop/scripts/superloop_cli.sh"
"$SUPERLOOP_HARNESS" resume --workspace /path/to/repo
```

```powershell
$env:SUPERLOOP_HOME = if ($env:SUPERLOOP_HOME) { $env:SUPERLOOP_HOME } else { Join-Path $HOME ".superloop" }
$env:SUPERLOOP_HARNESS = Join-Path $env:SUPERLOOP_HOME "superloop\scripts\superloop_cli.ps1"
& $env:SUPERLOOP_HARNESS resume --workspace C:\path\to\repo
```

Generic CLI state defaults to:

```text
$SUPERLOOP_HOME/state/<workspace-key>.json
```
