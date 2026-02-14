# CTEF Proxy (Capture The Evaluation Flag)

This project implements a proxy server to intercept, analyze, and control traffic between an Android application and the Gemini API (`generativelanguage.googleapis.com`). It allows for "Human-in-the-Loop" evaluation where requests can be paused, inspected, and classified before proceeding.

## Components

1.  **`interceptor.py`**: A `mitmproxy` script that intercepts HTTP traffic.
    *   It listens for requests to Gemini.
    *   It extracts the user's prompt.
    *   It sends a blocking request to the Dashboard to ask for permission.
    *   It logs metrics (latency, token usage) after the response is received.
2.  **`dashboard.py`**: A FastAPI web server that acts as the control panel.
    *   It provides a web UI for the human evaluator.
    *   It manages the blocking state of intercepted requests.
    *   It logs traffic and interventions to a SQLite database (`eval_metrics.db`).

## Setup & Usage

### 1. Prerequisites

*   Python 3.x
*   `mitmproxy`
*   `fastapi`, `uvicorn`, `requests`, `jinja2`

### 2. Configure Android Studio Proxy

To intercept traffic from your Android emulator or device, you need to configure the HTTP proxy settings in Android Studio:

1.  Go to **Settings** (or **Preferences** on macOS) -> **Appearance & Behavior** -> **System Settings** -> **HTTP Proxy**.
2.  Select **Manual proxy configuration**.
3.  Choose **HTTP**.
4.  Host name: `localhost` (or `127.0.0.1`)
5.  Port number: `8080`
6.  Click **Apply** and **OK**.

*Note: You may also need to install the mitmproxy CA certificate on your Android device to intercept HTTPS traffic. See the [mitmproxy documentation](https://docs.mitmproxy.org/stable/concepts-certificates/) for details.*

### 3. Start the Control Panel

Run the dashboard server first. This will handle the UI and the database.

```bash
python3 dashboard.py
```

The dashboard will be available at `http://localhost:8000`.

### 4. Start the Proxy

Run `mitmdump` with the interceptor script. This will start the proxy on port 8080 (default).

```bash
mitmdump -s interceptor.py
```

Now, any traffic from your Android app going to Gemini will be intercepted. The request will hang until you classify it in the dashboard.

### 5. Analyze Data

Data is stored in `eval_metrics.db`. You can inspect it using `sqlite3`.

```bash
sqlite3 eval_metrics.db
```

Example queries:

```sql
-- View traffic logs
SELECT * FROM traffic_log;

-- View human interventions
SELECT * FROM interventions;
```
