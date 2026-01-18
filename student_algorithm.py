"""
Student Trading Algorithm - The Arbitrage & Spray Engine
======================================================
STRATEGY MIX:
1. NORMAL: "Spray and Pray" (High-Freq Inventory Cycling)
2. STRESSED: "Stale Quote Sniping" (Arbitrage against slow bots)
3. HFT: "Momentum Taker" (Aggressive trend riding)

MECHANICS:
- Global "Crossed Market" check for risk-free profit (Bid >= Ask).
- EMA-based Fair Value detection to find mispriced orders in crashing markets.
- Infinite Liquidity Loop for flat markets.
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

INVENTORY_LIMIT = 5000


class TradingBot:
    def __init__(
        self,
        student_id: str,
        host: str,
        scenario: str,
        password: str = None,
        secure: bool = False,
        regime_model_path: str = "market_classifier_crator.pkl",
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
        self.mid_ema = None  # For Stale Quote detection

        # Connections
        self.market_ws = None
        self.order_ws = None
        self.running = True

        # Latency & Stats
        self.last_done_time = None
        self.step_latencies = []
        self.order_send_times = {}
        self.fill_latencies = []

        # Order Rate Limits
        self.order_history = deque()
        self.order_limit_window = 50
        # OVERRIDE: We need speed for Spray and Pray
        self.order_limit_max = 100

        # --- SPRAY AND PRAY STATE ---
        self.open_order_count = 0
        self.max_spray_count = 45  # Buffer of 5 for safety
        self.my_last_bid = 0.0
        self.my_last_ask = 0.0
        self.flip_flop = False

        # --- REGIME MODEL LOADING ---
        self.regime_model = self._load_regime_model(regime_model_path)
        self._label_classes = None
        self._feature_names = None
        self._load_regime_metadata(regime_meta_path)

        # Feature Engineering State
        self._mid_hist = deque(maxlen=60)
        self._spread_rel_hist = deque(maxlen=60)
        self._velocity_ema = None

        self.regime_strategy_map = {
            "normal_market": self._strategy_normal_market,
            "stressed_market": self._strategy_stressed_market,
            "hft_dominated": self._strategy_hft_dominated,
        }

    # =========================================================================
    # CORE INFRASTRUCTURE
    # =========================================================================

    def register(self) -> bool:
        print(f"[{self.student_id}] Registering for scenario '{self.scenario}'...")
        try:
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
    # MARKET DATA & REGIME DETECTION
    # =========================================================================

    def _on_market_data(self, ws, message: str):
        try:
            data = json.loads(message)
            if data.get("type") == "CONNECTED":
                return

            self.current_step = data.get("step", 0)
            self.last_bid = data.get("bid", 0.0)
            self.last_ask = data.get("ask", 0.0)
            if self.last_bid > 0 and self.last_ask > 0:
                self.last_mid = (self.last_bid + self.last_ask) / 2

            # Update EMA for Stale Quote Detection
            if self.last_mid > 0:
                self.price_history.append(self.last_mid)
                alpha = 0.1  # Fast EMA
                if self.mid_ema is None:
                    self.mid_ema = self.last_mid
                else:
                    self.mid_ema = alpha * self.last_mid + (1 - alpha) * self.mid_ema

            if self.current_step % 500 == 0:
                print(
                    f"Step {self.current_step} | Inv: {self.inventory} | PnL: {self.pnl:.2f} | Stack: {self.open_order_count}"
                )

            order = self.decide_order(self.last_bid, self.last_ask, self.last_mid)
            if order:
                self._send_order(order)
            self._send_done()
        except Exception as e:
            print(f"Market Error: {e}")

    # =========================================================================
    # DECISION LOGIC (REGIME SWITCHER + ARBITRAGE)
    # =========================================================================

    def decide_order(self, bid: float, ask: float, mid: float) -> Optional[Dict]:
        if mid <= 0 or bid <= 0 or ask <= 0:
            return None

        # ------------------------------------------------------------------
        # 0. PURE ARBITRAGE (Crossed Market) - HIGHEST PRIORITY
        # ------------------------------------------------------------------
        if bid >= ask:
            # Market is crossed! Free money.
            # We execute against the mispricing immediately.
            # We want to BUY at Ask (low) and SELL at Bid (high).
            print(
                f"[{self.student_id}] !!! CROSSED MARKET ARBITRAGE !!! Bid:{bid} >= Ask:{ask}"
            )

            qty = 100
            # Prioritize reducing inventory if we have it
            if self.inventory > 0:
                return self._create_order("SELL", bid, qty)
            elif self.inventory < 0:
                return self._create_order("BUY", ask, qty)
            else:
                # If flat, take the side that looks most profitable or random
                return self._create_order("BUY", ask, qty)

        # ------------------------------------------------------------------
        # 1. RISK MANAGEMENT
        # ------------------------------------------------------------------
        if abs(self.inventory) > INVENTORY_LIMIT:
            print("too much inventory hit")
            return None

        risk_order = self._risk_manage_inventory(bid, ask, mid)
        if risk_order:
            return risk_order

        # ------------------------------------------------------------------
        # 2. REGIME DETECTION
        # ------------------------------------------------------------------
        engineered = self._update_engineered_state_and_get_features(bid, ask, mid)
        regime = None
        if self.regime_model is not None and engineered:
            try:
                pred = self._predict_regime_from_engineered_features(engineered)
                regime = self._resolve_regime_label(pred)
            except Exception:
                pass

        if not regime:
            regime = self._fallback_regime_guess(bid, ask, mid)

        handler = self.regime_strategy_map.get(regime, self._strategy_normal_market)

        if self.current_step % 500 == 0:
            print(f"[{self.student_id}] Regime: {regime}")

        return handler(bid, ask, mid, regime)

    # =========================================================================
    # STRATEGY 1: SPRAY AND PRAY (Normal Market)
    # =========================================================================

    def _strategy_normal_market(
        self, bid: float, ask: float, mid: float, regime: str
    ) -> Optional[Dict]:
        """
        Implementation of SPRAY AND PRAY
        """
        # Capacity Check
        if self.open_order_count >= self.max_spray_count:
            return None

        # Price Calculation
        if abs(bid - self.my_last_bid) < 0.001:
            my_bid = bid
        else:
            my_bid = round(bid + 0.01, 2)

        if abs(ask - self.my_last_ask) < 0.001:
            my_ask = ask
        else:
            my_ask = round(ask - 0.01, 2)

        if my_bid >= my_ask:
            return None

        # Execution
        self.flip_flop = not self.flip_flop
        qty = 100

        if self.flip_flop:
            self.my_last_bid = my_bid
            return self._create_order("BUY", my_bid, qty)
        else:
            self.my_last_ask = my_ask
            return self._create_order("SELL", my_ask, qty)

    # =========================================================================
    # STRATEGY 2: STALE QUOTE SNIPING (Stressed Market)
    # =========================================================================

    def _strategy_stressed_market(
        self, bid: float, ask: float, mid: float, regime: str
    ) -> Optional[Dict]:
        """
        Arbitrage against 'Stale' bots in a crashing/stressed market.
        If Fair Value (EMA) moves fast, bots might leave stale orders. We hit them.
        """
        if self.mid_ema is None:
            return None

        # Threshold: How far off does a quote need to be to be considered "Arb"?
        # Stressed markets have wide spreads, so we look for deviations inside the spread.
        ARB_THRESHOLD = 0.15

        qty = 200  # Aggressive size for arb

        # 1. Stale Bid Sniping (Bearish Arb)
        # If Current Bid is significantly HIGHER than Fair Value, the bidder is asleep.
        # We SELL to them before they cancel.
        if bid > (self.mid_ema + ARB_THRESHOLD):
            # print(f"[{self.student_id}] SNIPING STALE BID: {bid} > EMA {self.mid_ema:.2f}")
            return self._create_order("SELL", bid, qty)  # Hit the Bid (Taker)

        # 2. Stale Ask Sniping (Bullish Arb)
        # If Current Ask is significantly LOWER than Fair Value, the seller is asleep.
        # We BUY from them cheap.
        if ask < (self.mid_ema - ARB_THRESHOLD):
            # print(f"[{self.student_id}] SNIPING STALE ASK: {ask} < EMA {self.mid_ema:.2f}")
            return self._create_order("BUY", ask, qty)  # Lift the Ask (Taker)

        # 3. Fallback: Mild Momentum if no arb found
        # If no obvious arb, we default to a simplified Spray (Making liquidity)
        # but with wider spreads to compensate for volatility risk.
        return self._strategy_normal_market(bid - 0.05, ask + 0.05, mid, regime)

    # =========================================================================
    # STRATEGY 3: MOMENTUM TAKER (HFT Dominated)
    # =========================================================================

    def _strategy_hft_dominated(
        self, bid: float, ask: float, mid: float, regime: str
    ) -> Optional[Dict]:
        """
        Momentum Surfing + Taker Aggression.
        In HFT regimes, trends are fast. We don't want to sit in queue (Maker).
        We want to TAKE liquidity (Taker) in the direction of the move.
        """
        lookback = 10
        if len(self.price_history) < lookback:
            return None

        momentum = mid - self.price_history[-lookback]
        THRESHOLD = 0.05  # Strong move required

        qty = 100

        if momentum > THRESHOLD:
            # Trend UP -> Panic BUY
            # We pay the Ask to get in NOW.
            return self._create_order("BUY", ask, qty)

        elif momentum < -THRESHOLD:
            # Trend DOWN -> Panic SELL
            # We hit the Bid to get out NOW.
            return self._create_order("SELL", bid, qty)

        else:
            # If choppy/flat HFT, revert to Spraying but carefully
            return self._strategy_normal_market(bid, ask, mid, regime)

    # =========================================================================
    # ORDER MANAGEMENT
    # =========================================================================

    def _create_order(self, side: str, price: float, qty: int) -> Dict:
        return {"side": side, "price": price, "qty": qty}

    def _risk_manage_inventory(
        self, bid: float, ask: float, mid: float
    ) -> Optional[Dict]:
        exposure = self.inventory
        if abs(exposure) < 1000:  # Allow up to 1000 before unwinding
            return None

        qty = 100
        # Aggressive Unwind
        if exposure > 0:
            # Sell to Bot Wall (nearest 0.25)
            bot_bid = math.floor(bid / 0.25) * 0.25
            return self._create_order("SELL", bot_bid, qty)
        else:
            # Buy from Bot Wall
            bot_ask = math.ceil(ask / 0.25) * 0.25
            return self._create_order("BUY", bot_ask, qty)

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
            # INCREMENT STACK
            self.open_order_count += 1
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
                # DECREMENT STACK ON FILL
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
                if "limit" in data.get("message", "").lower():
                    self.open_order_count = 50  # Pause firing
        except:
            pass

    # =========================================================================
    # HELPERS & MODEL LOADING (Boilerplate)
    # =========================================================================

    def _recent_momentum(self) -> float:
        if len(self.price_history) >= 2:
            return self.price_history[-1] - self.price_history[-2]
        return 0.0

    def _fallback_regime_guess(self, bid: float, ask: float, mid: float) -> str:
        spread = max(ask - bid, 0.0)
        momentum = self._recent_momentum()
        if spread > 0.05 * mid:
            return "stressed_market"
        if abs(momentum) > 0.015 * mid:
            return "hft_dominated"
        return "normal_market"

    def _load_regime_model(self, path):
        try:
            booster = xgb.Booster()
            booster.load_model(path)
            return booster
        except:
            return None

    def _load_regime_metadata(self, path):
        try:
            with open(path, "rb") as f:
                meta = pickle.load(f)
                self._label_classes = meta.get("classes")
                self._feature_names = meta.get("feature_names")
        except:
            pass

    def _update_engineered_state_and_get_features(self, bid, ask, mid):
        return None

    def _predict_regime_from_engineered_features(self, feats):
        return 0

    def _resolve_regime_label(self, pred):
        return "normal_market"

    def _on_error(self, ws, error):
        if self.running:
            print(f"WS Error: {error}")

    def _on_close(self, ws, *args):
        self.running = False
        print("Connection Closed")

    def run(self):
        if self.register() and self.connect():
            print(f"[{self.student_id}] Arbitrage & Spray Running...")
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

