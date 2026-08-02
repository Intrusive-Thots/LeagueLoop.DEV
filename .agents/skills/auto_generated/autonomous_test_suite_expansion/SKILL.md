---
name: autonomous_test_suite_expansion
description: Procedure for analyzing test coverage gaps, implementing in-memory HTTP/Event test harnesses, and expanding pytest suites autonomously.
---

# Autonomous Test Suite Expansion Skill

## Overview
Automates the analysis of untested application modules, creation of robust mock test harnesses (such as in-memory BaseHTTPRequestHandler handlers and EventBus listener suites), and execution of coverage benchmarking.

## Execution Steps
1. **Analyze Coverage**: Run `pytest --cov=src --cov-report=term-missing` to isolate modules lacking test coverage.
2. **Design Test Harnesses**:
   - For `EventBus`/State modules: test registration, unbinding (`off`), state mutations, and thread-safe callbacks.
   - For `BaseHTTPRequestHandler` services: instantiate an in-memory subclass with `io.BytesIO` for `rfile`/`wfile` and a `MockServer`.
   - For constant/version definitions: validate regex format patterns and bounds.
3. **Execute & Benchmark**: Run pytest with `-v` to confirm 100% test pass rate and verify execution time delta remains under 2 seconds.
4. **Log Capabilities**: Record findings in episodic, semantic, procedural, failures, and optimizations memory registries.
