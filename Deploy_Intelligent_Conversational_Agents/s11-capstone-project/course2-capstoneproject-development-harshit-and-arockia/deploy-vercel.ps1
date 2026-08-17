<#
.SYNOPSIS
    Deploys the Job Placement Agent (FastAPI backend + HTML frontend) to Vercel.

.DESCRIPTION
    This script automates the full Vercel deployment pipeline:
      1. Checks Node.js and Vercel CLI (installs CLI if missing)
      2. Verifies Vercel authentication (prompts login if needed)
      3. Reads backend/.env and pushes every variable to the Vercel project
      4. Deploys the backend (FastAPI) to production
      5. Injects the live backend URL into frontend/index.html and frontend/.env
      6. Deploys the frontend (HTML/JS) to production
      7. Prints a full deployment summary

.NOTES
    Run from the project root (no admin required):
        .\deploy-vercel.ps1

    Prerequisites:
        - Node.js  : https://nodejs.org  (Vercel CLI is installed via npm)
        - Vercel account : https://vercel.com/signup (free)

    The script skips any .env values that still contain placeholder text
    (e.g. "your_", "REPLACE_"). Update those in backend/.env first.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Paths ─────────────────────────────────────────────────────────────────────
$ProjectRoot = Split-Path -Parent $PSCommandPath
$SrcDir      = Join-Path $ProjectRoot "src"
$BackendDir  = Join-Path $SrcDir "backend"
$FrontendDir = Join-Path $SrcDir "frontend"
$BackendEnv  = Join-Path $BackendDir  ".env"
$FrontendEnv = Join-Path $FrontendDir ".env"

# ── Helpers ───────────────────────────────────────────────────────────────────
function Write-Step { param($msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "    [OK]  $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "    [!!]  $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "`n    [ERR] $msg" -ForegroundColor Red; exit 1 }

function Parse-EnvFile {
    <# Returns an ordered hashtable of KEY=VALUE pairs from a .env file.
       Comments (#) and blank lines are skipped. #>
    param([string]$Path)
    $vars = [ordered]@{}
    if (-not (Test-Path $Path)) { return $vars }
    foreach ($line in (Get-Content $Path)) {
        $line = $line.Trim()
        if (-not $line -or $line.StartsWith('#')) { continue }
        if ($line -match '^([^=]+)=(.*)$') {
            $key   = $Matches[1].Trim()
            $value = $Matches[2].Trim().Trim('"').Trim("'")
            $vars[$key] = $value
        }
    }
    return $vars
}

function Get-VercelUrl {
    <# Extracts the production URL from vercel CLI output lines. #>
    param([string[]]$Lines)
    $url = ""
    foreach ($line in $Lines) {
        if ($line -match "Aliased:\s+(https://\S+)") {
            return $Matches[1].Trim()
        }
        if ($line -match "Production:\s+(https://\S+)") {
            $url = $Matches[1].Trim()   # keep scanning for Aliased
        }
    }
    return $url
}

# ── Step 1 : Node.js ──────────────────────────────────────────────────────────
Write-Step "Checking Node.js"
try {
    $nodeVer = node --version 2>&1
    Write-OK "Node.js $nodeVer found."
} catch {
    Write-Fail "Node.js not found. Install it from https://nodejs.org/ and re-run."
}

# ── Step 2 : Vercel CLI ───────────────────────────────────────────────────────
# Helper: run an external command, capturing ALL output as plain strings.
# Vercel CLI writes to stderr; 2>&1 turns that into ErrorRecord objects.
# Wrapping in $EA=Continue + ForEach {"$_"} converts everything to strings safely.
function Invoke-External {
    param([scriptblock]$Cmd)
    $saved = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $out = @(& $Cmd 2>&1 | ForEach-Object { "$_" } | Where-Object { $_.Trim() -ne "" })
    $ErrorActionPreference = $saved
    return $out
}

Write-Step "Checking Vercel CLI"
$vercelCheck = @(Invoke-External { vercel --version })
if ($LASTEXITCODE -ne 0 -or $vercelCheck.Count -eq 0) {
    Write-Warn "Vercel CLI not found. Installing via npm..."
    Invoke-External { npm install -g vercel } | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Fail "npm install -g vercel failed. Check your npm installation." }
    Write-OK "Vercel CLI installed."
} else {
    Write-OK "Vercel CLI $($vercelCheck[0])"
}

# ── Step 3 : Authentication ───────────────────────────────────────────────────
Write-Step "Checking Vercel authentication"
$whoamiOutput = @(Invoke-External { vercel whoami })
if ($LASTEXITCODE -ne 0 -or $whoamiOutput.Count -eq 0) {
    Write-Warn "Not logged in. Launching Vercel login flow..."
    vercel login
    if ($LASTEXITCODE -ne 0) { Write-Fail "Vercel login failed." }
    $whoamiOutput = @(Invoke-External { vercel whoami })
}
$username = ($whoamiOutput | Where-Object { $_ -match '\w' } | Select-Object -Last 1)
if ($username) { $username = $username.Trim() } else { $username = "unknown" }
Write-OK "Authenticated as: $username"

# ── Step 4 : Push backend environment variables ───────────────────────────────
Write-Step "Pushing backend environment variables to Vercel"

if (-not (Test-Path $BackendEnv)) {
    Write-Warn "backend/.env not found - skipping env var push."
} else {
    $envVars     = Parse-EnvFile -Path $BackendEnv
    $placeholders = @("your_", "replace_", "changeme", "example")
    $skipped     = 0
    $pushed      = 0

    Push-Location $BackendDir
    # Lower error pref for the whole loop - vercel CLI writes to stderr
    $savedPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    foreach ($kv in $envVars.GetEnumerator()) {
        # Skip placeholder / unset values
        $isPlaceholder = $false
        foreach ($ph in $placeholders) {
            if ($kv.Value.ToLower() -like "*$ph*") { $isPlaceholder = $true; break }
        }
        if ($isPlaceholder) {
            Write-Warn "  Skipping $($kv.Key)  (placeholder - update backend/.env first)"
            $skipped++
            continue
        }

        # Remove existing variable (ignore error - it may not exist yet)
        vercel env rm $kv.Key production --yes 2>&1 | Out-Null

        # Strip CR/LF before piping — PowerShell on Windows adds \r\n to piped
        # strings; Vercel CLI strips \n but keeps \r, corrupting URL-valued vars.
        $cleanValue = ($kv.Value -replace "`r|`n", "").Trim()

        # Push new value (pipe value as stdin to vercel env add)
        Write-Host "    Pushing $($kv.Key) ..." -NoNewline
        $cleanValue | vercel env add $kv.Key production 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host " ok" -ForegroundColor Green
            $pushed++
        } else {
            Write-Host " FAILED" -ForegroundColor Yellow
        }
    }
    $ErrorActionPreference = $savedPref
    Pop-Location

    Write-OK "$pushed variable(s) pushed to Vercel.$(if ($skipped) { "  $skipped skipped (placeholder)." })"
}

# ── Step 5 : Deploy backend ───────────────────────────────────────────────────
Write-Step "Deploying backend (FastAPI) to Vercel"

Push-Location $BackendDir
$backendOutput = @(Invoke-External { vercel --prod --yes })
$backendExitCode = $LASTEXITCODE
Pop-Location

if ($backendExitCode -ne 0) {
    Write-Fail "Backend deployment failed.`n$($backendOutput -join "`n")"
}

$BackendUrl = Get-VercelUrl -Lines $backendOutput
if ($BackendUrl) {
    Write-OK "Backend live at: $BackendUrl"
} else {
    Write-Warn "Could not auto-detect backend URL - check your Vercel dashboard."
    $BackendUrl = Read-Host "  Enter the backend URL manually (or press Enter to skip)"
}

# ── Step 6 : Push frontend environment variables to Vercel ────────────────────
# The frontend build (node build.js) reads these from Vercel env vars at build
# time and injects them into index.html — nothing is hardcoded in source.
Write-Step "Pushing frontend environment variables to Vercel"

# Collect Auth0 values from backend/.env (single source of truth)
$backendVars = Parse-EnvFile -Path $BackendEnv

$resolvedBackendUrl = if ($BackendUrl) { $BackendUrl } else { $backendVars["BACKEND_URL"] }
$frontendVars = [ordered]@{
    "BACKEND_URL"     = $resolvedBackendUrl
    "AUTH0_DOMAIN"    = $backendVars["AUTH0_DOMAIN"]
    "AUTH0_CLIENT_ID" = $backendVars["AUTH0_CLIENT_ID"]
    "AUTH0_AUDIENCE"  = $backendVars["AUTH0_AUDIENCE"]
}

Push-Location $FrontendDir
$savedPref = $ErrorActionPreference
$ErrorActionPreference = "Continue"

foreach ($kv in $frontendVars.GetEnumerator()) {
    if (-not $kv.Value) {
        Write-Warn "  Skipping $($kv.Key) - value is empty (check backend/.env)"
        continue
    }
    vercel env rm $kv.Key production --yes 2>&1 | Out-Null
    $cleanValue = ($kv.Value -replace "`r|`n", "").Trim()
    Write-Host "    Pushing $($kv.Key) ..." -NoNewline
    $cleanValue | vercel env add $kv.Key production 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ok" -ForegroundColor Green
    } else {
        Write-Host " FAILED" -ForegroundColor Yellow
    }
}

$ErrorActionPreference = $savedPref
Pop-Location

# Also update frontend/.env so inject-env.ps1 works locally
$envContent  = "# =============================================`r`n"
$envContent += "# Job Placement Agent - Frontend Environment`r`n"
$envContent += "# =============================================`r`n`r`n"
$envContent += "# --- Backend API URL ---`r`n"
$envContent += "BACKEND_URL=$($frontendVars["BACKEND_URL"])`r`n`r`n"
$envContent += "# --- Auth0 (public values - safe for browser) ---`r`n"
$envContent += "AUTH0_DOMAIN=$($frontendVars["AUTH0_DOMAIN"])`r`n"
$envContent += "AUTH0_CLIENT_ID=$($frontendVars["AUTH0_CLIENT_ID"])`r`n"
$envContent += "AUTH0_AUDIENCE=$($frontendVars["AUTH0_AUDIENCE"])`r`n"
Set-Content -Path $FrontendEnv -Value $envContent -NoNewline
Write-OK "frontend/.env updated for local development"

# ── Step 7 : Deploy frontend ──────────────────────────────────────────────────
Write-Step "Deploying frontend (HTML/JS) to Vercel"

Push-Location $FrontendDir
$frontendOutput  = @(Invoke-External { vercel --prod --yes })
$frontendExitCode = $LASTEXITCODE
Pop-Location

if ($frontendExitCode -ne 0) {
    Write-Fail "Frontend deployment failed.`n$($frontendOutput -join "`n")"
}

$FrontendUrl = Get-VercelUrl -Lines $frontendOutput
if ($FrontendUrl) {
    Write-OK "Frontend live at: $FrontendUrl"
} else {
    Write-Warn "Could not auto-detect frontend URL - check your Vercel dashboard."
}

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "  Vercel Deployment Complete!" -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
Write-Host ""
if ($FrontendUrl) { Write-Host "  Chat UI   : $FrontendUrl"       -ForegroundColor Cyan }
if ($BackendUrl)  {
    Write-Host "  API       : $BackendUrl"                         -ForegroundColor Cyan
    Write-Host "  API Docs  : $BackendUrl/docs"                    -ForegroundColor Cyan
}
Write-Host "  Dashboard : https://vercel.com/$username"           -ForegroundColor White
Write-Host ""

# Warn about any remaining placeholders
$envVarsCheck = Parse-EnvFile -Path $BackendEnv
$missing = @()
if ($envVarsCheck["SERPAPI_API_KEY"]     -like "*your_*") { $missing += "SERPAPI_API_KEY" }
if ($envVarsCheck["AUTH0_CLIENT_SECRET"] -like "*your_*") { $missing += "AUTH0_CLIENT_SECRET" }

if ($missing.Count -gt 0) {
    Write-Host "  Action required - update these in backend/.env, then re-run this script:" `
               -ForegroundColor Yellow
    foreach ($m in $missing) {
        Write-Host "    * $m" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "  SERPAPI_API_KEY   -> https://serpapi.com (free tier available)" -ForegroundColor White
    Write-Host "  AUTH0_CLIENT_SECRET -> Auth0 dashboard -> Applications -> Settings" `
               -ForegroundColor White
    Write-Host ""
}
