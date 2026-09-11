param(
    [string]$VenvPath = ".venv-0.1.2",
    [string]$RequirementsPath = ""
)

$ErrorActionPreference = "Stop"
Remove-Item Env:PYTHONPATH, Env:PYTHONHOME, Env:BOOK_REPRO_ROOT -ErrorAction SilentlyContinue
$packageRoot = $PSScriptRoot
$environmentPath = if ([System.IO.Path]::IsPathRooted($VenvPath)) {
    [System.IO.Path]::GetFullPath($VenvPath)
} else {
    Join-Path $packageRoot $VenvPath
}
$requirements = if ($RequirementsPath) {
    [System.IO.Path]::GetFullPath($RequirementsPath)
} else {
    Join-Path $packageRoot "locks\requirements-windows.txt"
}
if (Test-Path -LiteralPath $environmentPath) {
    throw "The target environment already exists: $environmentPath"
}

Write-Output "[1/4] Creating virtual environment"
py -3.12 -m venv $environmentPath
if ($LASTEXITCODE -ne 0) { throw "create_venv failed with exit code $LASTEXITCODE" }
$python = Join-Path $environmentPath "Scripts\python.exe"
Write-Output "[2/4] Installing locked local dependencies"
& $python -m pip install --no-index --find-links (Join-Path $packageRoot "vendor\wheels") --require-hashes -r $requirements
if ($LASTEXITCODE -ne 0) { throw "install_dependencies failed with exit code $LASTEXITCODE" }
Write-Output "[3/4] Installing the local project"
& $python -m pip install --no-index --no-build-isolation --no-deps --editable $packageRoot
if ($LASTEXITCODE -ne 0) { throw "install_project failed with exit code $LASTEXITCODE" }
Write-Output "[4/4] Checking the installed environment"
& $python -m book_repro check-env
if ($LASTEXITCODE -ne 0) { throw "check_env failed with exit code $LASTEXITCODE" }
