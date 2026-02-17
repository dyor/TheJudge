# AGENTS.md

This document provides guidelines for AI agents managing the `ctef_proxy` codebase.

## 📂 File Structure

*   `interceptor.py`: **Network Layer**. The `mitmproxy` script. Handles HTTP request interception, modification, and blocking.
*   `dashboard.py`: **Application Layer**. The FastAPI web server. Manages blocking state, UI, and database persistence.
*   `templates/index.html`: **Presentation Layer**. The frontend for the dashboard.
*   `eval_metrics.db`: **Persistence Layer**. SQLite database. Contains `traffic_log` and `interventions`.

## 🛠 Guidelines

### 1. Database Schema
*   The SQLite schema is defined in `dashboard.py` within `init_db()`.
*   **Do not modify existing columns** without a migration plan, as it will break historical data access.
*   Current schema:
    *   `traffic_log`: (id, timestamp, tokens_in, tokens_out, latency_ms)
    *   `interventions`: (id, timestamp, prompt_text, classification)

### 2. Frontend Development
*   Keep logic in `index.html` simple (Vanilla JS). Avoid heavy frameworks.
*   Use `fetch` for API calls.
*   Format large numbers with commas (`formatNumber` function exists).
*   Ensure "View" buttons use the modal system (`showModal`) rather than alerts.

### 3. Backend Logic
*   `dashboard.py` must handle concurrent requests gracefully, though currently `blocking_event` is global (single-threaded blocking model).
*   If adding new endpoints, ensure they return JSON for consumption by the frontend.

### 4. Interceptor logic
*   `interceptor.py` relies on specific Gemini API JSON structures (`contents` -> `parts` -> `text`).
*   If the API changes, update the parsing logic in `request()` and `response()`.
*   Maintain the `flow.id` mapping for accurate latency tracking.

## 🔄 Workflow

1.  **Read Context**: Always check `dashboard.py` and `interceptor.py` before proposing changes.
2.  **Verify State**: Check `init_db` to understand the current data model.
3.  **Implement Changes**: Update backend first, then frontend.
4.  **Document**: Update `README.md` if new setup steps are required.
