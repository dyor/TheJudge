# dashboard.py
import sqlite3
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
import uvicorn
from datetime import datetime
import os

app = FastAPI()
templates = Jinja2Templates(directory="templates")
DB_FILE = 'eval_metrics.db'

# --- DATABASE SETUP ---
def init_db():
    print(f"Initializing database: {os.path.abspath(DB_FILE)}")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 1. Create Tables
    c.execute('''CREATE TABLE IF NOT EXISTS traffic_log
                 (id INTEGER PRIMARY KEY, timestamp TEXT, tokens_in INT, tokens_out INT, latency_ms REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS interventions
                 (id INTEGER PRIMARY KEY, timestamp TEXT, prompt_text TEXT, classification TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS iterations
                 (id INTEGER PRIMARY KEY,
                  name TEXT UNIQUE,
                  baseline_project TEXT,
                  model TEXT,
                  skills TEXT,
                  prompt TEXT,
                  notes TEXT,
                  task TEXT,
                  plan TEXT,
                  agents TEXT,
                  created_at TEXT)''')

    # 2. Migrations
    c.execute("PRAGMA table_info(traffic_log)")
    traffic_cols = [info[1] for info in c.fetchall()]
    if 'project_name' not in traffic_cols:
        c.execute("ALTER TABLE traffic_log ADD COLUMN project_name TEXT DEFAULT 'Factory'")
    if 'progress_percentage' not in traffic_cols:
        c.execute("ALTER TABLE traffic_log ADD COLUMN progress_percentage INT DEFAULT 0")
    if 'full_response' not in traffic_cols:
        c.execute("ALTER TABLE traffic_log ADD COLUMN full_response TEXT")
    if 'prompt_text' not in traffic_cols:
        c.execute("ALTER TABLE traffic_log ADD COLUMN prompt_text TEXT")

    c.execute("PRAGMA table_info(interventions)")
    inter_cols = [info[1] for info in c.fetchall()]
    if 'project_name' not in inter_cols:
        c.execute("ALTER TABLE interventions ADD COLUMN project_name TEXT DEFAULT 'Factory'")

    c.execute("PRAGMA table_info(iterations)")
    iter_cols = [info[1] for info in c.fetchall()]
    if 'task' not in iter_cols:
        c.execute("ALTER TABLE iterations ADD COLUMN task TEXT")
    if 'plan' not in iter_cols:
        c.execute("ALTER TABLE iterations ADD COLUMN plan TEXT")
    if 'agents' not in iter_cols:
        c.execute("ALTER TABLE iterations ADD COLUMN agents TEXT")

    # 3. Seed Data
    c.execute("SELECT count(*) FROM iterations WHERE name = 'Factory'")
    if c.fetchone()[0] == 0:
        c.execute('''INSERT INTO iterations (name, baseline_project, model, skills, prompt, notes, task, plan, agents, created_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  ('Factory', 'Factory', 'Gemini Pro Latest', '', '', 'Initial default iteration', 'Initial Task', 'Initial Plan', '', datetime.now().isoformat()))

    conn.commit()
    conn.close()
    print("Database initialization complete.")

# --- STATE MANAGEMENT ---
blocking_event = asyncio.Event()
current_intervention = {"text": "Waiting for input...", "classification": None, "default_class": None}
current_project = "Factory"
current_progress = 0

@app.on_event("startup")
def startup():
    init_db()

    # Load last active iteration
    global current_project, current_progress
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT project_name, progress_percentage FROM traffic_log ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        if row:
            current_project = row[0]
            current_progress = row[1] if row[1] is not None else 0
            print(f"Restored active iteration: {current_project} (Progress: {current_progress}%)")
        conn.close()
    except Exception as e:
        print(f"Error restoring state: {e}")

def get_project_stats_data(project_name):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        start_time = None
        try:
            c.execute("SELECT MIN(timestamp) FROM traffic_log WHERE project_name = ?", (project_name,))
            start_traffic = c.fetchone()[0]
            c.execute("SELECT MIN(timestamp) FROM interventions WHERE project_name = ?", (project_name,))
            start_interv = c.fetchone()[0]
            if start_traffic and start_interv: start_time = min(start_traffic, start_interv)
            elif start_traffic: start_time = start_traffic
            elif start_interv: start_time = start_interv
        except: pass

        duration_str = "00:00:00"
        if start_time:
            try:
                delta = datetime.now() - datetime.fromisoformat(start_time)
                duration_str = str(delta).split('.')[0]
            except: pass

        c.execute("SELECT SUM(tokens_in), SUM(tokens_out) FROM traffic_log WHERE project_name = ?", (project_name,))
        row = c.fetchone()
        tokens_in, tokens_out = (row[0] or 0, row[1] or 0)

        c.execute("SELECT classification, COUNT(*) FROM interventions WHERE project_name = ? GROUP BY classification", (project_name,))
        interventions = {"NIT": 0, "ISSUE": 0, "PLANNED": 0}
        for r in c.fetchall():
            if r[0] in interventions: interventions[r[0]] = r[1]
        conn.close()

        total = sum(interventions.values())
        return {
            "duration": duration_str,
            "tokens": {"in": tokens_in, "out": tokens_out, "total": tokens_in + tokens_out},
            "interventions": {"nit": interventions["NIT"], "issue": interventions["ISSUE"], "planned": interventions["PLANNED"], "total": total},
            "progress": current_progress
        }
    except Exception as e:
        print(f"Stats Error: {e}")
        return {"duration": "Error", "tokens": {"total":0,"in":0,"out":0}, "interventions": {"total":0,"nit":0,"issue":0, "planned":0}, "progress": 0}

# --- API ENDPOINTS ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "project_name": current_project, "current_progress": current_progress})

@app.get("/status")
async def get_status():
    if not blocking_event.is_set() and current_intervention["classification"] is None:
         return {
             "status": "BLOCKED",
             "text": current_intervention["text"],
             "default_class": current_intervention["default_class"]
         }
    return {"status": "RUNNING"}

@app.get("/stats")
async def get_stats_endpoint(): return get_project_stats_data(current_project)

@app.get("/stats/chart_data")
async def get_chart_data():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    query = """
        SELECT strftime('%Y-%m-%dT%H:00:00', timestamp) as hour,
               SUM(tokens_in + tokens_out) as total_tokens,
               MAX(progress_percentage) as progress
        FROM traffic_log
        WHERE project_name = ?
        GROUP BY hour
        ORDER BY hour ASC
    """
    c.execute(query, (current_project,))
    rows = c.fetchall()
    conn.close()

    data = {
        "labels": [],
        "tokens": [],
        "progress": []
    }

    last_hour = None
    for r in rows:
        dt = datetime.fromisoformat(r[0])
        label = dt.strftime("%m-%d %H:00")
        data["labels"].append(label)
        data["tokens"].append(r[1])
        data["progress"].append(r[2])
        last_hour = label

    now = datetime.now()
    current_label = now.strftime("%m-%d %H:00")

    if last_hour != current_label:
        data["labels"].append(current_label + " (Now)")
        data["tokens"].append(0)
        data["progress"].append(current_progress)
    else:
        if len(data["progress"]) > 0:
            data["progress"][-1] = max(data["progress"][-1], current_progress)

    return data

@app.get("/history/traffic")
async def history_traffic():
    conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row
    rows = [dict(row) for row in conn.cursor().execute("SELECT * FROM traffic_log WHERE project_name = ? ORDER BY id DESC", (current_project,)).fetchall()]
    conn.close(); return rows

@app.get("/history/interventions")
async def history_interventions():
    conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row
    rows = [dict(row) for row in conn.cursor().execute("SELECT * FROM interventions WHERE project_name = ? ORDER BY id DESC", (current_project,)).fetchall()]
    conn.close(); return rows

@app.get("/iterations")
async def get_iterations():
    conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row
    names = [row['name'] for row in conn.cursor().execute("SELECT name FROM iterations ORDER BY created_at DESC").fetchall()]
    conn.close(); return names

@app.get("/iteration/{name}")
async def get_iteration(name: str):
    conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row
    row = conn.cursor().execute("SELECT * FROM iterations WHERE name = ?", (name,)).fetchone()
    conn.close(); return dict(row) if row else {}

@app.get("/agents_md", response_class=PlainTextResponse)
async def get_agents_md():
    try:
        with open("AGENTS.md", "r") as f:
            return f.read()
    except FileNotFoundError:
        return "AGENTS.md not found."

@app.post("/create_iteration")
async def create_iteration(request: Request):
    global current_project, current_progress
    data = await request.json()
    name = data.get("name")
    if not name: raise HTTPException(status_code=400, detail="Iteration name is required")

    conn = sqlite3.connect(DB_FILE)
    try:
        conn.cursor().execute('''INSERT INTO iterations (name, baseline_project, model, skills, prompt, notes, task, plan, agents, created_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (name, data.get("baseline_project", ""), data.get("model", ""), data.get("skills", ""), data.get("prompt", ""), data.get("notes", ""), data.get("task", ""), data.get("plan", ""), data.get("agents", ""), datetime.now().isoformat()))
        conn.commit()
    except sqlite3.IntegrityError: pass
    finally: conn.close()

    current_project = name; current_progress = 0
    return {"status": "ok", "project": current_project}

@app.post("/set_project")
async def set_project(request: Request):
    global current_project, current_progress
    data = await request.json(); new_name = data.get("name", "Factory")
    conn = sqlite3.connect(DB_FILE)
    exists = conn.cursor().execute("SELECT count(*) FROM iterations WHERE name = ?", (new_name,)).fetchone()[0] > 0
    if exists:
        current_project = new_name
        try:
            row = conn.cursor().execute("SELECT progress_percentage FROM traffic_log WHERE project_name = ? ORDER BY id DESC LIMIT 1", (current_project,)).fetchone()
            current_progress = row[0] if row else 0
        except: current_progress = 0
        conn.close()
        return {"status": "ok", "exists": True, "project": current_project, "progress": current_progress}
    conn.close()
    return {"status": "ok", "exists": False, "project": new_name}

@app.post("/set_progress")
async def set_progress(request: Request):
    global current_progress
    data = await request.json()
    current_progress = int(data.get("progress", 0)); return {"status": "ok", "progress": current_progress}

@app.post("/ask_permission")
async def ask_permission(request: Request):
    # global current_intervention # Not strictly needed if we don't update UI state for blocking
    data = await request.json()
    user_text = data.get("text", "").strip()

    # Heuristics
    classification = "ISSUE"
    if user_text.lower() in ["proceed", "execute", "execute!", "continue"]:
        classification = "PLANNED"
    elif len(user_text.split()) <= 10:
        classification = "NIT"

    # Log immediately to DB
    conn = sqlite3.connect(DB_FILE)
    conn.cursor().execute("INSERT INTO interventions (timestamp, prompt_text, classification, project_name) VALUES (?, ?, ?, ?)",
                          (datetime.now().isoformat(), user_text, classification, current_project))
    conn.commit()
    conn.close()

    print(f"⚡ AUTO-RELEASED ({classification}): {user_text[:50]}...")
    # Don't touch blocking_event
    return {"status": "released", "classification": classification}

@app.post("/log_traffic")
async def log_traffic(request: Request):
    data = await request.json()
    conn = sqlite3.connect(DB_FILE)
    conn.cursor().execute("INSERT INTO traffic_log (timestamp, tokens_in, tokens_out, latency_ms, project_name, progress_percentage, prompt_text, full_response) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (datetime.now().isoformat(), data.get('tokens_in', 0), data.get('tokens_out', 0), data.get('latency_ms', 0), current_project, current_progress, data.get('prompt_text', ''), data.get('full_response', '')))
    conn.commit(); conn.close()
    return {"status": "logged"}

@app.post("/classify")
async def classify(request: Request):
    global current_intervention
    data = await request.json(); category = data.get("type")
    conn = sqlite3.connect(DB_FILE)
    conn.cursor().execute("INSERT INTO interventions (timestamp, prompt_text, classification, project_name) VALUES (?, ?, ?, ?)", (datetime.now().isoformat(), current_intervention["text"], category, current_project))
    conn.commit(); conn.close()
    current_intervention["classification"] = category; blocking_event.set()
    return {"status": "ok"}

# New Endpoint to Update Classification History
@app.post("/update_classification")
async def update_classification(request: Request):
    data = await request.json()
    record_id = data.get("id")
    new_class = data.get("classification")

    conn = sqlite3.connect(DB_FILE)
    conn.cursor().execute("UPDATE interventions SET classification = ? WHERE id = ?", (new_class, record_id))
    conn.commit()
    conn.close()
    return {"status": "ok"}

if __name__ == "__main__":
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000)