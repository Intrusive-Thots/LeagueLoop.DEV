---
name: Refresh Assets
description: Clear and rebuild the champion icon asset cache from DDragon
---

# Refresh Assets

## Asset Location
`c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\cache\assets\`

Champion icons follow the naming pattern: `champion_<DDragonKey>.png`

## Steps

1. Clear existing cached assets:
```powershell
Remove-Item "c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\cache\assets\champion_*.png" -Force
```

2. Clear cached data files:
```powershell
Remove-Item "c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\cache\champion.json" -Force -ErrorAction SilentlyContinue
Remove-Item "c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\cache\meraki_champions.json" -Force -ErrorAction SilentlyContinue
```

3. Launch the app — `AssetManager.start_loading()` will automatically re-download everything on startup.

## Notes
- Icons are downloaded from: `https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{key}.png`
- The DDragon version is auto-detected from: `https://ddragon.leagueoflegends.com/api/versions.json`
- If a champion icon is missing, the grid shows a 2-letter abbreviation as fallback.
