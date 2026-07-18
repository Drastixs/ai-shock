<#
    deploy.ps1 — sync project files to the board and (optionally) open the REPL.
    Works over USB (COM port) OR Wi-Fi (device IP) — mpremote treats both the same.

    Usage:
      # Over Wi-Fi (preferred, Phase 1 goal):
      .\tools\deploy.ps1 -Target 192.168.1.42
      # Over USB:
      .\tools\deploy.ps1 -Target COM5
      # Sync then drop into the live REPL:
      .\tools\deploy.ps1 -Target 192.168.1.42 -Repl

    Copies boot.py, main.py, lib/, config/ (incl. device_secrets.toml) to the board.
#>
param(
    [Parameter(Mandatory = $true)][string]$Target,
    [switch]$Repl,
    [switch]$Run
)

$ErrorActionPreference = "Stop"
$conn = "connect $Target"

Write-Host "Deploying to $Target ..." -ForegroundColor Cyan

# Ensure lib/ and config/ dirs exist on the board (ignore 'already exists').
mpremote $conn.Split(" ") fs mkdir :lib      2>$null | Out-Null
mpremote $conn.Split(" ") fs mkdir :config   2>$null | Out-Null

# Top-level entrypoints
mpremote $conn.Split(" ") fs cp boot.py :boot.py
mpremote $conn.Split(" ") fs cp main.py :main.py

# Package files
Get-ChildItem lib\*.py | ForEach-Object {
    mpremote $conn.Split(" ") fs cp $_.FullName ":lib/$($_.Name)"
}
Get-ChildItem config\*.py | ForEach-Object {
    mpremote $conn.Split(" ") fs cp $_.FullName ":config/$($_.Name)"
}
if (Test-Path config\device_secrets.toml) {
    mpremote $conn.Split(" ") fs cp config\device_secrets.toml :config/device_secrets.toml
} else {
    Write-Warning "config/device_secrets.toml missing — copy it from the .example and fill in Wi-Fi."
}

Write-Host "Sync complete." -ForegroundColor Green

if ($Run) {
    mpremote $conn.Split(" ") run main.py
}
if ($Repl) {
    mpremote $conn.Split(" ") repl
}
