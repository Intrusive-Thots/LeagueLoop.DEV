---
description: Quick patch — stage, commit, and push a targeted fix to the source repo
---
// turbo-all

# Quick Fix Pipeline

Use this for rapid hotfixes. Commits only modified files (not untracked) with a descriptive message.

## Steps

1. Show what changed:
```powershell
cd c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop
git status -s
```

2. Stage modified files only:
```powershell
git add -u
```

3. Commit with a fix message (agent should generate a descriptive message based on what changed):
```powershell
git commit -m "fix: <description of what was fixed>"
```

4. Push to remote:
```powershell
git push origin master
```
