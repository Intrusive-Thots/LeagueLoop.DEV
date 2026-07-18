"""
Provides static and dynamic data related to champions and game stats.
"""
import threading
import time
import requests
import re
from concurrent.futures import ThreadPoolExecutor
from utils.logger import Logger

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

# Cache TTL for live-scraped winrates (seconds)
_LIVE_CACHE_TTL = 1800  # 30 minutes

# Baseline ARAM win rates (approximate, sourced from public tier lists).
# Preserved here as an offline database since web scraping was removed.
BASELINE_ARAM_WINRATES = {
    "aatrox": 49.5, "ahri": 52.1, "akali": 49.0, "akshan": 52.8, "alistar": 50.5,
    "amumu": 53.2, "anivia": 51.8, "annie": 50.9, "aphelios": 47.8, "ashe": 52.4,
    "aurelionsol": 51.5, "azir": 46.5, "bard": 50.2, "belveth": 48.0, "blitzcrank": 51.6,
    "brand": 53.0, "braum": 49.0, "briar": 49.8, "caitlyn": 50.3, "camille": 48.5,
    "cassiopeia": 50.6, "chogath": 52.0, "corki": 49.2, "darius": 50.8, "diana": 52.5,
    "draven": 49.4, "drmundo": 53.5, "ekko": 50.0, "elise": 48.3, "evelynn": 47.5,
    "ezreal": 49.8, "fiddlesticks": 52.8, "fiora": 47.6, "fizz": 50.2, "galio": 52.3,
    "gangplank": 49.0, "garen": 52.1, "gnar": 49.5, "gragas": 51.2, "graves": 49.8,
    "gwen": 48.7, "hecarim": 51.0, "heimerdinger": 52.5, "illaoi": 52.8, "irelia": 48.5,
    "ivern": 48.0, "janna": 51.5, "jarvaniv": 50.8, "jax": 50.5, "jayce": 50.0,
    "jhin": 51.2, "jinx": 52.0, "kaisa": 50.5, "kalista": 48.2, "karma": 51.0,
    "karthus": 54.5, "kassadin": 49.8, "katarina": 50.5, "kayle": 51.8, "kayn": 48.5,
    "kennen": 50.0, "khazix": 50.3, "kindred": 49.2, "kled": 50.5, "kogmaw": 54.0,
    "ksante": 47.5, "leblanc": 48.5, "leesin": 49.0, "leona": 51.5, "lillia": 51.0,
    "lissandra": 51.8, "lucian": 50.0, "lulu": 52.0, "lux": 53.0, "malphite": 52.5,
    "malzahar": 52.0, "maokai": 54.0, "masteryi": 50.5, "milio": 52.5, "missfortune": 53.2,
    "mordekaiser": 50.8, "morgana": 52.0, "nami": 52.8, "nasus": 51.5, "nautilus": 50.5,
    "neeko": 52.0, "nidalee": 49.0, "nilah": 51.0, "nocturne": 50.0, "nunu": 49.5,
    "olaf": 50.0, "orianna": 51.5, "ornn": 50.2, "pantheon": 49.8, "poppy": 51.0,
    "pyke": 49.5, "qiyana": 47.0, "quinn": 50.8, "rakan": 49.5, "rammus": 50.0,
    "reksai": 48.5, "rell": 49.0, "renata": 51.5, "renekton": 49.5, "rengar": 48.0,
    "riven": 48.5, "rumble": 52.0, "ryze": 47.0, "samira": 50.5, "sejuani": 51.5,
    "senna": 52.5, "seraphine": 54.0, "sett": 51.0, "shaco": 48.5, "shen": 50.5,
    "shyvana": 51.0, "singed": 50.5, "sion": 53.5, "sivir": 52.0, "skarner": 50.0,
    "smolder": 50.8, "sona": 55.0, "soraka": 53.5, "swain": 53.8, "sylas": 50.0,
    "syndra": 49.5, "tahmkench": 51.0, "taliyah": 50.5, "talon": 49.0, "taric": 52.0,
    "teemo": 53.0, "thresh": 49.5, "tristana": 50.5, "trundle": 51.5, "tryndamere": 49.0,
    "twistedfate": 49.5, "twitch": 51.0, "udyr": 49.5, "urgot": 51.5, "varus": 52.0,
    "vayne": 49.0, "veigar": 54.0, "velkoz": 53.5, "vex": 51.5, "vi": 50.5,
    "viego": 49.5, "viktor": 50.5, "vladimir": 49.8, "volibear": 51.0, "warwick": 51.5,
    "wukong": 50.5, "xayah": 49.5, "xerath": 53.0, "xinzhao": 50.0, "yasuo": 49.0,
    "yone": 49.5, "yorick": 51.5, "yuumi": 48.0, "zac": 52.5, "zed": 48.0,
    "zeri": 47.0, "ziggs": 54.5, "zilean": 53.0, "zoe": 50.0, "zyra": 53.5,
    "aurora": 51.0, "hwei": 50.0, "naafiri": 49.0,
}

_CLEAN_TRANS = str.maketrans("", "", " '.")

# Derived baseline dictionaries for other game modes.
# Ranked tends to be slightly lower (lane matchup pressure), Arena higher (pick power).
BASELINE_RANKED_WINRATES = {k: round(v - 1.5, 1) for k, v in BASELINE_ARAM_WINRATES.items()}
BASELINE_ARENA_WINRATES = {k: round(v + 2.0, 1) for k, v in BASELINE_ARAM_WINRATES.items()}
BASELINE_QUICKPLAY_WINRATES = {k: round(v - 0.5, 1) for k, v in BASELINE_ARAM_WINRATES.items()}

# Queue ID → dataset mapping for dynamic resolution
_QUEUE_DATASET_MAP = {
    # ARAM family
    450: BASELINE_ARAM_WINRATES,     # ARAM
    2400: BASELINE_ARAM_WINRATES,    # ARAM Mayhem
    # Ranked / Draft
    420: BASELINE_RANKED_WINRATES,   # Ranked Solo/Duo
    440: BASELINE_RANKED_WINRATES,   # Ranked Flex
    400: BASELINE_RANKED_WINRATES,   # Draft Pick
    # Arena
    1700: BASELINE_ARENA_WINRATES,   # Arena
    1710: BASELINE_ARENA_WINRATES,   # Arena 3v6
    # Quickplay / Fun modes
    490: BASELINE_QUICKPLAY_WINRATES,  # Quickplay
    900: BASELINE_ARAM_WINRATES,     # URF
    1010: BASELINE_ARAM_WINRATES,    # ARURF
    1300: BASELINE_QUICKPLAY_WINRATES,  # Nexus Blitz
    1020: BASELINE_QUICKPLAY_WINRATES,  # One For All
    1400: BASELINE_QUICKPLAY_WINRATES,  # Ultimate Spellbook
    1900: BASELINE_RANKED_WINRATES,     # League Classic
}


class StatsScraper:
    """Provides base champion stats. Live web scraping legacy has been removed."""

    def __init__(self, mode="ARAM", fetch_live=True):
        """Initializes the StatsScraper."""
        self.mode = mode
        self.fetch_live = fetch_live
        self.win_rates = dict()
        self.live_winrates = dict()
        self._cache_timestamps = dict()
        self._executor = ThreadPoolExecutor(max_workers=2)
        self.set_mode(mode)

    def _fetch_live_data_background(self, mode):
        """Attempt to scrape live win rate data in the background.

        Falls back to baseline data silently if BeautifulSoup is not installed
        or the scrape fails.
        """
        if not self.fetch_live:
            return

        # Check in-memory cache first
        ts = self._cache_timestamps.get(mode)
        if ts and (time.time() - ts) < _LIVE_CACHE_TTL and mode in self.live_winrates:
            return

        if not _HAS_BS4:
            Logger.debug("StatsScraper", "bs4 not installed — using baseline win rates.")
            return

        self._executor.submit(self._scrape_winrates, mode)

    def _scrape_winrates(self, mode):
        """BeautifulSoup fallback scraper for community win rate data."""
        ml = str(mode).lower()
        if "aram" in ml:
            url = "https://lolalytics.com/lol/tierlist/?tier=all&patch=30&mode=aram"
        elif "arena" in ml:
            url = "https://lolalytics.com/lol/tierlist/?tier=all&patch=30&mode=arena"
        else:
            url = "https://lolalytics.com/lol/tierlist/?tier=all&patch=30"

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
            resp = requests.get(url, timeout=12, headers=headers)
            if resp.status_code != 200:
                Logger.debug("StatsScraper", f"Scrape failed (HTTP {resp.status_code}) for {mode}")
                return

            soup = BeautifulSoup(resp.text, "html.parser")

            scraped = {}
            # lolalytics uses data attributes or table rows — attempt common patterns
            # Pattern 1: table rows with champion name + win rate cells
            for row in soup.select("tr"):
                cells = row.find_all("td")
                if len(cells) >= 3:
                    name_cell = cells[0].get_text(strip=True)
                    # Try to find a cell that looks like a percentage (e.g. "52.3%")
                    for cell in cells[1:]:
                        txt = cell.get_text(strip=True).replace("%", "")
                        try:
                            wr = float(txt)
                            if 30.0 <= wr <= 75.0:  # sanity check
                                clean_name = name_cell.translate(_CLEAN_TRANS).lower()
                                if clean_name and len(clean_name) > 1:
                                    scraped[clean_name] = round(wr, 1)
                                break
                        except ValueError:
                            continue

            if scraped and len(scraped) >= 20:
                self.live_winrates[mode] = scraped
                self._cache_timestamps[mode] = time.time()
                Logger.info("StatsScraper", f"Scraped {len(scraped)} live win rates for {mode}")
            else:
                Logger.debug("StatsScraper", f"Scrape yielded too few results ({len(scraped)}) for {mode} — keeping baseline")

        except requests.RequestException as e:
            Logger.debug("StatsScraper", f"Network error during scrape: {e}")
        except Exception as e:
            Logger.debug("StatsScraper", f"Scrape parse error: {e}")

    def set_mode(self, mode):
        """Switch active dataset based on game mode string."""
        self.mode = mode
        ml = str(mode).lower()
        # Item #197: Reference baseline dicts directly instead of copying every time.
        # The automation engine only reads from win_rates, never mutates it.
        if "aram" in ml:
            self.win_rates = BASELINE_ARAM_WINRATES
        elif "arena" in ml:
            self.win_rates = BASELINE_ARENA_WINRATES
        elif "quickplay" in ml or "nexus" in ml or "one for all" in ml or "ultimate" in ml:
            self.win_rates = BASELINE_QUICKPLAY_WINRATES
        else:
            self.win_rates = BASELINE_RANKED_WINRATES
        self._fetch_live_data_background(self.mode)

    def set_mode_by_queue_id(self, queue_id):
        """Switch active dataset by numeric queue ID for precise mode resolution."""
        dataset = _QUEUE_DATASET_MAP.get(queue_id, BASELINE_ARAM_WINRATES)
        self.win_rates = dict(dataset)
        # Update self.mode string so is_offline returns accurate results
        _QUEUE_MODE_NAMES = {
            450: "ARAM", 2400: "ARAM Mayhem", 420: "Ranked Solo/Duo",
            440: "Ranked Flex", 400: "Draft Pick", 1700: "Arena", 1710: "Arena 3v6",
            490: "Quickplay", 900: "URF", 1010: "ARURF",
            1300: "Nexus Blitz", 1020: "One For All", 1400: "Ultimate Spellbook",
            1900: "League Classic",
        }
        self.mode = _QUEUE_MODE_NAMES.get(queue_id, self.mode)
        self._fetch_live_data_background(self.mode)

    def get_winrate(self, champ_name):
        """Look up a champion's win rate depending on mode. Returns 50.0 if completely unknown."""
        # ⚡ Bolt: Fast-path string manipulation.
        # Use str.translate instead of chained .replace calls to perform the cleanup in a single
        # optimized C pass and avoid allocating multiple intermediate strings on the heap.
        clean = champ_name.translate(_CLEAN_TRANS).lower()
        if self.mode in self.live_winrates and clean in self.live_winrates[self.mode]:
            return self.live_winrates[self.mode][clean]
        return self.win_rates.get(clean, 50.0)

    @property
    def is_offline(self) -> bool:
        """Dynamically returns True if operating on local fallback data."""
        return self.mode not in self.live_winrates


_instance = None

def get_stats_scraper(mode="ARAM") -> StatsScraper:
    global _instance
    if _instance is None:
        _instance = StatsScraper(mode)
    return _instance
