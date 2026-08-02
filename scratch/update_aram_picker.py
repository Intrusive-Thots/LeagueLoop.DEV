import sys
import os
import json
import requests

sys.path.append(r"c:\Users\Administrator\Desktop\LeagueLoop\src")

from services.stats_scraper import BASELINE_ARAM_WINRATES, _CLEAN_TRANS

def main():
    try:
        # Fetch champion.json to get proper display names
        print("Fetching champion.json...")
        r = requests.get("https://ddragon.leagueoflegends.com/cdn/14.1.1/data/en_US/champion.json")
        data = r.json()
        champs = data["data"]

        champ_winrates = []

        for key, info in champs.items():
            name = info["name"]
            clean_name = name.translate(_CLEAN_TRANS).lower()
            
            # Check if we have winrate
            wr = BASELINE_ARAM_WINRATES.get(clean_name)
            if wr is None:
                # Fallback to check key
                clean_key = key.translate(_CLEAN_TRANS).lower()
                wr = BASELINE_ARAM_WINRATES.get(clean_key, 50.0)
                
            champ_winrates.append((name, wr))

        # Sort by winrate descending
        champ_winrates.sort(key=lambda x: x[1], reverse=True)

        # Update config.json
        config_path = r"c:\Users\Administrator\Desktop\LeagueLoop\config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        config["priority_picker"]["list"] = [x[0] for x in champ_winrates]

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

        print("Done. Top 5:", [x[0] for x in champ_winrates[:5]])
        print("Bottom 5:", [x[0] for x in champ_winrates[-5:]])
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
