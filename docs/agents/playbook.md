
## Unit Testing Mock Best Practices
- When testing background periodic automation loops (like `AutomationEngine._tick`), always aggressively mock the environment state such as `_is_game_running` and control state variables like `_is_first_tick` to ensure idempotency and prevent side-effect pollution.
