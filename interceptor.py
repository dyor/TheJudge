# interceptor.py
from mitmproxy import http
import json
import time
import requests
import traceback

# Point this to your dashboard
DASHBOARD_URL = "http://localhost:8000"

class EvaluatorHook:
    def __init__(self):
        self.request_start_times = {}

    def request(self, flow: http.HTTPFlow):
        # Only watch Gemini traffic
        if "generativelanguage.googleapis.com" not in flow.request.pretty_host:
            return

        # 1. Start Timer (Store by flow ID in case of concurrent requests)
        self.request_start_times[flow.id] = time.time()

        # 2. Check for User Intervention
        try:
            payload = json.loads(flow.request.content)
            # Gemini JSON structure: contents -> parts -> text
            # We look for the LAST message sent by USER
            last_msg = payload.get('contents', [])[-1]

            # Simple Heuristic: If it has "text", ask for permission.
            if last_msg.get('role') == 'user':
                user_text = last_msg['parts'][0]['text']

                # === BLOCKING CALL ===
                # This freezes this specific request until Dashboard responds
                requests.post(f"{DASHBOARD_URL}/ask_permission", json={"text": user_text})

        except Exception:
            print(f"Error parsing request: {traceback.format_exc()}")
            pass

    def response(self, flow: http.HTTPFlow):
        if "generativelanguage.googleapis.com" not in flow.request.pretty_host:
            return

        # 3. Calculate Latency
        start_time = self.request_start_times.pop(flow.id, time.time())
        latency = (time.time() - start_time) * 1000

        # 4. Log Tokens
        metrics = {
            "tokens_in": 0,
            "tokens_out": 0,
            "latency_ms": latency,
            "full_response": "[Error capturing response]"
        }

        try:
            # Try to decode content
            try:
                content_str = flow.response.text # mitmproxy handles decoding (gzip etc)
            except Exception:
                content_str = str(flow.response.content)

            metrics["full_response"] = content_str

            # Logic to handle SSE (Server-Sent Events) format "data: {...}"
            if "data: " in content_str:
                final_usage = {}
                for line in content_str.splitlines():
                    line = line.strip()
                    if line.startswith("data: "):
                        try:
                            json_str = line[6:] # Strip "data: "
                            chunk = json.loads(json_str)
                            if "usageMetadata" in chunk:
                                final_usage = chunk["usageMetadata"]
                        except:
                            pass

                metrics["tokens_in"] = final_usage.get("promptTokenCount", 0)
                metrics["tokens_out"] = final_usage.get("candidatesTokenCount", 0)

            else:
                # Fallback to standard JSON parsing (non-streaming)
                data = json.loads(content_str)

                usage = {}
                if isinstance(data, list):
                    if len(data) > 0:
                        usage = data[-1].get("usageMetadata", {})
                elif isinstance(data, dict):
                    usage = data.get("usageMetadata", {})

                metrics["tokens_in"] = usage.get("promptTokenCount", 0)
                metrics["tokens_out"] = usage.get("candidatesTokenCount", 0)

        except Exception:
            print(f"Error parsing response: {traceback.format_exc()}")
            pass

        # Fire and forget logging
        try:
            requests.post(f"{DASHBOARD_URL}/log_traffic", json=metrics)
        except Exception as e:
            print(f"Failed to send logs to dashboard: {e}")

addons = [EvaluatorHook()]