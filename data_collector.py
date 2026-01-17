"""
Data Collector - High Performance Edition
=========================================
Passively records market data to Parquet files.
Optimized for speed: No arbitrary sleeps, smart polling, fast I/O.
"""

import json
import threading
import argparse
import time
import requests
import ssl
import sys
import urllib3
import pandas as pd
from datetime import datetime
from typing import Dict, Optional

# --- GUARD CLAUSE 1: LIBRARY CHECK ---
try:
    import websocket

    if not hasattr(websocket, "WebSocketApp"):
        raise AttributeError("Missing WebSocketApp")
except (ImportError, AttributeError):
    print("\n" + "=" * 60)
    print("CRITICAL ERROR: WRONG WEBSOCKET LIBRARY DETECTED")
    print("=" * 60)
    print("You have the old 'websocket' package installed.")
    print("You need 'websocket-client'.\n")
    print("RUN THESE COMMANDS TO FIX IT:")
    print("   pip uninstall websocket -y")
    print("   pip install websocket-client")
    print("=" * 60 + "\n")
    sys.exit(1)

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class DataCollector:
    def __init__(
        self,
        student_id: str,
        host: str,
        scenario: str,
        password: str = None,
        secure: bool = False,
    ):
        self.student_id = student_id
        self.host = host
        self.scenario = scenario
        self.password = password
        self.secure = secure

        self.http_proto = "https" if secure else "http"
        self.ws_proto = "wss" if secure else "ws"

        self.token = None
        self.run_id = None

        self.data_buffer = []
        self.running = True
        self.current_step = 0

        self.market_ws = None
        self.order_ws = None

    def register(self) -> bool:
        """Register with the server (and kill zombies)."""
        print(f"[{self.student_id}] Registering for scenario '{self.scenario}'...")

        headers = {"Authorization": f"Bearer {self.student_id}"}
        if self.password:
            headers["X-Team-Password"] = self.password

        # --- ZOMBIE KILLER (Optimized) ---
        try:
            stop_url = (
                f"{self.http_proto}://{self.host}/api/replays/{self.scenario}/stop"
            )
            requests.post(stop_url, headers=headers, timeout=2, verify=not self.secure)
            # Reduced sleep: just enough for the server to process the DB write
            time.sleep(0.2)
        except:
            pass

        try:
            url = f"{self.http_proto}://{self.host}/api/replays/{self.scenario}/start"
            resp = requests.get(
                url, headers=headers, timeout=10, verify=not self.secure
            )

            if resp.status_code != 200:
                print(f"Registration FAILED: {resp.text}")
                return False

            data = resp.json()
            self.token = data.get("token")
            self.run_id = data.get("run_id")

            if not self.token or not self.run_id:
                print(f"[{self.student_id}] Missing token or run_id")
                return False

            print(f"[{self.student_id}] Collecting data for Run ID: {self.run_id}")
            return True

        except Exception as e:
            print(f"Registration error: {e}")
            return False

    def connect(self) -> bool:
        try:
            sslopt = {"cert_reqs": ssl.CERT_NONE} if self.secure else None

            market_url = (
                f"{self.ws_proto}://{self.host}/api/ws/market?run_id={self.run_id}"
            )
            self.market_ws = websocket.WebSocketApp(
                market_url,
                on_message=self._on_market_data,
                on_error=self._on_error,
                on_close=self._on_close,
            )

            order_url = f"{self.ws_proto}://{self.host}/api/ws/orders?token={self.token}&run_id={self.run_id}"
            self.order_ws = websocket.WebSocketApp(
                order_url,
                on_message=self._on_order_response,
                on_error=self._on_error,
                on_close=self._on_close,
            )

            threading.Thread(
                target=lambda: self.market_ws.run_forever(sslopt=sslopt), daemon=True
            ).start()
            threading.Thread(
                target=lambda: self.order_ws.run_forever(sslopt=sslopt), daemon=True
            ).start()

            # --- SMART POLLING (No 1s sleep) ---
            print(f"[{self.student_id}] Connecting sockets...", end="", flush=True)
            for _ in range(50):  # Wait up to 2.5s total (50 * 0.05)
                if (
                    self.market_ws.sock
                    and self.market_ws.sock.connected
                    and self.order_ws.sock
                    and self.order_ws.sock.connected
                ):
                    print(" Connected!")
                    return True
                time.sleep(0.05)

            print(" Timeout waiting for sockets.")
            return False

        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def _on_market_data(self, ws, message: str):
        try:
            # OPTIMIZATION: Parse fast
            data = json.loads(message)
            if data.get("type") == "CONNECTED":
                return

            self.current_step = data.get("step", 0)
            bid = data.get("bid", 0.0)
            ask = data.get("ask", 0.0)

            # Calculate Mid
            mid = (
                (bid + ask) / 2 if (bid > 0 and ask > 0) else (bid if bid > 0 else ask)
            )

            # RECORD DATA
            # We store as tuple or dict. Dict is fine for modern Python.
            self.data_buffer.append(
                {
                    "step": self.current_step,
                    "bid": bid,
                    "ask": ask,
                    "mid": mid,
                    "spread": ask - bid,
                    "scenario": self.scenario,
                    "timestamp": time.time(),
                }
            )

            # Log periodically
            if self.current_step % 50 == 0 or self.current_step < 10:
                print(
                    f"[{self.scenario}] Step {self.current_step} | Collected {len(self.data_buffer)} rows..."
                )

            # PASSIVE MODE: Send DONE immediately.
            self._send_done()

        except Exception as e:
            print(f"Market data error: {e}")

    def _send_done(self):
        try:
            # Fail fast if socket is dead, don't wait
            if self.order_ws and self.order_ws.sock:
                self.order_ws.send(json.dumps({"action": "DONE"}))
        except:
            pass

    def _on_order_response(self, ws, message):
        pass

    def _on_error(self, ws, error):
        if self.running:
            print(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        self.running = False

    def save_data(self):
        if not self.data_buffer:
            print("No data collected to save.")
            return

        print(f"\nProcessing {len(self.data_buffer)} rows...")
        try:
            df = pd.DataFrame(self.data_buffer)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"training_data_{self.scenario}_v2.parquet"
            df.to_parquet(filename, index=False)
            print(f"SUCCESS: Data saved to {filename}")
        except Exception as e:
            print(f"ERROR SAVING DATA: {e}")
            try:
                filename = f"training_data_{self.scenario}_v2.csv"
                df.to_csv(filename, index=False)
                print(f"Saved as CSV instead: {filename}")
            except:
                pass

    def run(self):
        if not self.register() or not self.connect():
            return

        print(
            f"[{self.student_id}] STARTING COLLECTION. Press Ctrl+C to finish and save."
        )
        try:
            while self.running:
                # Fast heartbeat check
                time.sleep(0.1)
        except KeyboardInterrupt:
            print(f"\n[{self.student_id}] Stopping collection...")
        finally:
            self.running = False
            if self.market_ws:
                self.market_ws.close()
            if self.order_ws:
                self.order_ws.close()
            self.save_data()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--scenario", default="normal_market")
    parser.add_argument("--host", default="localhost:8080")
    parser.add_argument("--secure", action="store_true")
    args = parser.parse_args()

    bot = DataCollector(
        student_id=args.name,
        host=args.host,
        scenario=args.scenario,
        password=args.password,
        secure=args.secure,
    )
    bot.run()
