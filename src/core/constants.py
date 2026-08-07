"""
Constants module for LeagueLoop.
Centralizes magic numbers and configuration defaults.
"""

# --- Queue IDs ---
QUEUE_DRAFT = 400
QUEUE_RANKED_SOLO = 420
QUEUE_RANKED_FLEX = 440
QUEUE_ARAM = 450
QUEUE_ARENA = 1700
QUEUE_ARENA_3V6 = 1710

# --- Polling & Timing ---
DOCKING_POLL_INTERVAL = 0.05       # seconds between docking geometry checks
DOCKING_IDLE_INTERVAL = 0.5        # seconds when no client window found
CONNECTION_POLL_INTERVAL = 2.0     # seconds between LCU connection attempts
CONNECTION_ERROR_INTERVAL = 5.0    # seconds to wait after connection error
TICK_SLEEP_DEFAULT = 3.0
TICK_SLEEP_CHAMPSELECT = 1.0
TICK_SLEEP_READYCHECK = 1.0
TICK_SLEEP_LOBBY = 2.0
# In-game: rare LCU polls only (phase exit detection). Heavy polling hurts the CEF client.
TICK_SLEEP_INGAME = 45.0
TICK_SLEEP_SPECTATING = 15.0
TICK_SLEEP_SPECTATING_MAX = 30.0
# LCU WebSocket: allow long quiet periods while the game is running
LCU_WS_STALE_TIMEOUT_S = 45.0
LCU_WS_STALE_TIMEOUT_INGAME_S = 180.0
# HTTP anomaly alerts: sliding window (not lifetime cumulative)
LCU_HTTP_ANOMALY_WINDOW_S = 120.0
LCU_HTTP_ANOMALY_LOG_COOLDOWN_S = 60.0
GEOMETRY_THRESHOLD = 2             # pixels of movement before triggering geometry update
PRIORITY_SWAP_COOLDOWN = 1.0       # seconds between priority sniper swaps

# --- UI Dimensions ---
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 24

SIDEBAR_WIDTH = 300
SIDEBAR_HEIGHT = 500

# --- Layout System ---
PADDING_X = 10
PADDING_Y = 6
SECTION_GAP = 10       # Vertical gap between card containers
CARD_PAD = 10          # Internal card padding (all sides)
INNER_GAP = 6          # Gap between elements inside a card
CARD_RADIUS = 8
ICON_SIZE = 36
ROW_HEIGHT = 36        # Toggle rows, status rows
BTN_HEIGHT = 36        # All action buttons
HEADER_HEIGHT = 40     # Top header / drag area
FOOTER_HEIGHT = 44     # Bottom footer (pinned)
# --- LCU Request ---
LCU_REQUEST_TIMEOUT = 2            # seconds

# --- Asset Manager ---
DDRAGON_DEFAULT_VERSION = "14.1.1"
DOWNLOAD_WORKER_COUNT = 5
PROCESS_SCAN_WARN_THRESHOLD = 0.5  # seconds; log warning if scan is slower

# --- Icon Cache ---
ICON_CACHE_MAX = 300

# --- WebSocket ---
WS_RECONNECT_DELAY = 3.0          # seconds between WS reconnect attempts

# --- Rate Limiter ---
RATE_LIMIT_CAPACITY = 20.0        # max burst tokens
RATE_LIMIT_REFILL = 5.0           # tokens per second
