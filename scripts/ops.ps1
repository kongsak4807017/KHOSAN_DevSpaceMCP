param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('materialize', 'status', 'classify', 'doctor', 'start')]
    [string]$Command,

    [Parameter(Position = 1)]
    [ValidateSet('local', 'web')]
    [string]$Profile = 'local',

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AdditionalArguments
)

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    & python -m ops.cli $Command $Profile @AdditionalArguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
