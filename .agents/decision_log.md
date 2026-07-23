# Architectural Decision Log

## ADR-001: EventBus Architecture
- **Status**: Accepted
- **Context**: UI controls and background automation services needed decoupled communication without circular dependencies.
- **Decision**: Implemented singleton `EventBus` class in `src/core/events.py` for pub/sub messaging.

## ADR-002: PySide6 (Qt) UI Framework Transition
- **Status**: Accepted
- **Context**: CustomTkinter lacked styling flexibility for complex Riot-style UI components, vector icons, and docking support.
- **Decision**: Adopted PySide6 Qt framework as the primary UI shell while maintaining backward compatibility for CustomTkinter via dual launcher `run.py`.

## ADR-003: Memory & Self-Improvement Architecture (.agents/)
- **Status**: Accepted
- **Context**: System directive requires autonomous evolution, task tracking, failure logging, and persistent memory across execution cycles without user prompts.
- **Decision**: Maintained project state memory, failure logs, and architectural decision docs inside `.agents/` directory.
