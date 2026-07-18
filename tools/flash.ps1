<#
    flash.ps1 — one-time USB flash of MicroPython onto the Genesis Mini (ESP32-S3)
    Run from the repo root in an activated venv (see docs/SETUP.md).

    Usage:
      .\tools\flash.ps1 -Port COM5
      .\tools\flash.ps1 -Port COM5 -Firmware .\firmware\ESP32_GENERIC_S3-20240602-v1.23.0.bin

    If -Firmware is omitted, the newest ESP32_GENERIC_S3-*.bin under .\firmware is used.
    Put the board in DOWNLOAD mode first: hold BOOT, tap RESET, release BOOT
    (see docs/FLASH.md).
#>
param(
    [Parameter(Mandatory = $true)][string]$Port,
    [string]$Firmware,
    [int]$Baud = 460800
)

$ErrorActionPreference = "Stop"

if (-not $Firmware) {
    $bin = Get-ChildItem -Path .\firmware -Filter "ESP32_GENERIC_S3-*.bin" -ErrorAction SilentlyContinue |
           Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $bin) {
        Write-Error "No firmware .bin found in .\firmware. Download from https://micropython.org/download/ESP32_GENERIC_S3/ (standard 4MiB build) and place it there, or pass -Firmware."
    }
    $Firmware = $bin.FullName
}

Write-Host "Chip     : esp32s3"
Write-Host "Port     : $Port"
Write-Host "Firmware : $Firmware"
Write-Host ""
Write-Host "Step 1/2: erase_flash" -ForegroundColor Cyan
esptool.py --chip esp32s3 --port $Port erase_flash

Write-Host "Step 2/2: write_flash @ 0x0" -ForegroundColor Cyan
esptool.py --chip esp32s3 --port $Port --baud $Baud write_flash 0 "$Firmware"

Write-Host ""
Write-Host "Done. Tap RESET on the board, then verify the REPL:" -ForegroundColor Green
Write-Host "  mpremote connect $Port repl" -ForegroundColor Green
