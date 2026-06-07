# Windows deployment orchestrator for WEGA Claude.
# Run as Administrator from the repo root:  .\scripts\deploy-windows.ps1
#
# What it does:
#   1. Installs backend + frontend deps.
#   2. Builds the frontend (vite copies frontend/public/web.config into dist).
#   3. Installs node-windows and registers the WegaClaude service.
#   4. Prints the manual IIS steps you still need to perform.

$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$BackendDir = Join-Path $RepoRoot 'backend'
$FrontendDir = Join-Path $RepoRoot 'frontend'
$DistDir = Join-Path $FrontendDir 'dist'

function Section($msg) { Write-Host "`n==> $msg`n" -ForegroundColor Cyan }

Section "Backend deps"
Push-Location $BackendDir
npm install --omit=dev
Pop-Location

Section "Frontend deps + production build"
Push-Location $FrontendDir
npm install
npm run build
Pop-Location

if (-not (Test-Path (Join-Path $DistDir 'web.config'))) {
  Write-Warning "web.config not found in dist after build. Copying from frontend/public..."
  Copy-Item (Join-Path $FrontendDir 'public\web.config') (Join-Path $DistDir 'web.config')
}

Section "Installing node-windows (only used by the install script)"
Push-Location $BackendDir
npm install node-windows --no-save
Pop-Location

Section "Registering Windows service: WegaClaude"
node (Join-Path $RepoRoot 'scripts\install-windows-service.cjs')

Section "Done"
Write-Host @"
Manual IIS configuration still required:

  1. Open IIS Manager.
  2. Add a new Site (or edit Default Web Site):
       Physical path: $DistDir
       Binding:       http (port 80) or https with your cert
  3. Confirm URL Rewrite and Application Request Routing are installed.
     In ARR: Server Proxy Settings → Enable proxy.
  4. Confirm the WebSocket Protocol Windows feature is installed.
  5. Set system environment variables (System Properties → Environment Variables):
       CLAUDE_CODE_OAUTH_TOKEN   (run 'claude setup-token' on this server)
       MCP_*_TOKEN               (any MCP integrations you want available)
       PROJECTS_ROOT=C:\wega-data\projects   (or wherever you want persisted data)
       DB_PATH=C:\wega-data\wega2.db
     Then restart the WegaClaude service:
       Restart-Service WegaClaude
  6. Visit http://<server-hostname>/ — WEGA UI should load.

Logs:
  C:\Windows\System32\config\systemprofile\AppData\Roaming\node-windows\WegaClaude\daemon\
  (node-windows writes service stdout/stderr to .log/.err in this directory)
"@
