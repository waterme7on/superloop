[CmdletBinding()]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$RemainingArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $PSCommandPath
$Cli = Join-Path $ScriptDir "superloop_cli.ps1"

& $Cli "install" @RemainingArgs
exit $LASTEXITCODE
