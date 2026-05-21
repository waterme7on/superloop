[CmdletBinding()]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$RemainingArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $PSCommandPath
$Harness = Join-Path $ScriptDir "superloop_harness.py"

function Get-SuperloopPython {
  $candidates = @(
    @{ Name = "py"; PrefixArgs = @("-3") },
    @{ Name = "python"; PrefixArgs = @() },
    @{ Name = "python3"; PrefixArgs = @() }
  )

  foreach ($candidate in $candidates) {
    $command = Get-Command $candidate.Name -ErrorAction SilentlyContinue
    if (-not $command) {
      continue
    }

    $probeArgs = @()
    $probeArgs += $candidate.PrefixArgs
    $probeArgs += @(
      "-c",
      "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
    )

    & $command.Source @probeArgs *> $null
    if ($LASTEXITCODE -eq 0) {
      return @{
        File = $command.Source
        PrefixArgs = $candidate.PrefixArgs
      }
    }
  }

  throw "Python 3.10 or newer is required. Install Python from python.org or run: winget install Python.Python.3.12"
}

$Python = Get-SuperloopPython
$PythonArgs = @()
$PythonArgs += $Python.PrefixArgs
$PythonArgs += @($Harness)
$PythonArgs += $RemainingArgs

& $Python.File @PythonArgs
exit $LASTEXITCODE
