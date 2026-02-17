# PLAN.md

This document tracks future improvements and tasks for the CTEF Proxy project.

## 🚀 Future Improvements

### 1. **Data Management**

*   **Export/Import**: Add buttons to download logs as JSON/CSV.
*   **Search/Filter**: Add search bars to filter logs by `prompt_text` or classification.
*   **Detailed Metrics**: Capture full request/response bodies in SQLite (currently only snippets/metrics).
*   **Project Filtering**: Add `project_id` column to support multiple projects.

### 2. **User Interface**

*   **Polling Optimization**: Replace 2s polling with WebSockets for real-time updates.
*   **Prompt Diffing**: Show diffs between original and modified prompts (if editing is added).
*   **Replay**: Allow re-sending intercepted requests directly from the dashboard.
*   **Charts**: Visualize token usage and latency trends over time.

### 3. **Architecture**

*   **Concurrency**: Support multiple concurrent intercepted requests (currently using a single global `blocking_event`).
*   **Docker**: Containerize the app for easier deployment.
*   **Authentication**: Add basic auth for the dashboard if deployed remotely.

### 4. **Testing**

*   **Mock Tests**: Add unit tests for `interceptor.py` JSON parsing.
*   **Integration Tests**: Script to simulate traffic flow and verify DB writes.
