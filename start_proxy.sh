#!/bin/bash

echo "Starting FastAPI Dashboard in the background..."
nohup python3 dashboard.py > dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo "Dashboard PID: $DASHBOARD_PID"

echo "Starting mitmproxy interceptor..."
echo "Press Ctrl+C to stop mitmproxy. You will then need to manually kill the dashboard process (PID: $DASHBOARD_PID)."
mitmdump -s interceptor.py

echo "Mitmproxy stopped. Killing dashboard process (PID: $DASHBOARD_PID)..."
kill $DASHBOARD_PID
echo "Dashboard process killed."
