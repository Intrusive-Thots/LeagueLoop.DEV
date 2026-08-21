## 2024-05-15 - Missing hover affordances on buttons
**Learning:** In CustomTkinter applications, custom `CTkButton` components and elements acting as buttons often lack standard hover affordances. Without `cursor="hand2"`, users don't get immediate feedback that an element is clickable, leading to poor accessibility.
**Action:** Always apply `cursor="hand2"` to interactive elements to ensure clear click/drag usability.
## 2024-03-28 - CTkOptionMenu Affordances
**Learning:** In CustomTkinter, `CTkOptionMenu` components (dropdowns) do not automatically provide a change in the cursor (e.g., to a pointing hand) when hovered, unlike standard web buttons or links. This omission can make it slightly less obvious that the element is clickable and interactive, particularly when styled to blend into the application background.
**Action:** Always ensure `cursor="hand2"` is explicitly passed to `CTkOptionMenu` instances alongside other interactive widgets like `CTkButton` to maintain clear affordance and consistent visual UX cues across the application.
## 2024-05-18 - RiotButton Affordance
**Learning:** In CustomTkinter, custom components that behave as interactive buttons (like `RiotButton`, built by composing `CTkFrame` and `CTkLabel`) lack standard hover affordances. The mouse cursor does not naturally change to a pointing hand, which reduces the immediate visual cue that the element is clickable.
**Action:** Always manually apply `cursor="hand2"` to the parent frame and all its relevant inner composite components to maintain clear and accessible clickability affordances.
## 2026-03-29 - Interactive Label Affordances
**Learning:** In CustomTkinter, `CTkLabel` elements acting as buttons or toggles (like collapsible section headers) do not inherently provide hover affordances. Without explicitly setting `cursor="hand2"` and text color hover states, users lack the visual cue that the element is interactive.
**Action:** Always apply explicit cursor and hover color bindings to interactive labels to ensure accessibility and intuitive UX.
## 2024-05-19 - Keyboard Shortcut Discoverability
**Learning:** Users often miss global hotkeys because they are hidden within the settings menu. Adding dynamic keyboard shortcut hints directly to the tooltips of corresponding UI buttons significantly improves hotkey discoverability and overall keyboard accessibility without cluttering the main interface.
**Action:** Always append keyboard shortcut hints (e.g., `(CTRL+SHIFT+X)`) to the tooltips of interactive elements that are bound to global hotkeys.

## 2024-03-31 - Actionable Configuration Errors
**Learning:** Generic error states like "Invalid" in configuration inputs (like HotkeyRecorder) fail to provide guidance. Users need to know *why* it failed (e.g., only modifiers were pressed).
**Action:** Always provide actionable micro-copy (e.g., "! Needs a key") and sufficient display duration (1200ms) for temporary error states.
## 2026-03-31 - Keyboard Accessibility on CustomTkinter Settings
**Learning:** High-density configuration modals using CustomTkinter buttons for hotkey recording severely limit keyboard users because they lack default focus rings and space/enter activation.
**Action:** Explicitly bind <FocusIn>, <FocusOut>, <KeyPress-space>, and <KeyPress-Return> to interactive elements like HotkeyRecorder to guarantee WCAG-compliant keyboard operability.

## 2024-05-20 - Global Button Cursor Affordance
**Learning:** Base CustomTkinter button components do not default to `cursor="hand2"`. Missing this across shared components like `IconButton`, `PrimaryButton`, and `SidebarItem` causes a systemic lack of visual feedback for interactive elements.
**Action:** Always ensure `cursor="hand2"` is passed down to `super().__init__` in generic button wrapper classes to guarantee global interaction consistency.

## 2024-05-21 - Interactive List Results Affordance
**Learning:** In CustomTkinter, complex interactive list items (like the search results in the Omnibar) that are built from generic frames and labels (`CTkFrame`, `CTkLabel`) do not inherently show a pointing cursor on hover. Without explicitly setting `cursor="hand2"` on the container and all its children, users miss the critical visual cue that the entire row is clickable.
**Action:** Always apply `cursor="hand2"` to all sub-components (frames, icons, text labels) of an interactive list item to ensure uniform hover affordances across the entire clickable area.
## $(date +%Y-%m-%d) - Context-Aware Interaction Feedback
**Learning:** Hardcoded text states on multi-phase action buttons (like 'Find Match') leave users without visual confirmation of system state transitions.
**Action:** Dynamically map button text and color to application phases (e.g., '■ Cancel Search' + Danger Color when active) to reduce cognitive load and provide clear status indicators.
## 2024-04-02 - Interactive Collapsible Headers
**Learning:** In CustomTkinter, structural UI elements acting as toggle buttons (like CardHeader labels) do not natively receive standard click interaction affordances, resulting in a hidden hit area that decreases discoverability. Users intuitively attempt to click the header text itself rather than just a tiny trailing icon button.
**Action:** When creating collapsible UI sections or composite widgets, explicitly bind `<Button-1>` to the main descriptive label, set `cursor="hand2"`, and implement visual hover feedback via `<Enter>` and `<Leave>` bindings changing `text_color` to expand the actionable target area.
## 2024-05-24 - CTkOptionMenu Affordance
**Learning:** In CustomTkinter, \`CTkOptionMenu\` components (dropdowns) do not automatically provide a change in the cursor (e.g., to a pointing hand) when hovered. This omission can make it slightly less obvious that the element is clickable, particularly when styled to blend into the application background.
**Action:** Always ensure \`cursor="hand2"\` is explicitly passed to \`CTkOptionMenu\` instances alongside other interactive widgets like \`CTkButton\` to maintain clear affordance and consistent visual UX cues across the application.
## 2025-02-18 - FriendPriorityList Affordances
**Learning:** In CustomTkinter applications, custom list elements that serve as interactive items (like right-click context menus in FriendPriorityList) do not inherently have standard hover affordances.
**Action:** Always apply `cursor="hand2"` to all sub-components (frames, icons, text labels) of an interactive list item to ensure uniform hover affordances across the entire clickable area.
## $(date +%Y-%m-%d) - Adding interactive affordances to standalone CTkLabels
**Learning:** In CustomTkinter, `CTkLabel` elements acting as standalone buttons or toggles (like collapsible section headers) do not inherently provide hover affordances. It is crucial to manually apply `cursor="hand2"` and `<Enter>`/`<Leave>` color change bindings so the user knows they are interactive, as `app_sidebar.py` showed with its `lbl_profile_section`.
**Action:** Always explicitly set `cursor="hand2"` and bind `<Enter>` and `<Leave>` events to toggle text color on standalone `CTkLabels` acting as buttons/toggles.
## $(date +%Y-%m-%d) - Drag Handle Hover Affordances
**Learning:** In CustomTkinter, standard text labels (`CTkLabel`) repurposed as drag handles lack visual interaction cues. Using explicit `cursor="hand2"` is insufficient.
**Action:** Always implement `<Enter>` and `<Leave>` hover bindings that utilize theme tokens (e.g., `get_color("colors.text.primary")` and `get_color("colors.text.muted")`) to provide clear visual feedback that the element is interactable.
## $(date +%Y-%m-%d) - Interactive Grid Icon Affordances
**Learning:** In CustomTkinter, icon grid items created with `CTkLabel` (like those in `priority_grid.py`) do not inherit click cursors automatically, even when bound to mouse events (`<Button-1>`). This missing visual feedback leaves users guessing if the items are interactive, especially during edit modes.
**Action:** Always explicitly pass `cursor="hand2"` to `CTkLabel` and `CTkFrame` components that act as interactive grid cells to ensure standard discoverability.
