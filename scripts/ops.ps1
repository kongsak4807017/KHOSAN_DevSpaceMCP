param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('materialize', 'status', 'doctor', 'start')]
    [string]$Command,

    [Parameter(Position = 1)]
    [ValidateSet('local', 'web')]
    [string]$Profile = 'local'
)

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    & python -m ops.cli $Command $Profile
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
