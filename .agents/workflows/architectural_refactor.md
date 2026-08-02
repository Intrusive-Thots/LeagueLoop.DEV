# Architectural Refactor Guideline

## ⚠️ OBJECTIVE

Ensure the application:
- Works correctly end-to-end
- Matches intended behavior
- Is then optimized without breaking functionality

## 🔷 PHASE 1 — DEFINE EXPECTED SYSTEM BEHAVIOR (NO CODE)

Before touching code, the agent must lock the intended behavior.

### 🧠 SYSTEM MODEL (HOW IT SHOULD WORK)
```
START APP
    ↓
Initialize Config
Initialize State
Initialize Event Bus
Initialize LCU Connection
    ↓
Launch UI (empty/default state)
    ↓
LCU connects
    ↓
LCU emits events (queue, lobby, friends, champ select)
    ↓
EventBus receives events
    ↓
State updates
    ↓
UI reacts to state change (NO polling)
    ↓
User interacts with UI
    ↓
Actions sent to LCU API
    ↓
Loop continues
```

## 🔷 PHASE 2 — SUDO CODE (CORRECT ARCHITECTURE)

This is the reference implementation logic.

**1. APP ENTRY**
```python
main():
    state = AppState()
    bus = EventBus()

    lcu = LCUClient(state, bus)
    ui = MainWindow(state, bus)

    start_thread(lcu.connect)
    ui.start()
```

**2. LCU CLIENT (EVENT SOURCE)**
```python
LCUClient.connect():
    while not connected:
        try connect
    subscribe_to_events()

on_event(event):
    normalized = normalize(event)
    bus.emit(event.type, normalized)
```

**3. STATE MANAGEMENT**
```python
on_event(event):
    if event.type == "queue":
        state.queue = event.data
    if event.type == "friends":
        state.friends = event.data

    bus.emit("state_updated")
```

**4. UI LOGIC (CRITICAL)**
```python
on_state_updated():
    update_queue_display()
    update_friends_list()
    update_champion_grid()
```

**5. USER ACTION FLOW**
```python
on_click_find_match():
    lcu.start_queue()

on_toggle_auto_accept():
    state.auto_accept = not state.auto_accept
```

## 🔷 PHASE 3 — COMPARE AGAINST CURRENT CODE

Agent must audit code and flag violations:

**❌ COMMON PROBLEMS TO FIND**
- UI directly calling API (BAD)
- No central state (BAD)
- Polling loops instead of events (BAD)
- Rebuilding UI every update (BAD)
- Blocking calls in UI thread (CRITICAL FAILURE)
- Mixed responsibilities (UI + logic + API)

**✔ REQUIRED STRUCTURE**
| Layer | Responsibility |
| --- | --- |
| UI | Render only |
| State | Single source of truth |
| Event Bus | Communication |
| LCU Client | External data |

## 🔷 PHASE 4 — DECISION LOGIC (OPTIMAL APPROACH)

Agent must decide:
- If code is: **Working but messy** → refactor
- **Partially broken** → restructure module
- **Fundamentally wrong** → rewrite component

## 🔷 PHASE 5 — SAFE REFACTOR STRATEGY

**Step 1 — Isolate State**
Move all shared data:
```python
state = {
    queue,
    friends,
    champs,
    settings
}
```

**Step 2 — Remove UI Logic**
❌ BAD: `button.click → call API directly`
✔ GOOD: `button.click → emit event → service handles API`

**Step 3 — Replace Polling**
❌ BAD: `while True: check_lcu()`
✔ GOOD: `websocket → event → state update`

**Step 4 — Prevent UI Rebuilds**
❌ BAD: `destroy widgets → recreate`
✔ GOOD: `update existing widgets`

**Step 5 — Thread Safety**
All background updates must use:
`QtCore.QMetaObject.invokeMethod(...)`

## 🔷 PHASE 6 — OPTIMIZATION RULES

ONLY after correctness is verified.

**Performance fixes:**
- Cache icons/images
- Use virtualized lists
- Avoid full layout recalculation
- Batch UI updates
- Use signals (Qt) instead of loops

Example optimization:
```python
if new_state == old_state:
    return
```

## 🔷 PHASE 7 — VALIDATION (MANDATORY)

Agent must verify:

**Functional**
- [ ] Queue start works
- [ ] Auto accept works
- [ ] Friends list updates live
- [ ] Champion selection logic works
- [ ] No crashes on disconnect

**Performance**
- [ ] No UI freezing
- [ ] No unnecessary redraws
- [ ] Events processed in real-time

**Architecture**
- [ ] No direct API calls in UI
- [ ] No polling loops
- [ ] State is single source of truth
- [ ] Events drive updates

## 🔷 FINAL EXECUTION FLOW (TARGET)
```
LCU EVENT
    ↓
EventBus
    ↓
State Update
    ↓
UI Update (minimal diff)
```

## ⚠️ CRITICAL RULE

If ANY part is unclear:
→ Agent must STOP
→ Inspect actual code
→ Not guess

## 🔥 RESULT

After this process:
- System behaves predictably
- UI reflects real state instantly
- Code is modular and maintainable
- Performance improves without breaking logic
