# FolioSentry Windows launcher: invoke Linux/WSL2 local CI without Cursor Agent.
# PowerShell 5.1+; never changes the source checkout, GitHub, Docker, or DB.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string]$ExpectedSha,

    [ValidateSet('offline', 'full')]
    [string]$Mode = 'offline',

    [switch]$InstallDeps
)

$ErrorActionPreference = 'Stop'

if ($InstallDeps -and $Mode -ne 'full') {
    throw 'LOCAL_CI_INSTALL_DEPS_ONLY_WITH_FULL'
}
$Wsl = Get-Command 'wsl.exe' -ErrorAction SilentlyContinue
if (-not $Wsl) {
    throw 'LOCAL_CI_WSL2_REQUIRED: Windows native Python cannot validate Linux fcntl/KIS'
}
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$LinuxPath = (& $Wsl.Source -- wslpath -a -u $Repo 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($LinuxPath -join ''))) {
    throw 'LOCAL_CI_WSL_PATH_UNAVAILABLE'
}
$LinuxPath = ($LinuxPath | Select-Object -First 1).Trim()

# WSL direct-process invocation does not load the user's nvm Node PATH.
# Source nvm in Linux before calling Python; never use the Windows npm shim.
$BashScript = 'NVM_DIR="$HOME/.nvm"; if [ -s "$NVM_DIR/nvm.sh" ]; then . "$NVM_DIR/nvm.sh"; fi; exec python3 -B scripts/ci/local_gate.py --expected-sha "$1" --mode "$2" "${@:3}"'
$ArgsToWsl = @(
    '--cd', $LinuxPath, '--', 'bash', '-lc', $BashScript,
    'folio-local-ci', $ExpectedSha, $Mode
)
if ($InstallDeps) {
    $ArgsToWsl += '--install-deps'
}
Write-Host 'FOLIOSENTRY_WINDOWS_LAUNCHER=WSL2_TEMP_SNAPSHOT'
& $Wsl.Source @ArgsToWsl
$Status = $LASTEXITCODE
if ($Status -ne 0) {
    Write-Error "FOLIOSENTRY_WINDOWS_LOCAL_CI_FAIL_EXIT=$Status"
    exit $Status
}
Write-Host 'FOLIOSENTRY_WINDOWS_LOCAL_CI_LAUNCH_COMPLETE'
