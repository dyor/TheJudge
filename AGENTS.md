# AGENTS.md

This document provides instructions for AI agents managing the `ctef_proxy` codebase.

## Overview

The `ctef_proxy` is a specialized HTTP proxy designed to intercept and manage traffic to the Gemini API (`generativelanguage.googleapis.com`) for evaluation purposes. It enables a "Human-in-the-Loop" workflow where requests are paused and reviewed before being forwarded.

## Architecture

*   **`interceptor.py`**: A `mitmproxy` script. It handles interception, request modification, and logging.
    *   **Logic**: Checks for `generativelanguage.googleapis.com`. Extracts user prompts. Blocks requests by calling `dashboard.py`. Logs metrics on response.
*   **`dashboard.py`**: A FastAPI application serving as the control plane.
    *   **Logic**: Manages blocking state using `asyncio.Event`. Provides endpoints for the UI (`/`) and API (`/ask_permission`, `/log_traffic`). Writes to SQLite (`eval_metrics.db`).
*   **`templates/index.html`**: The frontend for the dashboard.
    *   **Logic**: Polls `/status` to check for blocked requests. Allows human classification ("NIT" or "ISSUE").

## Development Guidelines

1.  **Dependencies**:
    *   Use `mitmproxy` (for `interceptor.py`).
    *   Use `fastapi`, `uvicorn`, `requests`, `jinja2` (for `dashboard.py`).
    *   Use `sqlite3` for persistence.

2.  **Running the Stack**:
    *   Start `dashboard.py` first (`python3 dashboard.py`).
    *   Start `interceptor.py` with `mitmdump` (`mitmdump -s interceptor.py`).

3.  **Code Structure**:
    *   Keep logic separated between interception (network layer) and dashboard (application/UI layer).
    *   Use `eval_metrics.db` for all persistent data.
    *   Ensure proper error handling in `interceptor.py` to avoid breaking traffic flow (use try-except blocks).

4.  **Testing**:
    *   Test by sending requests to `generativelanguage.googleapis.com` through the proxy.
    *   Verify data is written to `eval_metrics.db`.
    *   Verify UI reflects the blocked state and allows classification.

## Future Improvements

*   Refine JSON parsing in `interceptor.py` to handle different message structures.
*   Add more granular metrics (e.g., specific error codes).
*   Improve UI polling efficiency (consider WebSockets).
*   Add support for multiple concurrent users/flows.
