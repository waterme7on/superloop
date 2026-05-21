# Install on Windows

Superloop supports Windows through native PowerShell entrypoints. You do not need
WSL or Git Bash for the harness itself.

## Requirements

- Windows 10 or newer
- PowerShell 5.1 or PowerShell 7+
- Python 3.10 or newer on `PATH`

If Python is missing, install it with:

```powershell
winget install Python.Python.3.12
```

Open a new PowerShell session after installation so `python` or `py -3` is on
`PATH`.

## Run from the source checkout

From the Superloop source checkout:

```powershell
.\scripts\superloop_cli.ps1 resume --workspace C:\path\to\repo
.\scripts\superloop_cli.ps1 doctor --host generic --source $PWD
```

If your execution policy blocks local scripts, use one of these:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\superloop_cli.ps1 resume --workspace C:\path\to\repo
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Install for Codex

```powershell
.\scripts\install.ps1 --host codex
.\scripts\install.ps1 --host codex --source $PWD --check
```

The installed path is:

```text
$env:CODEX_HOME\skills\superloop
```

If `CODEX_HOME` is unset, Superloop uses `%USERPROFILE%\.codex`.

Use the installed harness:

```powershell
$env:CODEX_HOME = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
$env:SUPERLOOP_HARNESS = Join-Path $env:CODEX_HOME "skills\superloop\scripts\superloop_cli.ps1"
& $env:SUPERLOOP_HARNESS resume --workspace C:\path\to\repo
```

Codex state defaults to:

```text
$env:CODEX_HOME\state\superloop\<workspace-key>.json
```

## Install for Claude Code

```powershell
.\scripts\install.ps1 --host claude-code
.\scripts\install.ps1 --host claude-code --source $PWD --check
```

The installed path is:

```text
$env:CLAUDE_HOME\skills\superloop
```

If `CLAUDE_HOME` is unset, Superloop uses `%USERPROFILE%\.claude`.

Use the installed harness:

```powershell
$env:CLAUDE_HOME = if ($env:CLAUDE_HOME) { $env:CLAUDE_HOME } else { Join-Path $HOME ".claude" }
$env:SUPERLOOP_HARNESS = Join-Path $env:CLAUDE_HOME "skills\superloop\scripts\superloop_cli.ps1"
& $env:SUPERLOOP_HARNESS resume --workspace C:\path\to\repo
```

Claude Code state defaults to:

```text
$env:CLAUDE_HOME\state\superloop\<workspace-key>.json
```

## Install as a generic CLI

```powershell
.\scripts\install.ps1 --host generic
.\scripts\install.ps1 --host generic --source $PWD --check
```

The installed path is:

```text
$env:SUPERLOOP_HOME\superloop
```

If `SUPERLOOP_HOME` is unset, Superloop uses `%USERPROFILE%\.superloop`.

Use the installed harness:

```powershell
$env:SUPERLOOP_HOME = if ($env:SUPERLOOP_HOME) { $env:SUPERLOOP_HOME } else { Join-Path $HOME ".superloop" }
$env:SUPERLOOP_HARNESS = Join-Path $env:SUPERLOOP_HOME "superloop\scripts\superloop_cli.ps1"
& $env:SUPERLOOP_HARNESS resume --workspace C:\path\to\repo
```

Generic state defaults to:

```text
$env:SUPERLOOP_HOME\state\<workspace-key>.json
```

## Environment overrides

These variables work the same way on Windows as on Linux and macOS:

- `SUPERLOOP_HOME`
- `SUPERLOOP_STATE_HOME`
- `SUPERLOOP_INSTALL_PATH`
- `SUPERLOOP_HOST`
- `CODEX_HOME`
- `CLAUDE_HOME`

Use `SUPERLOOP_STATE_HOME` when you want state files somewhere outside the
default profile directory.
