"""
Cancellation Capability Tester
==============================
Determines if the exchange supports the 'CANCEL' action.

Methodology:
1. Place a "Stink Bid" (Deep OTM) that won't fill.
2. Send a CANCEL request.
3. Analyze the server response (ACK, ERROR, or SILENCE).
"""

import json
import websocket
import threading
import argparse
import time
import requests
import ssl
import urllib3

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class CancelTester:
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
        self.market_ws = None
        self.order_ws = None
        self.running = True

        self.test_phase = "CONNECT"  # CONNECT -> PLACE -> CANCEL -> VERIFY
        self.test_order_id = "TEST_CANCEL_001"
        self.order_placed = False

    def register(self):
        print(f"[{self.student_id}] Registering...")
        try:
            url = f"{self.http_proto}://{self.host}/api/replays/{self.scenario}/start"
            headers = {"Authorization": f"Bearer {self.student_id}"}
            if self.password:
                headers["X-Team-Password"] = self.password

            resp = requests.get(
                url, headers=headers, timeout=10, verify=not self.secure
            )
            if resp.status_code != 200:
                return False

            data = resp.json()
            self.token = data.get("token")
            self.run_id = data.get("run_id")
            return True
        except:
            return False

    def connect(self):
        sslopt = {"cert_reqs": ssl.CERT_NONE} if self.secure else None

        # We only need Order WS for this test really, but Market WS keeps the sim alive
        m_url = f"{self.ws_proto}://{self.host}/api/ws/market?run_id={self.run_id}"
        self.market_ws = websocket.WebSocketApp(m_url, on_message=self._on_market)

        o_url = f"{self.ws_proto}://{self.host}/api/ws/orders?token={self.token}&run_id={self.run_id}"
        self.order_ws = websocket.WebSocketApp(
            o_url, on_message=self._on_order, on_open=self._on_open
        )

        threading.Thread(
            target=lambda: self.market_ws.run_forever(sslopt=sslopt), daemon=True
        ).start()
        threading.Thread(
            target=lambda: self.order_ws.run_forever(sslopt=sslopt), daemon=True
        ).start()
        time.sleep(1)
        return True

    def _on_market(self, ws, msg):
        # We assume market data works. We just need to keep the connection alive.
        pass

    def _on_open(self, ws):
        print(">>> Order Stream Connected. Starting Test sequence...")
        threading.Thread(target=self.run_test_sequence).start()

    def _on_order(self, ws, message):
        data = json.loads(message)
        msg_type = data.get("type")

        print(f"\n[SERVER RESPONSE] Type: {msg_type} | Payload: {data}")

        if msg_type == "ERROR":
            print("!!! TEST FAILED: Server returned ERROR. !!!")
            if "Unknown action" in data.get("message", ""):
                print(
                    "Reason: 'CANCEL' action is likely NOT supported or syntax is wrong."
                )

        if msg_type == "CANCELLED" or msg_type == "CANCELED":
            print("!!! TEST PASSED: Server confirmed CANCELLATION. !!!")
            print("We can safely use cancellations to manage the 50-order limit.")
            self.running = False

    def run_test_sequence(self):
        time.sleep(2)

        # 1. PLACE ORDER
        print(f"\n[STEP 1] Placing Stink Bid (ID: {self.test_order_id})...")
        # Buy @ $10.00 (Assuming market is ~1000, this will never fill)
        msg = {
            "order_id": self.test_order_id,
            "side": "BUY",
            "price": 10.00,
            "qty": 100,
        }
        self.order_ws.send(json.dumps(msg))

        time.sleep(2)

        # 2. CANCEL ORDER
        print(f"\n[STEP 2] Sending CANCEL request...")
        cancel_msg = {"action": "CANCEL", "order_id": self.test_order_id}
        print(f"Sending: {cancel_msg}")
        self.order_ws.send(json.dumps(cancel_msg))

        time.sleep(2)
        print("\n[STEP 3] Test Complete (Check logs above). Closing...")
        self.running = False
        self.market_ws.close()
        self.order_ws.close()

    def run(self):
        if self.register() and self.connect():
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--scenario", default="normal_market")
    parser.add_argument("--host", default="localhost:8080")
    parser.add_argument("--secure", action="store_true")
    args = parser.parse_args()

    bot = CancelTester(args.name, args.host, args.scenario, args.password, args.secure)
    bot.run()
