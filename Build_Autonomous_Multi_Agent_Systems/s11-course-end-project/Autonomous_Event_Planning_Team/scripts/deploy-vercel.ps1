<#
.SYNOPSIS
  Deploys the backend (FastAPI, app/main.py) and frontend (Next.js,
  front-end/) to Vercel as two separate projects, then wires the frontend's
  NEXT_PUBLIC_API_BASE_URL to the backend's production URL and tightens the
  backend's CORS_ALLOWED_ORIGINS to the frontend's origin.

.NOTES
  Requires `vercel login` already completed in this environment.

  KNOWN LIMITATION: real plan generation observed at 20-140+s against real
  Azure/Gemini calls. Vercel Hobby caps functions at 60s; vercel.json here
  sets maxDuration=60 (Hobby-safe default). If you're on Pro, raise it (up
  to 800s) in vercel.json for a much better chance of full multi-iteration
  runs actually completing before Vercel kills the invocation.

  Idempotent: safe to re-run (env vars are added with --force to overwrite).

  Native `vercel` calls are never redirected with 2>&1/2>$null here - under
  Windows PowerShell 5.1 that wraps each stderr line in a terminating
  NativeCommandError even when the process exits 0. stderr is left to print
  directly to the console; success/failure is checked via $LASTEXITCODE.
#>

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$FrontEndRoot = Join-Path $RepoRoot "front-end"
$EnvFile = Join-Path $RepoRoot ".env"

$BackendProject = "autonomous-event-planning-backend"
$FrontendProject = "autonomous-event-planning-frontend"

# Vercel's default domain for a project with no custom domain attached.
# Deploy-Vercel below returns the ephemeral per-deployment URL (e.g.
# ...-r8nwjvl0w.vercel.app), which sits behind Vercel's SSO deployment
# protection wall even in production. The stable alias below does not, so
# it - not the per-deployment URL - is what real users/CORS/env wiring
# must point at.
$BackendAliasUrl = "https://$BackendProject.vercel.app"
$FrontendAliasUrl = "https://$FrontendProject.vercel.app"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Read-DotEnv($path) {
    $result = @{}
    if (-not (Test-Path $path)) { return $result }
    Get-Content $path | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $key = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim().Trim('"')
        $result[$key] = $value
    }
    return $result
}

# Writes the value to a throwaway temp file and redirects it into stdin via
# cmd.exe, rather than `$Value | vercel ...` or a --value argument. Piping a
# string to a native command's stdin in Windows PowerShell 5.1 prepends a
# UTF-8 BOM and appends a trailing CRLF to whatever the child process reads -
# Vercel stored that verbatim, corrupting every secret (e.g. PRESIDIO_ENABLED
# came back as "﻿alse\r\n", which fails bool parsing at runtime). Since
# the temp file holds the exact bytes and cmd.exe's `<` reads them directly,
# the value never passes through PowerShell's pipeline-to-native-stdin
# serialization, and it never appears in the process command line either.
function Set-VercelEnv($Name, $Value, $Cwd) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return }
    $tmpFile = [System.IO.Path]::GetTempFileName()
    try {
        [System.IO.File]::WriteAllText($tmpFile, $Value, (New-Object System.Text.UTF8Encoding($false)))
        cmd /c "vercel env add $Name production --force --yes --cwd `"$Cwd`" < `"$tmpFile`"" | Out-Null
        $exitCode = $LASTEXITCODE
    } finally {
        Remove-Item $tmpFile -Force -ErrorAction SilentlyContinue
    }
    if ($exitCode -ne 0) {
        Write-Warning "Failed to set $Name (exit code $exitCode)"
        return
    }
    Write-Host "Set $Name (production)"
}

function Deploy-Vercel($Cwd, $Label) {
    $lines = vercel deploy --prod --yes --cwd $Cwd
    $exitCode = $LASTEXITCODE
    $text = ($lines -join "`n")
    Write-Host $text
    if ($exitCode -ne 0) {
        Write-Error "$Label deployment failed (exit code $exitCode). See output above."
        exit 1
    }
    $url = [regex]::Match($text, "https://\S+\.vercel\.app").Value
    if (-not $url) {
        Write-Error "$Label deployment succeeded but no https://*.vercel.app URL was found in the output above."
        exit 1
    }
    return $url
}

# --- 0. Preconditions ---
$who = vercel whoami
if ($LASTEXITCODE -ne 0 -or -not $who) {
    Write-Error "Not logged in to Vercel. Run 'vercel login' first."
    exit 1
}
Write-Host "Logged in as: $who"

$envValues = Read-DotEnv $EnvFile
$maxIterations = if ($envValues["MAX_ITERATIONS"]) { $envValues["MAX_ITERATIONS"] } else { "3" }

# --- 1. Backend: link, configure, deploy ---
Write-Step "Linking backend Vercel project ($BackendProject)"
vercel link --yes --project $BackendProject --cwd $RepoRoot | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to link backend project (exit code $LASTEXITCODE)."
    exit 1
}

Write-Step "Setting backend environment variables"
Set-VercelEnv "AZURE_OPENAI_API_KEY" $envValues["AZURE_OPENAI_API_KEY"] $RepoRoot
Set-VercelEnv "AZURE_OPENAI_ENDPOINT" $envValues["AZURE_OPENAI_ENDPOINT"] $RepoRoot
Set-VercelEnv "AZURE_OPENAI_LLM_DEPLOYMENT" $envValues["AZURE_OPENAI_LLM_DEPLOYMENT"] $RepoRoot
Set-VercelEnv "AZURE_OPENAI_API_VERSION" $envValues["AZURE_OPENAI_API_VERSION"] $RepoRoot
Set-VercelEnv "GEMINI_API_KEY" $envValues["GEMINI_API_KEY"] $RepoRoot
Set-VercelEnv "GEMINI_MODEL_NAME" $envValues["GEMINI_MODEL_NAME"] $RepoRoot
Set-VercelEnv "MAX_ITERATIONS" $maxIterations $RepoRoot
# Avoids Presidio's ~400MB spaCy model download attempt on a cold serverless start.
Set-VercelEnv "PRESIDIO_ENABLED" "false" $RepoRoot
Set-VercelEnv "CORS_ALLOWED_ORIGINS" "*" $RepoRoot

Write-Step "Deploying backend to production"
$backendUrl = Deploy-Vercel -Cwd $RepoRoot -Label "Backend"
Write-Host "Backend URL: $backendUrl" -ForegroundColor Green

# --- 2. Frontend: link, configure, deploy ---
Write-Step "Linking frontend Vercel project ($FrontendProject)"
vercel link --yes --project $FrontendProject --cwd $FrontEndRoot | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to link frontend project (exit code $LASTEXITCODE)."
    exit 1
}

Write-Step "Setting frontend environment variable"
Set-VercelEnv "NEXT_PUBLIC_API_BASE_URL" $BackendAliasUrl $FrontEndRoot

Write-Step "Deploying frontend to production"
$frontendUrl = Deploy-Vercel -Cwd $FrontEndRoot -Label "Frontend"
Write-Host "Frontend URL: $frontendUrl" -ForegroundColor Green

# --- 3. Tighten backend CORS now that the frontend origin is known ---
Write-Step "Tightening backend CORS to the frontend origin and redeploying"
Set-VercelEnv "CORS_ALLOWED_ORIGINS" $FrontendAliasUrl $RepoRoot
$corsLines = vercel deploy --prod --yes --cwd $RepoRoot
if ($LASTEXITCODE -ne 0) {
    Write-Warning "CORS-tightening redeploy failed (exit code $LASTEXITCODE) - backend is still reachable with CORS_ALLOWED_ORIGINS=* from the first deploy."
} else {
    Write-Host ($corsLines -join "`n")
}

# --- 4. Verify ---
Write-Step "Verifying deployment"
try {
    $health = Invoke-RestMethod -Uri "$BackendAliasUrl/health" -TimeoutSec 30
    Write-Host "Backend health: $($health | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Warning "Backend health check failed: $($_.Exception.Message)"
}

Write-Step "Done"
Write-Host "Backend:  $BackendAliasUrl (latest per-deployment URL: $backendUrl)"
Write-Host "Frontend: $FrontendAliasUrl (latest per-deployment URL: $frontendUrl)"
