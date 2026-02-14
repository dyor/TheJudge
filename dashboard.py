# dashboard.py
import sqlite3
import asyncio
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import uvicorn
from datetime import datetime, timedelta

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- GLOBAL STATE ---
# This event acts as a traffic light. Red = Wait, Green = Go.
blocking_event = asyncio.Event()
current_intervention = {"text": "Waiting for input...", "classification": None}
active_project_name = "default_project"
current_progress = 0

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('eval_metrics.db')
    c = conn.cursor()

    # Create tables if they don't exist
    c.execute('''CREATE TABLE IF NOT EXISTS traffic_log
                 (id INTEGER PRIMARY KEY, timestamp TEXT, tokens_in INT, tokens_out INT, latency_ms REAL, project_name TEXT, full_response TEXT, progress_percentage INT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS interventions
                 (id INTEGER PRIMARY KEY, timestamp TEXT, prompt_text TEXT, classification TEXT, project_name TEXT)''')

    # Migration: Add project_name column if it doesn't exist (for existing DBs)
    try:
        c.execute("ALTER TABLE traffic_log ADD COLUMN project_name TEXT")
    except sqlite3.OperationalError:
        pass # Column likely already exists

    try:
        c.execute("ALTER TABLE traffic_log ADD COLUMN full_response TEXT")
    except sqlite3.OperationalError:
        pass # Column likely already exists

    try:
        c.execute("ALTER TABLE traffic_log ADD COLUMN progress_percentage INT")
    except sqlite3.OperationalError:
        pass # Column likely already exists

    try:
        c.execute("ALTER TABLE interventions ADD COLUMN project_name TEXT")
    except sqlite3.OperationalError:
        pass # Column likely already exists

    conn.commit()
    conn.close()

@app.on_event("startup")
def startup():
    init_db()

def get_project_stats(conn, project_name):
    c = conn.cursor()

    # 1. Calculate Time Elapsed (Earliest log - Now)
    # We check both traffic_log and interventions for the start time
    c.execute("SELECT MIN(timestamp) FROM traffic_log WHERE project_name = ?", (project_name,))
    start_traffic = c.fetchone()[0]

    c.execute("SELECT MIN(timestamp) FROM interventions WHERE project_name = ?", (project_name,))
    start_interv = c.fetchone()[0]

    start_time = None
    if start_traffic and start_interv:
        start_time = min(start_traffic, start_interv)
    elif start_traffic:
        start_time = start_traffic
    elif start_interv:
        start_time = start_interv

    duration_str = "00:00:00"
    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time)
            delta = datetime.now() - start_dt
            # Format to HH:MM:SS (remove microseconds)
            duration_str = str(delta).split('.')[0]
        except:
            pass

    # 2. Token Stats
    c.execute("SELECT SUM(tokens_in), SUM(tokens_out) FROM traffic_log WHERE project_name = ?", (project_name,))
    row = c.fetchone()
    tokens_in = row[0] if row[0] else 0
    tokens_out = row[1] if row[1] else 0

    # 3. Intervention Stats
    c.execute("SELECT classification, COUNT(*) FROM interventions WHERE project_name = ? GROUP BY classification", (project_name,))
    rows = c.fetchall()
    interventions = {"NIT": 0, "ISSUE": 0}
    for r in rows:
        interventions[r[0]] = r[1]

    return {
        "duration": duration_str,
        "tokens": {
            "in": tokens_in,
            "out": tokens_out,
            "total": tokens_in + tokens_out
        },
        "interventions": {
            "nit": interventions.get("NIT", 0),
            "issue": interventions.get("ISSUE", 0),
            "total": interventions.get("NIT", 0) + interventions.get("ISSUE", 0)
        }
    }

# --- WEBPAGE UI ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    conn = sqlite3.connect('eval_metrics.db')
    conn.row_factory = sqlite3.Row # Access columns by name
    c = conn.cursor()

    # Fetch recent traffic logs
    c.execute("SELECT * FROM traffic_log ORDER BY id DESC LIMIT 10")
    rows_log = c.fetchall()
    recent_logs = [dict(row) for row in rows_log]

    # Fetch recent interventions
    c.execute("SELECT * FROM interventions ORDER BY id DESC LIMIT 10")
    rows_int = c.fetchall()
    recent_interventions = [dict(row) for row in rows_int]

    # Get Project Stats
    stats = get_project_stats(conn, active_project_name)

    conn.close()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "logs": recent_logs,
        "interventions": recent_interventions,
        "project_name": active_project_name,
        "current_progress": current_progress,
        "stats": stats
    })

@app.post("/set_project")
async def set_project(request: Request):
    global active_project_name, current_progress
    data = await request.json()
    new_name = data.get("project_name", "default_project").strip()

    conn = sqlite3.connect('eval_metrics.db')
    c = conn.cursor()

    # Check if project name exists in either table
    c.execute("SELECT count(*) FROM traffic_log WHERE project_name = ?", (new_name,))
    count_log = c.fetchone()[0]
    c.execute("SELECT count(*) FROM interventions WHERE project_name = ?", (new_name,))
    count_int = c.fetchone()[0]

    conn.close()

    # If exists, append timestamp
    if count_log > 0 or count_int > 0:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = f"{new_name}_{timestamp}"

    active_project_name = new_name
    current_progress = 0 # Reset progress for new project
    return {"status": "ok", "project_name": active_project_name}

@app.post("/set_progress")
async def set_progress(request: Request):
    global current_progress
    data = await request.json()
    current_progress = int(data.get("progress", 0))
    return {"status": "ok", "progress": current_progress}

@app.get("/status")
async def get_status():
    """Polled by the UI to check if we need help."""
    if not blocking_event.is_set() and current_intervention["classification"] is None:
         return {"status": "BLOCKED", "text": current_intervention["text"]}
    return {"status": "RUNNING"}

# --- MITMPROXY ENDPOINTS ---
@app.post("/ask_permission")
async def ask_permission(request: Request):
    """Called by mitmproxy. BLOCKS until human clicks a button."""
    data = await request.json()

    # 1. Update State
    global current_intervention
    current_intervention["text"] = data.get("text", "")
    current_intervention["classification"] = None
    blocking_event.clear() # Turn light RED

    print(f"🚨 INTERVENTION NEEDED: {data.get('text')[:50]}...")

    # 2. WAIT HERE (This keeps mitmproxy hanging)
    await blocking_event.wait()

    # 3. Release
    return {"status": "released", "classification": current_intervention["classification"]}

@app.post("/log_traffic")
async def log_traffic(request: Request):
    """Called by mitmproxy after request finishes."""
    data = await request.json()
    conn = sqlite3.connect('eval_metrics.db')
    c = conn.cursor()

    # Check if progress_percentage is in payload (from newer interceptors), otherwise use global state
    progress = data.get('progress_percentage', current_progress)

    c.execute("INSERT INTO traffic_log (timestamp, tokens_in, tokens_out, latency_ms, project_name, full_response, progress_percentage) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (datetime.now().isoformat(), data['tokens_in'], data['tokens_out'], data['latency_ms'], active_project_name, data.get('full_response', ''), progress))
    conn.commit()
    conn.close()
    return {"status": "logged"}

# --- UI BUTTON ENDPOINTS ---
@app.post("/classify")
async def classify(request: Request):
    """Called by the Human via Web UI."""
    data = await request.json()
    category = data.get("type") # "NIT" or "ISSUE"

    # Log the intervention
    conn = sqlite3.connect('eval_metrics.db')
    c = conn.cursor()
    c.execute("INSERT INTO interventions (timestamp, prompt_text, classification, project_name) VALUES (?, ?, ?, ?)",
              (datetime.now().isoformat(), current_intervention["text"], category, active_project_name))
    conn.commit()
    conn.close()

    # Release the Block
    current_intervention["classification"] = category
    blocking_event.set() # Turn light GREEN
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)