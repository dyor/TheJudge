# CTEF Proxy (Capture The Evaluation Flag)

The **CTEF Proxy** is a "Human-in-the-Loop" evaluation tool designed to intercept, analyze, and control traffic between an Android application and the Gemini API (`generativelanguage.googleapis.com`). It allows developers and evaluators to pause LLM requests in flight, inspect the prompt, and classify or modify the interaction before it proceeds.

## 🏗 Architecture

The system consists of two main components:

1.  **Interceptor (`interceptor.py`)**: A `mitmproxy` script that sits between the Android device and the internet.
    *   Intercepts requests to Gemini.
    *   Extracts prompts and pauses execution.
    *   forwards metadata to the Dashboard.
    *   Logs performance metrics (latency, token usage).
2.  **Dashboard (`dashboard.py`)**: A FastAPI web server providing the control interface.
    *   Displays blocked requests to the human evaluator.
    *   Allows classification ("NIT" or "ISSUE").
    *   Visualizes recent traffic and intervention history.
    *   Persists data to SQLite (`eval_metrics.db`).

## 🚀 Setup & Usage

### 1. Prerequisites

*   Python 3.8+
*   `mitmproxy`
*   `fastapi`, `uvicorn`, `requests`, `jinja2`

Install dependencies:
```bash
pip install mitmproxy fastapi uvicorn requests jinja2
```

### 2. Configure Android Studio Proxy

To intercept traffic from the Android Emulator:

1.  Open Android Studio.
2.  Go to **Settings** (or **Preferences** on macOS) -> **Appearance & Behavior** -> **System Settings** -> **HTTP Proxy**.
3.  Select **Manual proxy configuration**.
4.  Choose **HTTP**.
5.  **Host name**: `127.0.0.1` (or `localhost`)
6.  **Port number**: `8080`
7.  **No Proxy For**: `*.maven.org, *.jetbrains.com, services.gradle.org` (Ensure `*.google.com` is **NOT** in this list so Gemini traffic is intercepted).
8.  Click **Apply** and **OK**.

*Note: You may need to install the mitmproxy CA certificate on the emulator to inspect HTTPS traffic. See [mitmproxy certificates](https://docs.mitmproxy.org/stable/concepts-certificates/).*

### 3. Start the Dashboard

Run the web server first. This handles the UI and database.

```bash
python3 dashboard.py
```
Access the dashboard at: [http://localhost:8000](http://localhost:8000)

### 4. Start the Interceptor

Run `mitmdump` with the interceptor script. This starts the proxy on port 8080.

```bash
mitmdump -s interceptor.py
```

### 5. Workflow

1.  Trigger an LLM feature in your Android app.
2.  The request will hang.
3.  Check the Dashboard. You will see "🛑 BLOCKED - INTERVENTION NEEDED".
4.  Review the prompt.
5.  Click **NIT** (Minor issue) or **ISSUE** (Major problem) to resume the request.
6.  The app receives the response, and metrics are logged.

## 📊 Data & Analysis

Data is stored in `eval_metrics.db` (SQLite). The Dashboard provides a live view of:
*   **Recent Traffic Logs**: Token usage, latency, and timestamps.
*   **Recent Interventions**: History of human reviews and full prompts.

To query directly:
```bash
sqlite3 eval_metrics.db "SELECT * FROM traffic_log ORDER BY id DESC LIMIT 5;"
```
