## 2024-03-26 - Visual Consistency with Custom Components
**Learning:** Standard OS or default GUI components (like `CTkSwitch`) break visual immersion when placed alongside highly stylized, custom components (like Riot-themed `LolToggle`).
**Action:** When auditing or implementing UI features, prioritize extending and utilizing existing custom design system components over mixing default components, ensuring a cohesive and immersive user experience.
## 2024-03-27 - Inline Confirmations for Destructive Actions
**Learning:** Using inline, timed confirmations (where a button changes text and color briefly before allowing the action) avoids popup fatigue and keeps the user in their context, while still preventing accidental clicks for destructive actions like resetting settings. Coupling the successful action with a delightful feedback loop (like a Confetti Toast) makes the interaction satisfying rather than purely utilitarian.
**Action:** Default to inline, timed confirmation states for medium-risk actions (like reset, clear history, or bulk changes) instead of modal dialogues to preserve UX fluidity and increase engagement through micro-interactions.
## 2024-03-28 - Micro-Interactions in Low-Risk Zones
**Learning:** Adding unexpected, delightful interactions (like an Easter egg) to typically static and low-risk UI elements (like a footer or "Made by" label) can significantly boost user joy and engagement without compromising the core workflow or introducing friction.
**Action:** When seeking opportunities for "delight," target functional dead-ends or static attribution areas, applying progressive disclosure (e.g., color hints on hover, requiring multiple clicks) to hide the gamified interaction until explicitly sought.

## 2024-03-29 - Contextual Feedback for Configuration Inputs
**Learning:** Providing immediate, contextual micro-feedback (like success flashes or error nudges) on configuration inputs (e.g., hotkey recording) transforms a dry, error-prone task into an intuitive, gamified experience, reducing cognitive load and increasing confidence.
**Action:** When designing data entry or configuration components, always incorporate distinct visual and textual states for 'listening', 'success', and 'invalid' to provide continuous haptic-like feedback.
## 2024-05-24 - Interactive Empty States turn Dead Ends into Conversion Points
**Learning:** Empty lists (like Priority or Friends) present a "dead end" friction point for new users. Instead of leaving a blank space, transforming the empty area into a large, themed, interactive dropzone/button significantly reduces cognitive load and directs immediate user action.
**Action:** Always verify what the "empty state" of a component looks like. If it lacks clear instruction, replace it with a low-friction, gamified call-to-action button that directly launches the creation flow.
## 2024-04-03 - Contextual Quick Status Presets
**Learning:** Users often change their League client status to common states (AFK, Grinding, ARAMs) but manual entry creates friction. Providing visual, one-click preset buttons with micro-feedback significantly reduces cognitive load and encourages personalization.
**Action:** Implemented a row of interactive emoji preset buttons in the Profile section that instantly update the status and trigger a success toast. Used dynamic restyling on hover to provide clear visual affordances.
