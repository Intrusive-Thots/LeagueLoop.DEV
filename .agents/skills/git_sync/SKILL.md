---
name: Git Sync
description: Commit all changes and sync with the remote repository
---

# Git Sync

## Steps

1. Stage all changes (source repo only):
```powershell
cd c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop
git add -A
```

2. Commit with a descriptive message:
```powershell
git commit -m "chore: <description>"
```

3. Pull latest from remote (rebase to keep history clean):
```powershell
git pull --rebase origin master
```

4. If conflicts occur, resolve them, then:
```powershell
git add .
git rebase --continue
```

5. Push to remote:
```powershell
git push origin master
```

## Dual-Repo Sync (after a release)
If the installer was rebuilt, also sync the installer repo:
```powershell
cd c:\Users\Administrator\Desktop\LeagueLoop-Installer
git add -A
git commit -m "chore: sync installer"
git push origin master
```

## Notes
- Always pull before push to avoid rejected pushes.
- Use `--rebase` to keep a linear commit history.
- **NEVER** stage `build/` or `dist/` contents — they corrupt stash/rebase with binary patch errors.
- Source repo: `c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop` → `Intrusive-Thots/LeagueLoop-Lock`
- Installer repo: `c:\Users\Administrator\Desktop\LeagueLoop-Installer` → `Intrusive-Thots/LeagueLoop-Installer`
