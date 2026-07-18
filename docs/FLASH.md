# Phase 1a — Flash MicroPython over USB

One-time step. After this the board runs MicroPython and we never need USB again (except as a fallback).

## 1. Find the COM port

Plug the Genesis Mini into USB-C. Then:

```powershell
mpremote connect list
```

Note the port (e.g. `COM5`). If nothing appears, check Device Manager -> Ports (COM & LPT), and confirm the USB-serial driver from docs/SETUP.md.

## 2. Enter download (bootloader) mode

The ESP32-S3 must be in ROM-download mode to accept a flash:

1. Press and **hold BOOT** (aka IO0).
2. **Tap RESET** (EN) once.
3. **Release BOOT**.

The board is now waiting for `esptool`. Some Genesis Mini revisions with native USB auto-enter download mode from `esptool` without the manual combo — if the flash below starts on its own, you can skip the button dance.

## 3. Flash

```powershell
.\tools\flash.ps1 -Port COM5
```

This runs `erase_flash` then `write_flash 0 <firmware>`. Expected tail:

```
Hash of data verified.
Leaving...
Hard resetting via RTS pin...
```

Manual equivalent, if you prefer:

```powershell
esptool.py --chip esp32s3 --port COM5 erase_flash
esptool.py --chip esp32s3 --port COM5 --baud 460800 write_flash 0 .\firmware\ESP32_GENERIC_S3-*.bin
```

## 4. Verify the REPL

Tap **RESET**, then:

```powershell
mpremote connect COM5 repl
```

You should get the `>>>` prompt. Test:

```python
>>> import sys; print(sys.implementation)
```

It should report `micropython`. Press `Ctrl+]` to exit the REPL.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| No COM port | driver / cable | Use a data USB-C cable (not charge-only); install serial driver |
| `esptool` can't connect | not in download mode | Redo BOOT+RESET combo |
| `A fatal error occurred: MD5 ...` | bad/interrupted write | Re-run; lower `-Baud 115200` |
| REPL blank after reset | wrong firmware variant | Use standard 4 MiB `ESP32_GENERIC_S3`, not octal-SPIRAM |

Next: **docs/DEPLOY.md** (Wi-Fi deploy).
