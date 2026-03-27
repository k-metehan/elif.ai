# update-data.ps1
# Manual data refresh script for elif.ai
# Run from your local machine (Turkish residential IP works best for scrapers)
#
# Usage:
#   .\update-data.ps1              # Refresh all manual data
#   .\update-data.ps1 pharmacies   # Refresh only pharmacies
#   .\update-data.ps1 events       # Refresh only events
#   .\update-data.ps1 push         # Refresh all + git push (triggers Fly deploy)

param(
    [string]$Target = "all"
)

$ErrorActionPreference = "Continue"
$BackendDir = Join-Path $PSScriptRoot "backend"

Write-Host "`n=== elif.ai Manual Data Refresh ===" -ForegroundColor Cyan
Write-Host "Target: $Target"
Write-Host "Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm')`n"

Set-Location $BackendDir

# --- Pharmacies (most reliable scraper) ---
if ($Target -eq "all" -or $Target -eq "pharmacies") {
    Write-Host "[1/4] Pharmacies..." -ForegroundColor Yellow
    python scrape_nobetci.py
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK" -ForegroundColor Green
    } else {
        Write-Host "  FAILED (non-critical)" -ForegroundColor Red
    }
}

# --- Events (may fail if municipality site is down) ---
if ($Target -eq "all" -or $Target -eq "events") {
    Write-Host "[2/4] Events..." -ForegroundColor Yellow
    python scrape_events.py
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK" -ForegroundColor Green
    } else {
        Write-Host "  FAILED (non-critical)" -ForegroundColor Red
    }
}

# --- Water (often blocked by WAF) ---
if ($Target -eq "all" -or $Target -eq "water") {
    Write-Host "[3/4] Water outages..." -ForegroundColor Yellow
    python scrape_water.py
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK" -ForegroundColor Green
    } else {
        Write-Host "  FAILED (source likely blocked)" -ForegroundColor Red
    }
}

# --- Electricity (often blocked by WAF) ---
if ($Target -eq "all" -or $Target -eq "electricity") {
    Write-Host "[4/4] Electricity outages..." -ForegroundColor Yellow
    python scrape_electricity.py
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK" -ForegroundColor Green
    } else {
        Write-Host "  FAILED (source likely blocked)" -ForegroundColor Red
    }
}

Set-Location $PSScriptRoot

# --- Show what changed ---
Write-Host "`n=== Changes ===" -ForegroundColor Cyan
git diff --stat backend/data/

# --- Push if requested ---
if ($Target -eq "push" -or $Target -eq "deploy") {
    Write-Host "`n=== Pushing to GitHub (triggers Fly deploy) ===" -ForegroundColor Cyan
    git add backend/data/*.json
    $hasChanges = git diff --staged --quiet; $LASTEXITCODE -ne 0
    if ($hasChanges) {
        git commit -m "chore: manual data refresh $(Get-Date -Format 'yyyy-MM-dd')"
        git push
        Write-Host "Pushed. Fly will auto-deploy." -ForegroundColor Green
    } else {
        Write-Host "No data changes to push." -ForegroundColor Yellow
    }
}

Write-Host "`nDone.`n" -ForegroundColor Cyan
