import sqlite3

def check_db():
    try:
        conn = sqlite3.connect('eval_metrics.db')
        c = conn.cursor()

        # Check columns in traffic_log
        print("--- traffic_log columns ---")
        c.execute("PRAGMA table_info(traffic_log)")
        cols = c.fetchall()
        for col in cols:
            print(col)

        # Check columns in interventions
        print("\n--- interventions columns ---")
        c.execute("PRAGMA table_info(interventions)")
        cols = c.fetchall()
        for col in cols:
            print(col)

        # Check recent data
        print("\n--- Recent Traffic ---")
        c.execute("SELECT * FROM traffic_log ORDER BY id DESC LIMIT 5")
        rows = c.fetchall()
        for row in rows:
            print(row)

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db()