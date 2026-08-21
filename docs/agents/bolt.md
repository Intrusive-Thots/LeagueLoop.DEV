## 2024-05-24 - String manipulation overhead in UI event loops
**Learning:** High-frequency event handlers like keyboard typing (`_on_key`, `_on_search`) suffer from significant UI thread latency if they perform string manipulations (like `.lower()`) inside loops iterating over O(N) items.
**Action:** Pre-compute and cache normalized string lists or tuples during initialization or data-fetch to eliminate runtime string allocation overhead in these hot-paths.

## 2024-06-03 - O(N^2) list membership checks during drag-and-drop
**Learning:** Checking membership against a list during drag-and-drop operations causes O(N^2) time complexity, leading to severe UI thread stalls when dropping large lists.
**Action:** Pre-convert list comprehensions into sets (Hash Maps) before iterating over dropped items to achieve O(1) membership checks.

## 2024-06-15 - Loop Invariant Code Motion (LICM) for CustomTkinter Render Loops
**Learning:** In CustomTkinter applications, repetitive static token lookups like `get_color` or `get_font` inside UI render loops (e.g., populating a dropdown or rendering a list) cause unnecessary string parsing overhead and micro-allocations on the main thread, leading to potential stuttering.
**Action:** Apply Loop Invariant Code Motion (LICM) to hoist static function calls and repetitive string manipulations outside of iteration loops to avoid redundant recalculations for every rendered element.
## 2026-03-29 - O(1) Tkinter Widget Updates
**Learning:** Iterating over O(N) widgets to call `.configure()` or forcing synchronous layout recalculations with `update_idletasks()` during high-frequency keyboard navigation causes severe UI thread blocking in Tkinter/CustomTkinter.
**Action:** Pass an `old_index` to update only the specific delta (O(1)) and defer `update_idletasks()` away from hot-paths.
## 2024-06-25 - Eager Initialization vs Lazy Caching in Event Loops
**Learning:** Lazy initialization of string caches (like `if "_search_target" not in cmd:`) inside UI event loops still incurs dictionary check and mutation overhead on the hot path, causing micro-stutters during rapid typing.
**Action:** Move cache normalization entirely upstream to the data-fetch or UI initialization phase to achieve pure O(1) lookups in the hot path.

## 2024-10-24 - Debouncing UI Event Handlers
**Learning:** High-frequency event handlers like search input on keystrokes cause severe UI thread latency if they trigger O(N) widget destruction and recreation on every keystroke.
**Action:** Add a debounce timer (e.g. 150ms) to throttle UI updates during rapid typing.
## 2026-03-30 - Optimize Hovered Champion Lookups in High-Frequency UI
**Learning:** High-frequency UI event handlers (like updating hovered champions from LCU data) that perform O(N) list iterations with repeated string `.lower()` allocations on both the target and the list items cause unnecessary CPU overhead and micro-stuttering in Tkinter applications.
**Action:** Optimize O(N) membership checks inside UI loops by pre-caching the lowercase target string and using a short-circuiting generator expression (`any()`) to minimize string allocations.

## 2026-03-31 - Expensive BeautifulSoup parsing blocks background threads
**Learning:** In Python web scrapers, importing and using heavy DOM parsers like `BeautifulSoup` on background threads can still cause CPU spikes that delay the main UI thread, especially when only extracting a simple JSON payload or a small set of known table rows.
**Action:** To optimize Python web scrapers and prevent background thread CPU spikes from blocking the main UI thread, replace heavy DOM parsers (like `BeautifulSoup`) with targeted regular expressions (`re.search` or `re.findall`) when extracting simple JSON payloads or specific known HTML structures.

## 2024-06-25 - Local Data Structure Allocation in High-Frequency Key Events
**Learning:** Re-allocating static data structures (like maps, sets, and lists) inside high-frequency keyboard event handlers (e.g. `_on_key_press` in `HotkeyRecorder`) causes unnecessary heap allocations and garbage collection pressure, leading to micro-stutters during rapid input.
**Action:** Move static data structures (like modifier key maps) to class-level variables or constants to eliminate runtime allocation overhead on the hot path.

## 2026-03-31 - Synchronous Asset Loading in UI Loops
**Learning:** Loading remote assets (like icons or images) synchronously within a UI render loop forces the main thread to wait for the download/read operation to complete. This leads to severe UI thread freezing and rendering stalls, especially when dealing with lists or grids where multiple assets are loaded sequentially.
**Action:** Replace synchronous loading calls (e.g., `get_icon`) with asynchronous equivalents (e.g., `get_icon_async`) inside UI loops. Provide a callback to update the widget safely once the asset is ready, ensuring the main UI thread remains responsive during rendering.

## 2024-06-25 - Loop Invariant Code Motion (LICM) for Dynamic Search Parameters
**Learning:** In UI search loops (like queue resolution), performing string normalization (e.g., `.lower()`) on the static search parameter (like `mode`) inside the loop causes unnecessary string allocation overhead on every iteration.
**Action:** Hoist the static target string's normalization outside the loop. Combine this with a short-circuiting generator expression or O(1) lookups to prevent redundant string allocations on every iteration.
## 2024-06-25 - Eager String Normalization in Data Fetch
**Learning:** Performing string normalizations (like `.lower()`) on dynamic data inside high-frequency UI render loops (e.g. `_render_list`) causes unnecessary string allocations on the main thread, leading to UI stuttering during rapid updates.
**Action:** Move string normalization completely upstream to the background data-fetch phase (e.g. `_fetch_lcu_friends_loop`), caching the normalized string directly in the data payload for O(1) lookups in the UI thread.

## 2026-03-31 - Pseudo-Async Asset Loading in Tkinter
**Learning:** Using `self.after()` to stagger synchronous file I/O operations (like `Image.open()`) in Tkinter/CustomTkinter still blocks the main UI thread during execution, causing severe micro-stutters and rendering stalls when processing lists.
**Action:** Replace pseudo-async staggered calls with truly asynchronous loaders (like `AssetManager.get_icon_async`) that offload I/O to background threads and safely update the widget via a callback, while being careful to pass default arguments (`def cb(img, w=widget)`) to avoid loop-closure bugs.

## 2024-06-25 - LICM for String Normalization in Automation Loops
**Learning:** Performing string normalizations like `.lower()` on a constant target string inside high-frequency automation loops (such as `_perform_arena_synergy` traversing all synergy pairs) causes repetitive O(N) string allocation overhead.
**Action:** Apply Loop Invariant Code Motion (LICM) to hoist the static target string's normalization outside the loop.
