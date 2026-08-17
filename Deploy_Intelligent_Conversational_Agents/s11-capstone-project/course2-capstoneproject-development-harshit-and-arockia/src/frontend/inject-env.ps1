<#
.SYNOPSIS
    Injects frontend environment variables from .env into index.html,
    producing index.dist.html ready to open in a browser or deploy.

.USAGE
    cd src/frontend
    .\inject-env.ps1

    # Use a different env file:
    .\inject-env.ps1 -EnvFile ".env.production"
#>
param(
    [string]$EnvFile = ".env",
    [string]$Source  = "index.html",
    [string]$Output  = "index.dist.html"
)

$dir     = Split-Path -Parent $MyInvocation.MyCommand.Path
$envPath = Join-Path $dir $EnvFile
$srcPath = Join-Path $dir $Source
$outPath = Join-Path $dir $Output

# ── Validate inputs ────────────────────────────────────────────────────────
if (-not (Test-Path $envPath)) { Write-Error "Env file not found: $envPath"; exit 1 }
if (-not (Test-Path $srcPath)) { Write-Error "Source not found: $srcPath";   exit 1 }

# ── Parse .env ─────────────────────────────────────────────────────────────
$vars = @{}
Get-Content $envPath | ForEach-Object {
    $line = ($_ -replace "`r", "").Trim()
    if ($line -and -not $line.StartsWith('#') -and $line -match '^([^=]+?)\s*=\s*(.*)$') {
        $vars[$Matches[1].Trim()] = $Matches[2].Trim()
    }
}

if ($vars.Count -eq 0) {
    Write-Warning "No variables found in $EnvFile"
    exit 1
}

# ── Substitute %%PLACEHOLDERS%% ────────────────────────────────────────────
$html = Get-Content $srcPath -Raw -Encoding UTF8

foreach ($key in $vars.Keys) {
    $placeholder = "%%$key%%"
    if ($html -notlike "*$placeholder*") {
        Write-Warning "  Placeholder $placeholder not found in $Source — skipping"
        continue
    }
    $html = $html -replace [regex]::Escape($placeholder), $vars[$key]
}

# ── Write output ───────────────────────────────────────────────────────────
[System.IO.File]::WriteAllText($outPath, $html, [System.Text.UTF8Encoding]::new($false))

Write-Host ""
Write-Host "Build complete -> $Output" -ForegroundColor Green
Write-Host ""
$vars.Keys | Sort-Object | ForEach-Object {
    Write-Host ("  {0,-22} = {1}" -f "%%$_%%", $vars[$_]) -ForegroundColor Cyan
}
Write-Host ""
Write-Host "Open in browser: file:///$($outPath -replace '\\','/')" -ForegroundColor Yellow
