"""Live smoke test for LootService via LeagueLoop LCUClient."""
from services.api_handler import LCUClient
from services.loot_service import LootService, is_likely_openable, LootItem

lcu = LCUClient()
ok = lcu.connect(silent=True)
print("connected", ok, getattr(lcu, "port", None))
if not ok:
    raise SystemExit(0)

r = lcu.request("GET", "/lol-loot/v1/player-loot", silent=True)
print("status", None if r is None else r.status_code)
if r is not None and r.status_code == 200:
    data = r.json()
    print("total loot entries", len(data) if isinstance(data, list) else type(data))
    if isinstance(data, list):
        for x in data[:30]:
            item = LootItem.from_api(x)
            print(
                f"  count={item.count} type={item.type:16} "
                f"cat={item.display_categories:12} openable={is_likely_openable(item)} "
                f"id={item.loot_id} name={item.name[:40]}"
            )

svc = LootService(lcu)
rows = svc.summarize_openable()
print("openable rows", len(rows))
for row in rows[:20]:
    print(
        f"  {row['count']}x {row['name'][:35]:35} "
        f"will={row['will_open']} key={row['needs_key']}"
    )
