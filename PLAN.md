# PLAN.md

## Current Status

The basic functionality is implemented:
*   `interceptor.py`: Intercepts Gemini requests, extracts user prompts, blocks requests, and logs metrics (including full response).
*   `dashboard.py`: Provides a control panel to approve/classify requests and persist data to SQLite.
*   `templates/index.html`: Basic UI for human intervention with project scoping and full response inspection.

## Immediate Next Steps (User Requested)

### 1. Progress Tracking
- [ ] **Add Progress Column**:
    - Update `traffic_log` (or a new table?) to include a `progress_percentage` column.
    - *Decision*: It's probably better to store this as a separate "state" associated with the *project* or the *current timestamp*, but attaching it to the `traffic_log` entry makes it easy to plot X/Y later.
    - Let's add a global `current_progress` state in `dashboard.py`.
- [ ] **UI for Progress**:
    - Add a row of toggle buttons (0%, 10%, ..., 100%) to `templates/index.html`.
    - When clicked, these buttons update the global `current_progress` state on the server.
- [ ] **Log Progress**:
    - When `log_traffic` is called by `interceptor.py`, include the `current_progress` value in the database record.

### 2. Visualization (Future)
- [ ] **Chart.js Integration**:
    - Add a chart to the dashboard plotting `progress_percentage` (X) vs `tokens_out` (Y) (or `tokens_in + tokens_out`).

## Backlog

### 3. Verification & Testing

- [ ] **Verify End-to-End Flow**:
    - Start `dashboard.py`.
    - Start `mitmdump -s interceptor.py`.
    - Configure Android emulator proxy to `localhost:8000`.
    - Send a request from the Android app.
    - Confirm the request hangs.
    - Confirm the dashboard shows the prompt.
    - Classify the request (NIT/ISSUE).
    - Confirm the request proceeds and the response is received by the app.
    - Verify data in `eval_metrics.db`.

### 4. UI Improvements

- [ ] **Real-time Updates**: Replace polling (`/status`) with WebSockets for instant updates.
- [ ] **Better Visualization**:
    - Show full conversation history, not just the last message.
    - Display token usage and latency in the dashboard.
- [ ] **Filtering**: Allow filtering by timestamp or classification type.

### 5. Concurrency Handling

- [ ] **Support Multiple Requests**:
    - Currently, `blocking_event` is global. This means if multiple requests come in simultaneously, they might interfere with each other.
    - Implement a dictionary of `asyncio.Event` objects keyed by `flow.id` to handle concurrent requests independently.
- [ ] **Request Queue**: Implement a queue for pending requests on the dashboard.

### 6. Deployment & Configuration

- [ ] **Dockerization**: Create a `Dockerfile` to run `dashboard.py` and `mitmdump` together or separately.
- [ ] **Configuration**: Move hardcoded URLs (e.g., `DASHBOARD_URL`) to environment variables or a config file.

### 7. Advanced Features

- [ ] **Automated Classification**:
    - Integrate a lightweight local LLM to pre-classify requests as "Safe" or "Flagged".
- [ ] **Response Modification**:
    - Allow the human evaluator to *edit* the response before sending it back to the app.
