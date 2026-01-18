"""
Student Trading Algorithm - The Spray and Pray
==============================================
STRATEGY: HIGH-FREQUENCY SPRAY (Inventory Cycling)
TARGET: Normal Market

MECHANICS:
1. Maintain a 'stack' of up to 45 open orders.
2. Continuously place orders at the best possible price (Bid+0.01 / Ask-0.01).
3. As orders fill, immediately replace them.
4. Rely on the sheer volume of orders to catch market moves.
"""

import json
import websocket
import threading
import argparse
import time
import requests
import ssl
import urllib3
import pickle
import xgboost as xgb
import math
import os
from typing import Dict, Optional, Any, List
from collections import deque

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class TradingBot:
    def __init__(
        self,
        student_id: str,
        host: str,
        scenario: str,
        password: str = None,
        secure: bool = False,
        regime_model_path: str = None,
        regime_meta_path: str = None,
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

        # Trading state
        self.inventory = 0
        self.cash_flow = 0.0
        self.pnl = 0.0
        self.current_step = 0
        self.orders_sent = 0

        # Market data
        self.last_bid = 0.0
        self.last_ask = 0.0
        self.last_mid = 0.0
        self.price_history = deque(maxlen=20)

        # Connections
        self.market_ws = None
        self.order_ws = None
        self.running = True

        # State for Strategies
        self.order_limit_max = 100  # OVERRIDE: We need speed
        self.last_known_inventory = 0
        self.flip_flop = False  # Used to alternate Buy/Sell placement

        # Spray Management
        self.open_order_count = 0  # Track active orders locally
        self.max_spray_count = 45  # Leave buffer of 5 for safety

        # Track our own prices to avoid jumping ourselves
        self.my_last_bid = 0.0
        self.my_last_ask = 0.0

    # =========================================================================
    # CORE INFRASTRUCTURE
    # =========================================================================

    def register(self) -> bool:
        print(f"[{self.student_id}] Registering for scenario '{self.scenario}'...")
        try:
            # Adding a small delay to ensure simulation startup synchronization
            url = f"{self.http_proto}://{self.host}/api/replays/{self.scenario}/start?delay=3"
            headers = {"Authorization": f"Bearer {self.student_id}"}
            if self.password:
                headers["X-Team-Password"] = self.password

            resp = requests.get(
                url, headers=headers, timeout=10, verify=not self.secure
            )
            if resp.status_code != 200:
                print(f"[{self.student_id}] Registration FAILED: {resp.text}")
                return False

            data = resp.json()
            self.token = data.get("token")
            self.run_id = data.get("run_id")
            print(f"[{self.student_id}] Registered! Run ID: {self.run_id}")
            return True
        except Exception as e:
            print(f"Registration Error: {e}")
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
                on_open=lambda ws: print(f"[{self.student_id}] Market Data Connected"),
            )
            order_url = f"{self.ws_proto}://{self.host}/api/ws/orders?token={self.token}&run_id={self.run_id}"
            self.order_ws = websocket.WebSocketApp(
                order_url,
                on_message=self._on_order_response,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=lambda ws: print(f"[{self.student_id}] Order Entry Connected"),
            )
            threading.Thread(
                target=lambda: self.market_ws.run_forever(sslopt=sslopt), daemon=True
            ).start()
            threading.Thread(
                target=lambda: self.order_ws.run_forever(sslopt=sslopt), daemon=True
            ).start()
            time.sleep(1)
            return True
        except Exception as e:
            print(f"Connection Error: {e}")
            return False

    # =========================================================================
    # STRATEGY LOGIC
    # =========================================================================

    def decide_order(self, bid: float, ask: float, mid: float) -> Optional[Dict]:
        """
        STRATEGY: SPRAY AND PRAY
        """
        if bid <= 0 or ask <= 0:
            return None

        # ------------------------------------------------------------------
        # 1. INVENTORY PROTECTION (DUMP VALVE)
        # ------------------------------------------------------------------
        # Emergency unwind if we get too heavy.
        if self.inventory > 1000:
            bot_bid = math.floor(bid / 0.25) * 0.25
            return self._create_order("SELL", bot_bid, 100)

        elif self.inventory < -1000:
            bot_ask = math.ceil(ask / 0.25) * 0.25
            return self._create_order("BUY", bot_ask, 100)

        # ------------------------------------------------------------------
        # 2. THE SPRAY (Capacity Check)
        # ------------------------------------------------------------------
        # If we have too many orders open, we stop firing.
        # This prevents the server from disconnecting us.
        if self.open_order_count >= self.max_spray_count:
            return None

        # ------------------------------------------------------------------
        # 3. PRICE CALCULATION (Adaptive Anti-Spiral)
        # ------------------------------------------------------------------
        # We calculate the aggressive price, but ensure we don't spiral.
        # If the top of book is US, we re-affirm it (stacking depth).
        # If the top of book is SOMEONE ELSE, we jump them.

        if abs(bid - self.my_last_bid) < 0.001:
            my_bid = bid
        else:
            my_bid = round(bid + 0.01, 2)

        if abs(ask - self.my_last_ask) < 0.001:
            my_ask = ask
        else:
            my_ask = round(ask - 0.01, 2)

        # Spread Safety
        if my_bid >= my_ask:
            return None

        # ------------------------------------------------------------------
        # 4. EXECUTION (Alternating Fire)
        # ------------------------------------------------------------------
        self.flip_flop = not self.flip_flop
        qty = 100

        if self.flip_flop:
            self.my_last_bid = my_bid
            return self._create_order("BUY", my_bid, qty)
        else:
            self.my_last_ask = my_ask
            return self._create_order("SELL", my_ask, qty)

    # =========================================================================
    # HELPERS & HANDLERS
    # =========================================================================

    def _create_order(self, side: str, price: float, qty: int) -> Dict:
        return {"side": side, "price": price, "qty": qty}

    def _on_market_data(self, ws, message: str):
        try:
            data = json.loads(message)
            if data.get("type") == "CONNECTED":
                return

            self.current_step = data.get("step", 0)
            self.last_bid = data.get("bid", 0.0)
            self.last_ask = data.get("ask", 0.0)
            self.last_mid = (
                (self.last_bid + self.last_ask) / 2
                if (self.last_bid and self.last_ask)
                else 0
            )

            # Log status regularly
            if self.current_step % 200 == 0:
                print(
                    f"Step {self.current_step} | Inv: {self.inventory} | PnL: {self.pnl:.2f} | Stack: {self.open_order_count}"
                )

            order = self.decide_order(self.last_bid, self.last_ask, self.last_mid)
            if order:
                self._send_order(order)
            self._send_done()
        except Exception as e:
            print(f"Market Error: {e}")

    def _send_order(self, order: Dict):
        order_id = f"ORD_{self.current_step}_{self.orders_sent}"
        msg = {
            "order_id": order_id,
            "side": order["side"],
            "price": order["price"],
            "qty": order["qty"],
        }
        try:
            self.order_ws.send(json.dumps(msg))
            self.orders_sent += 1
            self.open_order_count += 1  # Track open order
        except:
            pass

    def _send_done(self):
        try:
            self.order_ws.send(json.dumps({"action": "DONE"}))
        except:
            pass

    def _on_order_response(self, ws, message: str):
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "FILL":
                # We got a fill! This frees up a slot in our stack.
                self.open_order_count = max(0, self.open_order_count - 1)

                qty = data.get("qty", 0)
                price = data.get("price", 0.0)
                side = data.get("side", "")
                if side == "BUY":
                    self.inventory += qty
                    self.cash_flow -= qty * price
                else:
                    self.inventory -= qty
                    self.cash_flow += qty * price
                self.pnl = self.cash_flow + (self.inventory * self.last_mid)

                print(
                    f"[{self.student_id}] >>> FILL: {side} {qty} @ {price:.2f} | PnL: {self.pnl:.2f} | Stack: {self.open_order_count}"
                )

            elif msg_type == "ERROR":
                # If we hit the limit, max out our counter to stop firing
                if "limit" in data.get("message", "").lower():
                    print(f"[{self.student_id}] HIT LIMIT. Pausing spray.")
                    self.open_order_count = 50
        except:
            pass

    def _on_error(self, ws, error):
        if self.running:
            print(f"WS Error: {error}")

    def _on_close(self, ws, *args):
        self.running = False
        print("Connection Closed")

    def run(self):
        if self.register() and self.connect():
            print(f"[{self.student_id}] Spray and Pray Running...")
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("Stopped.")
            finally:
                self.running = False
                if self.market_ws:
                    self.market_ws.close()
                if self.order_ws:
                    self.order_ws.close()
                print(f"Final PnL: {self.pnl:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--scenario", default="normal_market")
    parser.add_argument("--host", default="localhost:8080")
    parser.add_argument("--secure", action="store_true")
    args = parser.parse_args()

    bot = TradingBot(args.name, args.host, args.scenario, args.password, args.secure)
    bot.run()
