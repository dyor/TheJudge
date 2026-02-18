# dashboard.py
import sqlite3
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
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

    # New Table for Iteration Metadata
    c.execute('''CREATE TABLE IF NOT EXISTS iterations
                 (id INTEGER PRIMARY KEY,
                  name TEXT UNIQUE,
                  baseline_project TEXT,
                  model TEXT,
                  agent TEXT,
                  skills TEXT,
                  prompt TEXT,
                  notes TEXT,
                  created_at TEXT)''')

    # 2. Check and Migrate 'traffic_log'
    c.execute("PRAGMA table_info(traffic_log)")
    columns = [info[1] for info in c.fetchall()]

    if 'project_name' not in columns:
        print("Migrating: Adding 'project_name' to traffic_log")
        try:
            c.execute("ALTER TABLE traffic_log ADD COLUMN project_name TEXT DEFAULT 'Factory'")
        except Exception as e:
            print(f"Migration Error (traffic_log): {e}")

    if 'progress_percentage' not in columns:
        print("Migrating: Adding 'progress_percentage' to traffic_log")
        try:
            c.execute("ALTER TABLE traffic_log ADD COLUMN progress_percentage INT DEFAULT 0")
        except Exception as e:
            print(f"Migration Error (traffic_log): {e}")

    # 3. Check and Migrate 'interventions'
    c.execute("PRAGMA table_info(interventions)")
    columns = [info[1] for info in c.fetchall()]
    if 'project_name' not in columns:
        print("Migrating: Adding 'project_name' to interventions")
        try:
            c.execute("ALTER TABLE interventions ADD COLUMN project_name TEXT DEFAULT 'Factory'")
        except Exception as e:
            print(f"Migration Error (interventions): {e}")

    # 4. Ensure default iteration exists
    c.execute("SELECT count(*) FROM iterations WHERE name = 'Factory'")
    if c.fetchone()[0] == 0:
        print("Seeding default 'Factory' iteration metadata.")
        c.execute('''INSERT INTO iterations (name, baseline_project, model, agent, skills, prompt, notes, created_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  ('Factory', 'Factory', 'Gemini Pro Latest', 'Standard', '', '', 'Initial default iteration', datetime.now().isoformat()))

    conn.commit()
    conn.close()
    print("Database initialization complete.")

# --- STATE MANAGEMENT ---
blocking_event = asyncio.Event()
current_intervention = {"text": "Waiting for input...", "classification": None}
current_project = "Factory"
current_progress = 0

@app.on_event("startup")
def startup():
    init_db()

def get_project_stats_data(project_name):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # 1. Calculate Time Elapsed
        try:
            c.execute("SELECT MIN(timestamp) FROM traffic_log WHERE project_name = ?", (project_name,))
            start_traffic = c.fetchone()[0]
            c.execute("SELECT MIN(timestamp) FROM interventions WHERE project_name = ?", (project_name,))
            start_interv = c.fetchone()[0]
        except sqlite3.OperationalError as e:
            print(f"SQL Error in stats: {e}")
            return {"duration": "Error", "tokens": {"total":0,"in":0,"out":0}, "interventions": {"total":0,"nit":0,"issue":0}, "progress": 0}

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
            if r[0] in interventions:
                interventions[r[0]] = r[1]

        total_interventions = sum(interventions.values())
        conn.close()

        return {
            "duration": duration_str,
            "tokens": {
                "in": tokens_in,
                "out": tokens_out,
                "total": tokens_in + tokens_out
            },
            "interventions": {
                "nit": interventions["NIT"],
                "issue": interventions["ISSUE"],
                "total": total_interventions
            },
            "progress": current_progress
        }
    except Exception as e:
        print(f"Stats Error: {e}")
        return {"duration": "Error", "tokens": {"total":0,"in":0,"out":0}, "interventions": {"total":0,"nit":0,"issue":0}, "progress": 0}

# --- WEBPAGE UI ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "project_name": current_project, "current_progress": current_progress})

@app.get("/status")
async def get_status():
    if not blocking_event.is_set() and current_intervention["classification"] is None:
         return {"status": "BLOCKED", "text": current_intervention["text"]}
    return {"status": "RUNNING"}

@app.get("/stats")
async def get_stats_endpoint():
    return get_project_stats_data(current_project)

@app.get("/history/traffic")
async def history_traffic():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM traffic_log ORDER BY id DESC LIMIT 10")
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows

@app.get("/history/interventions")
async def history_interventions():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM interventions ORDER BY id DESC LIMIT 10")
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows

# --- ITERATION MANAGEMENT ---

@app.get("/iterations")
async def get_iterations():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT name FROM iterations ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [row['name'] for row in rows]

@app.get("/iteration/{name}")
async def get_iteration(name: str):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM iterations WHERE name = ?", (name,))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(row)
    else:
        return {}

@app.post("/create_iteration")
async def create_iteration(request: Request):
    global current_project, current_progress
    data = await request.json()

    name = data.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Iteration name is required")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    try:
        c.execute('''INSERT INTO iterations (name, baseline_project, model, agent, skills, prompt, notes, created_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (name,
                   data.get("baseline_project", "Default"),
                   data.get("model", "Gemini Pro Latest"),
                   data.get("agent", "Standard"),
                   data.get("skills", ""),
                   data.get("prompt", ""),
                   data.get("notes", ""),
                   datetime.now().isoformat()))
        conn.commit()
    except sqlite3.IntegrityError:
        # If it already exists, maybe update it? Or just pass.
        # Requirement was to create new.
        pass
    finally:
        conn.close()

    current_project = name
    current_progress = 0
    return {"status": "ok", "project": current_project}

@app.post("/set_project")
async def set_project(request: Request):
    global current_project, current_progress
    data = await request.json()
    new_name = data.get("name", "Factory")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT count(*) FROM iterations WHERE name = ?", (new_name,))
    exists = c.fetchone()[0] > 0
    conn.close()

    if exists:
        current_project = new_name
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT progress_percentage FROM traffic_log WHERE project_name = ? ORDER BY id DESC LIMIT 1", (current_project,))
            row = c.fetchone()
            current_progress = row[0] if row else 0
            conn.close()
        except:
            current_progress = 0

        return {"status": "ok", "exists": True, "project": current_project, "progress": current_progress}
    else:
        return {"status": "ok", "exists": False, "project": new_name}

@app.post("/set_progress")
async def set_progress(request: Request):
    global current_progress
    data = await request.json()
    current_progress = int(data.get("progress", 0))
    return {"status": "ok", "progress": current_progress}

# --- MITMPROXY ENDPOINTS ---
@app.post("/ask_permission")
async def ask_permission(request: Request):
    data = await request.json()
    global current_intervention
    current_intervention["text"] = data.get("text", "")
    current_intervention["classification"] = None
    blocking_event.clear()
    print(f"🚨 INTERVENTION NEEDED: {data.get('text')[:50]}...")
    await blocking_event.wait()
    return {"status": "released", "classification": current_intervention["classification"]}

@app.post("/log_traffic")
async def log_traffic(request: Request):
    data = await request.json()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO traffic_log (timestamp, tokens_in, tokens_out, latency_ms, project_name, progress_percentage) VALUES (?, ?, ?, ?, ?, ?)",
              (datetime.now().isoformat(), data.get('tokens_in', 0), data.get('tokens_out', 0), data.get('latency_ms', 0), current_project, current_progress))
    conn.commit()
    conn.close()
    return {"status": "logged"}

@app.post("/classify")
async def classify(request: Request):
    data = await request.json()
    category = data.get("type")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO interventions (timestamp, prompt_text, classification, project_name) VALUES (?, ?, ?, ?)",
              (datetime.now().isoformat(), current_intervention["text"], category, current_project))
    conn.commit()
    conn.close()
    current_intervention["classification"] = category
    blocking_event.set()
    return {"status": "ok"}

if __name__ == "__main__":
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000)