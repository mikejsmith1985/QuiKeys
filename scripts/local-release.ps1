<#
.SYNOPSIS
    Bump version, commit, tag, and push a QuiKeys release.
.DESCRIPTION
    Usage: .\scripts\local-release.ps1 <patch|minor|major>

    1. Reads the current version from package.json
    2. Bumps the requested component (patch / minor / major)
    3. Writes the new version back to package.json AND src/config.py
    4. Commits the version files
    5. Creates an annotated git tag vX.Y.Z
    6. Pushes the commit and tag to origin
#>

param(
    [Parameter(Mandatory)]
    [ValidateSet("patch","minor","major")]
    [string]$Bump
)

$ErrorActionPreference = "Stop"

# ── Read current version ─────────────────────────────────────────────
$pkg = Get-Content "$PSScriptRoot\..\package.json" -Raw | ConvertFrom-Json
$current = $pkg.version

if ($current -notmatch '^(\d+)\.(\d+)\.(\d+)$') {
    Write-Error "Cannot parse version '$current' from package.json"
    exit 1
}
$major = [int]$Matches[1]
$minor = [int]$Matches[2]
$patch = [int]$Matches[3]

# ── Compute new version ──────────────────────────────────────────────
switch ($Bump) {
    "major" { $major++; $minor = 0; $patch = 0 }
    "minor" { $minor++; $patch = 0 }
    "patch" { $patch++ }
}
$newVersion = "$major.$minor.$patch"

Write-Host "Releasing $current → $newVersion" -ForegroundColor Cyan

# ── Guard: working tree must be clean ────────────────────────────────
$dirty = git status --porcelain
if ($dirty) {
    Write-Error "Working tree is not clean. Commit or stash changes first."
    exit 1
}

# ── Update package.json ──────────────────────────────────────────────
$pkgPath = "$PSScriptRoot\..\package.json"
$pkgText = Get-Content $pkgPath -Raw
$pkgText = $pkgText -replace '"version":\s*"[^"]+"', "`"version`": `"$newVersion`""
Set-Content $pkgPath -Value $pkgText -NoNewline
Write-Host "  Updated package.json" -ForegroundColor Gray

# ── Update src/config.py ─────────────────────────────────────────────
$cfgPath = "$PSScriptRoot\..\src\config.py"
$cfgText = Get-Content $cfgPath -Raw
$cfgText = $cfgText -replace 'APP_VERSION\s*=\s*"[^"]+"', "APP_VERSION = `"$newVersion`""
Set-Content $cfgPath -Value $cfgText -NoNewline
Write-Host "  Updated src/config.py" -ForegroundColor Gray

# ── Commit & tag ─────────────────────────────────────────────────────
git add "$pkgPath" "$cfgPath"
git commit -m "chore: release v$newVersion`n`nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git tag -a "v$newVersion" -m "Release v$newVersion"

Write-Host "  Committed and tagged v$newVersion" -ForegroundColor Gray

# ── Push ─────────────────────────────────────────────────────────────
git push origin HEAD
git push origin "v$newVersion"

Write-Host "  Pushed commits and tag" -ForegroundColor Gray

# ── GitHub Release ────────────────────────────────────────────────────
# Collect all commits since the previous tag for release notes
$prevTag = git describe --tags --abbrev=0 "v$newVersion^" 2>$null
if ($prevTag) {
    $commitLog = git --no-pager log "$prevTag..v$newVersion" --pretty=format:"- %s" --no-merges |
                 Where-Object { $_ -notmatch '^- chore: release' }
    $notes = "## What's Changed`n`n$($commitLog -join "`n")"
} else {
    $notes = "Initial release v$newVersion"
}

$env:GH_TOKEN = $null   # ensure keyring credential is used, not a stale env token
gh release create "v$newVersion" --title "v$newVersion" --notes $notes

Write-Host ""
Write-Host "✅ Released v$newVersion" -ForegroundColor Green
