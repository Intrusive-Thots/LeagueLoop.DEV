---
name: Read Crash Logs
description: Parse and diagnose LeagueLoop crash logs and error files
---

# Read Crash Logs

## Log File Locations
| File | Purpose |
|------|---------|
| `crash.log` | Fatal crashes and unhandled exceptions |
| `error.log` | Runtime errors logged by Logger.error() |
| `debug.log` | Verbose debug output from all subsystems |

## Steps

1. Check the most recent crash:
```powershell
Get-Content "c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\crash.log" -Tail 50
```

2. Check recent errors:
```powershell
Get-Content "c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\error.log" -Tail 100
```

3. Search for a specific error pattern:
```powershell
Select-String -Path "error.log" -Pattern "PATTERN" -Context 3
```

4. Check debug logs for a specific subsystem:
```powershell
Select-String -Path "debug.log" -Pattern "\[AutoLoop\]" -Context 1 | Select-Object -Last 20
```

## Common Error Patterns
- `ValueError: ... cursor`: Unsupported kwargs in customtkinter widgets. Remove the `cursor` argument.
- `ConnectionRefusedError`: LCU client not running. Check `test_lcu_connection` skill.
- `queue.Empty`: Usually harmless, suppressed by design.
- `TclError`: Widget was destroyed before callback fired. Usually a shutdown race condition.
