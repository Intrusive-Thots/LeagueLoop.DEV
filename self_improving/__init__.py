# self_improving — Autonomous Self-Improvement Loop for LeagueLoop
#
# Usage:  py -m self_improving [--once] [--dry-run] [--interval MINUTES]
#
# This module implements a repeating improvement cycle that:
#   1. Indexes the repository (files, lines, complexity)
#   2. Loads persistent memory (episodic, failures, procedural)
#   3. Runs the test suite and captures results
#   4. Detects regressions, dead code, missing docs, and TODOs
#   5. Logs findings as structured JSON into the memory system
#   6. Optionally schedules the next run
