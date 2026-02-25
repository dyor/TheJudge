# The Judge

**The Judge** is a "Human-in-the-Loop" evaluation tool designed to intercept and analyze traffic between an Android application and the Gemini API (`generativelanguage.googleapis.com`). It allows developers and evaluators to inspect LLM requests in flight, offering an opportunity to review and optionally reclassify interactions.

## 🏗 Architecture

The system consists of two main components:

1.  **Interceptor (`interceptor.py`)**: A `mitmproxy` script that sits between the Android device and the internet.
    *   Intercepts requests to Gemini.
    *   Extracts prompts and forwards metadata to the Dashboard.
    *   Automatically classifies interactions based on heuristics (NIT, ISSUE, PLANNED).
    *   Logs performance metrics (latency, token usage).
2.  **Dashboard (`dashboard.py`)**: A FastAPI web server providing the control interface.
    *   Displays intercepted requests and their automatic classifications.
    *   Allows manual re-classification of interventions (e.g., changing an "ISSUE" to a "PLANNED").
    *   Visualizes recent traffic and intervention history.
    *   Persists data to SQLite (`eval_metrics.db`), which is gitignored to avoid sharing private information.

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
7.  **No Proxy For**: `127.0.0.1, *.maven.org, *.jetbrains.com, services.gradle.org` (Ensure `*.google.com` is **NOT** in this list so Gemini traffic is intercepted).
8.  Click **Apply** and **OK**.

*Note: You may need to install the mitmproxy CA certificate on the emulator to inspect HTTPS traffic. See [mitmproxy certificates](https://docs.mitmproxy.org/stable/concepts-certificates/).*

### 3. Start the Proxy and Dashboard

The easiest way to start both the dashboard and the interceptor is to use the provided shell script:

```bash
./start_proxy.sh
```

Alternatively, you can run them separately:

```bash
python3 dashboard.py
```
(Access the dashboard at: [http://localhost:8000](http://localhost:8000))

```bash
mitmdump -s interceptor.py
```

### 4. Workflow

1.  Trigger an LLM feature in your Android app.
2.  The request will be automatically classified (e.g., as "NIT", "ISSUE", or "PLANNED") and released, allowing the app to receive a response.
3.  Check the Dashboard ([http://localhost:8000](http://localhost:8000)) to review the interaction, including the prompt and its classification.
4.  If needed, you can manually update the classification of any intervention from the "Recent Interventions" table.

## 📊 Data & Analysis

Data is stored in `eval_metrics.db` (SQLite), which is excluded from version control by `.gitignore`. The Dashboard provides a live view of:
*   **Recent Traffic Logs**: Token usage, latency, and timestamps.
*   **Recent Interventions**: History of human reviews and full prompts. You can reclassify interventions here.
*   **Export Iteration Details**: Use the button in the metadata section to export all iteration details and current stats to a Markdown file.

To query directly:
```bash
sqlite3 eval_metrics.db "SELECT * FROM traffic_log ORDER BY id DESC LIMIT 5;"
```

If you want to use Gemini from an emulator while the proxy is running, you need to open the emulator as standalone, click the ..., select settings, proxy, and uncheck "use android studio HTTP proxy settings"

`~/Library/Android/sdk/emulator/emulator -avd Medium_Phone_API_36.1 -no-snapshot-load`