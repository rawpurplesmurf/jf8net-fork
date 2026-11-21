# jf8net — AI Coding Agent Instructions

Async and synchronous Python client library for the **JF8Call** WebSocket API (`v0.7.0+`).

## Branch & Pull Request Workflow

1. Never commit or push directly to `main`; always use an isolated `feat/*`, `fix/*`, or `docs/*` branch and merge via Pull Request after automated review and CI checks pass.
2. Maintain `>= 80%` unit test coverage (`pytest --cov=jf8net --cov-fail-under=80`), zero `ruff` and `bandit` findings, and patched dependency floors (`websockets>=17.4`, `setuptools>=78.1.1`, `pip>=26.2.1`).
