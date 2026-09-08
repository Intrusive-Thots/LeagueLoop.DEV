# LeagueLoop documentation

Project overview, install instructions and feature list are in the
[root README](../README.md). This page indexes everything in `docs/`.

## Start here

| Document | What it covers |
|---|---|
| [architecture.md](architecture.md) | Layers, event flow, and service boundaries |
| [development.md](development.md) | Local setup, running from source, workflow |
| [troubleshooting.md](troubleshooting.md) | Common failures, log locations, diagnostics |
| [file_index.md](file_index.md) | Major files, their responsibilities and dependencies |

## Decisions

| Document | What it covers |
|---|---|
| [adr/0001-lcu-websocket-primary.md](adr/0001-lcu-websocket-primary.md) | Why the LCU WebSocket is primary over polling |
| [`.agents/ARCHITECTURE_CONSTRAINTS.md`](../.agents/ARCHITECTURE_CONSTRAINTS.md) | The LCU-only rule — what the app may and may not touch |

## Planning and history

| Document | What it covers |
|---|---|
| [CHANGELOG.md](CHANGELOG.md) | Release history |
| [roadmap.md](roadmap.md) | Product and technical roadmap |
| [improvement_plan.md](improvement_plan.md) | Comprehensive audit and improvement plan |
| [engineering_baseline.md](engineering_baseline.md) | Engineering baseline report |
| [INSTALLER_BUILD_GUIDE.md](INSTALLER_BUILD_GUIDE.md) | Installer build system |

## Working notes

Scratch and in-progress documents. Point-in-time snapshots rather than
maintained references — read them for context, not as current truth.

- [CONTEXT.md](CONTEXT.md)
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
- [IMPROVEMENTS_SUMMARY.md](IMPROVEMENTS_SUMMARY.md)
- [PERFORMANCE_OPTIMIZATION_PLAN.md](PERFORMANCE_OPTIMIZATION_PLAN.md)
- [PERFORMANCE_OPTIMIZATION_REPORT.md](PERFORMANCE_OPTIMIZATION_REPORT.md)
- [TASK_QUEUE.md](TASK_QUEUE.md)
- [TODO.md](TODO.md)
- [task.md](task.md)

## Agent configuration

[AGENTS.md](AGENTS.md) holds the workspace rules; [agents/](agents/) holds the
individual role definitions. Reusable procedures live in
[`.agents/skills/`](../.agents/skills/).
