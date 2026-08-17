<#
.SYNOPSIS
  Deploys the Autonomous Event Planning backend (FastAPI/uvicorn) and
  frontend (Next.js production build) to local IIS via HttpPlatformHandler.

.DESCRIPTION
  HttpPlatformHandler makes IIS start and supervise each app as a
  persistent, long-lived process (restarting it if it crashes) and
  reverse-proxy each site's requests to it. Unlike serverless platforms,
  the uvicorn process stays alive across requests, so the POST /plans
  BackgroundTasks pattern (app/api/routers/plans.py) and the SQLite-backed
  checkpointer/plan_store keep working exactly as they do in local dev.

  Idempotent: safe to re-run. Requires Administrator privileges.

.PARAMETER BackendOnly
  Deploy only the backend site (e.g. when the frontend is hosted elsewhere,
  such as Vercel, and only the backend needs a persistent local process).
  Skips the front-end/.next check and all frontend IIS setup.

.NOTES
  - Backend site:  EventPlanningBackend,  http://localhost:8080
  - Frontend site: EventPlanningFrontend, http://localhost:3000
  - Both bind to 127.0.0.1 only (not exposed beyond this machine).
  - Run `npm run build` in front-end/ before this script (see front-end/README.md).
#>

param(
    [switch]$BackendOnly
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$FrontEndRoot = Join-Path $RepoRoot "front-end"

$BackendSiteName = "EventPlanningBackend"
$BackendPoolName = "EventPlanningBackendPool"
$BackendPort = 8080

$FrontendSiteName = "EventPlanningFrontend"
$FrontendPoolName = "EventPlanningFrontendPool"
$FrontendPort = 3000

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

# --- 0. Preconditions ---
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "This script must be run as Administrator (right-click PowerShell > Run as administrator)."
    exit 1
}

if (-not $BackendOnly -and -not (Test-Path (Join-Path $FrontEndRoot ".next"))) {
    Write-Error "front-end\.next not found. Run 'npm run build' in front-end\ first (see front-end/README.md)."
    exit 1
}

Import-Module WebAdministration -ErrorAction Stop

# --- 1. Install HttpPlatformHandler if missing ---
# Checked via the DLL on disk, not Get-WebGlobalModule — that cmdlet returns
# an empty result rather than throwing when the module isn't registered, so
# a try/catch around it alone gives a false positive.
Write-Step "Checking HttpPlatformHandler"
$hphInstalled = Test-Path "$env:windir\System32\inetsrv\HttpPlatformHandler.dll"

if ($hphInstalled) {
    Write-Host "HttpPlatformHandler already installed."
} else {
    Write-Host "Installing HttpPlatformHandler from the official Microsoft/IIS.net download..."
    # https://www.iis.net/downloads/microsoft/httpplatformhandler (x64 link)
    $msiUrl = "https://go.microsoft.com/fwlink/?LinkId=690721"
    $msiPath = Join-Path $env:TEMP "httpPlatformHandler_amd64.msi"
    Invoke-WebRequest -Uri $msiUrl -OutFile $msiPath -UseBasicParsing
    $proc = Start-Process msiexec.exe -ArgumentList "/i `"$msiPath`" /quiet /norestart" -Wait -PassThru
    Remove-Item $msiPath -ErrorAction SilentlyContinue
    if ($proc.ExitCode -ne 0) {
        Write-Error "HttpPlatformHandler install failed with exit code $($proc.ExitCode)."
        exit 1
    }
    Write-Host "Restarting IIS to load the new module..."
    iisreset /noforce | Out-Null
    Write-Host "HttpPlatformHandler installed."
}

# --- 1b. Unlock the config sections a site-level web.config needs to write to ---
# By default applicationHost.config locks these (overrideModeDefault="Deny"),
# which otherwise fails with HTTP 500.19 "configuration section cannot be
# used at this path" the moment IIS tries to read either web.config.
Write-Step "Unlocking handlers/httpPlatform config sections"
& "$env:windir\system32\inetsrv\appcmd.exe" unlock config -section:system.webServer/handlers | Out-Null
& "$env:windir\system32\inetsrv\appcmd.exe" unlock config -section:system.webServer/httpPlatform | Out-Null
Write-Host "Unlocked."

# --- 2. Ensure log directories exist (HttpPlatformHandler needs the dir, not just the file) ---
Write-Step "Preparing log directories"
$logDirs = if ($BackendOnly) { @((Join-Path $RepoRoot "logs")) } else { @((Join-Path $RepoRoot "logs"), (Join-Path $FrontEndRoot "logs")) }
foreach ($dir in $logDirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
    Write-Host "OK: $dir"
}

# --- 3. Application pools (No Managed Code — these aren't .NET apps) ---
function Set-AppPool($Name) {
    if (-not (Test-Path "IIS:\AppPools\$Name")) {
        Write-Host "Creating app pool: $Name"
        New-WebAppPool -Name $Name | Out-Null
    } else {
        Write-Host "App pool already exists: $Name"
    }
    Set-ItemProperty "IIS:\AppPools\$Name" -Name managedRuntimeVersion -Value ""
    Set-ItemProperty "IIS:\AppPools\$Name" -Name startMode -Value "AlwaysRunning"
}

Write-Step "Configuring application pools"
Set-AppPool -Name $BackendPoolName
if (-not $BackendOnly) { Set-AppPool -Name $FrontendPoolName }

# --- 4. Sites (bound to loopback only) ---
function Set-Site($SiteName, $PoolName, $PhysicalPath, $Port) {
    if (Get-Website -Name $SiteName -ErrorAction SilentlyContinue) {
        Write-Host "Site already exists: $SiteName (updating path/pool)"
        Set-ItemProperty "IIS:\Sites\$SiteName" -Name physicalPath -Value $PhysicalPath
        Set-ItemProperty "IIS:\Sites\$SiteName" -Name applicationPool -Value $PoolName
    } else {
        Write-Host "Creating site: $SiteName -> http://127.0.0.1:$Port"
        New-Website -Name $SiteName -PhysicalPath $PhysicalPath -Port $Port -IPAddress "127.0.0.1" -ApplicationPool $PoolName | Out-Null
    }
}

Write-Step "Configuring IIS sites"
$defaultSiteState = (Get-Website -Name "Default Web Site" -ErrorAction SilentlyContinue).State
Set-Site -SiteName $BackendSiteName -PoolName $BackendPoolName -PhysicalPath $RepoRoot -Port $BackendPort
if (-not $BackendOnly) { Set-Site -SiteName $FrontendSiteName -PoolName $FrontendPoolName -PhysicalPath $FrontEndRoot -Port $FrontendPort }
# New-Website has a known quirk of stopping unrelated sites — restore Default Web Site's prior state.
if ($defaultSiteState -eq "Started" -and (Get-Website -Name "Default Web Site").State -ne "Started") {
    Start-Website -Name "Default Web Site" -ErrorAction SilentlyContinue
}

# --- 5. Filesystem permissions for the app pool identities ---
Write-Step "Granting filesystem permissions to app pool identities"
icacls "$RepoRoot" /grant ("IIS AppPool\" + $BackendPoolName + ":(OI)(CI)M") /T /Q | Out-Null
if (-not $BackendOnly) { icacls "$FrontEndRoot" /grant ("IIS AppPool\" + $FrontendPoolName + ":(OI)(CI)M") /T /Q | Out-Null }
Write-Host "Done."

# --- 6. Start everything ---
Write-Step "Starting application pools and sites"
Start-WebAppPool -Name $BackendPoolName -ErrorAction SilentlyContinue
Start-Website -Name $BackendSiteName
if (-not $BackendOnly) {
    Start-WebAppPool -Name $FrontendPoolName -ErrorAction SilentlyContinue
    Start-Website -Name $FrontendSiteName
}

Write-Step "Waiting for the apps to warm up"
Start-Sleep -Seconds 10

# --- 7. Health checks ---
Write-Step "Verifying deployment"
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/health" -TimeoutSec 30
    Write-Host "Backend OK: $($health | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Warning "Backend health check failed: $($_.Exception.Message)"
    Write-Warning "Check logs under $RepoRoot\logs\"
}

if (-not $BackendOnly) {
    try {
        $front = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort" -TimeoutSec 30 -UseBasicParsing
        Write-Host "Frontend OK: HTTP $($front.StatusCode)" -ForegroundColor Green
    } catch {
        Write-Warning "Frontend check failed: $($_.Exception.Message)"
        Write-Warning "Check logs under $FrontEndRoot\logs\"
    }
}

Write-Step "Done"
Write-Host "Backend:  http://localhost:$BackendPort"
if (-not $BackendOnly) { Write-Host "Frontend: http://localhost:$FrontendPort" }
