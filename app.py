"""Flask web dashboard and API for a strictly virtual-funds trading demo."""

from datetime import datetime, timezone
import logging
import threading

from flask import Flask, jsonify, render_template, request

from ai_brain import analyze_market
from config import AGENT_NAME, VERSION, Settings, default_settings
from data_engine import DataEngine, SAMPLE_ASSETS
from execution import DemoTrader


class TradingService:
    def __init__(self, settings: Settings | None = None):
        self.settings = (settings or default_settings()).validate()
        self.data = DataEngine()
        self.trader = DemoTrader(self.settings.starting_balance, self.settings.max_investment,
                                 self.settings.payout_rate)
        self.analysis = analyze_market(self.data.get_candles(), fast_period=self.settings.sma_fast,
                                       slow_period=self.settings.sma_slow, rsi_period=self.settings.rsi_period)
        self.last_completed: dict | None = None
        self._lock = threading.RLock()
        self._worker_lock = threading.Lock()
        self._worker_started = False
        self._stop_event = threading.Event()
        self.consecutive_trades = 0
        self.realized_pnl = 0.0
        self.cumulative_losses = 0.0

    def ensure_worker(self) -> None:
        with self._worker_lock:
            if not self._worker_started:
                threading.Thread(target=self._worker, name="demo-agent", daemon=True).start()
                self._worker_started = True

    def _worker(self) -> None:
        while not self._stop_event.wait(1):
            if self.trader.agent_running or self.trader.open_position:
                try:
                    self.step()
                except Exception as exc:  # Keep errors visible and stop the autonomous loop safely.
                    logging.exception("Demo agent step failed")
                    self.trader.error = str(exc)
                    self.trader.agent_running = False
                    self.trader.state = "ERROR"

    def step(self, now: datetime | None = None) -> dict:
        """Advance sample prices, settle due positions and analyze one agent cycle."""
        with self._lock:
            current_time = now or datetime.now(timezone.utc)
            candle = self.data.advance_sample()
            position = self.trader.open_position
            if position and datetime.fromisoformat(position["expires_at"]) <= current_time:
                completed = self.trader.settle_position(candle.close, current_time)
                if completed:
                    self.last_completed = completed["trade"]
                    self.realized_pnl += completed["trade"]["profit_loss"]
                    self.cumulative_losses += max(0.0, -completed["trade"]["profit_loss"])
                    self.consecutive_trades += 1

            self.analysis = analyze_market(
                self.data.get_candles(), fast_period=self.settings.sma_fast,
                slow_period=self.settings.sma_slow, rsi_period=self.settings.rsi_period,
            )
            if not self.trader.agent_running:
                return self.snapshot()
            if self.cumulative_losses >= self.settings.max_demo_loss:
                self.trader.stop_agent()
                self.trader.state = "STOPPED"
                self.trader.error = "Maximum demo loss threshold reached; agent stopped."
            elif self.consecutive_trades >= self.settings.max_consecutive_trades:
                self.trader.stop_agent()
                self.trader.error = "Maximum consecutive demo trades reached; agent stopped."
            elif self.trader.open_position is None:
                signal = self.analysis["signal"]
                if signal in ("BUY", "SELL"):
                    order = self.trader.execute_trade(
                        "UP" if signal == "BUY" else "DOWN", candle.close,
                        self.settings.investment, self.settings.duration_seconds, self.data.asset, current_time,
                    )
                    if not order["success"]:
                        self.trader.error = order["message"]
                        self.trader.state = "ERROR"
            return self.snapshot()

    def start(self) -> dict:
        self.ensure_worker()
        self.trader.start_agent()
        self.trader.error = None
        return self.snapshot()

    def stop(self) -> dict:
        self.trader.stop_agent()
        return self.snapshot()

    def snapshot(self) -> dict:
        trader = self.trader.snapshot()
        position = trader["open_position"]
        state = "DEMO TRADE OPEN" if position else trader["state"]
        if trader["agent_running"] and not position and self.analysis["signal"] in ("BUY", "SELL"):
            state = "SIGNAL FOUND"
        return {
            "agent_name": AGENT_NAME, "version": VERSION, "model": "QuantumEdge AI v3.2",
            "mode": "DEMO ONLY", "asset": self.data.asset, "account_mode": "DEMO",
            "balance": trader["balance"], "initial_balance": trader["initial_balance"],
            "agent_running": trader["agent_running"], "state": state, "error": trader["error"],
            "signal": self.analysis, "latest_price": self.data.latest_price(),
            "candles": [candle.to_dict() for candle in self.data.get_candles(100)],
            "history": trader["history"], "open_position": position,
            "settings": self.settings.as_dict(), "assets": list(SAMPLE_ASSETS),
            "payout_estimate": round(self.settings.investment * self.settings.payout_rate, 2),
            "payout_rate": self.settings.payout_rate, "data_label": "SAMPLE DATA — generated, not live",
            "server_time": datetime.now(timezone.utc).isoformat(),
        }

    def select_asset(self, asset: str) -> None:
        if asset not in SAMPLE_ASSETS:
            raise ValueError("Select one of the available sample assets.")
        if self.trader.open_position:
            raise ValueError("Cannot change asset while a demo trade is open.")
        self.data.select_asset(asset)
        self.analysis = analyze_market(self.data.get_candles(), fast_period=self.settings.sma_fast,
                                       slow_period=self.settings.sma_slow, rsi_period=self.settings.rsi_period)

    def update_settings(self, values: dict) -> None:
        unknown = set(values) - set(Settings.__dataclass_fields__)
        if unknown:
            raise ValueError(f"Unknown setting: {sorted(unknown)[0]}")
        proposed = Settings.from_mapping({**self.settings.as_dict(), **values})
        if self.trader.open_position and (
            proposed.starting_balance != self.settings.starting_balance
            or proposed.max_investment != self.settings.max_investment
            or proposed.payout_rate != self.settings.payout_rate
        ):
            raise ValueError("Balance and execution settings cannot change while a trade is open.")
        with self.trader._lock:
            if proposed.starting_balance != self.settings.starting_balance:
                self.trader.initial_balance = proposed.starting_balance
                self.trader.balance = proposed.starting_balance
                self.trader.trades.clear()
                self.realized_pnl = 0.0
                self.cumulative_losses = 0.0
                self.consecutive_trades = 0
            self.trader.max_investment = proposed.max_investment
            self.trader.payout_rate = proposed.payout_rate
        self.settings = proposed
        self.analysis = analyze_market(self.data.get_candles(), fast_period=proposed.sma_fast,
                                       slow_period=proposed.sma_slow, rsi_period=proposed.rsi_period)

    def reset_settings(self) -> None:
        self.stop()
        self.settings = default_settings()
        self.data = DataEngine()
        self.trader = DemoTrader(self.settings.starting_balance, self.settings.max_investment,
                                 self.settings.payout_rate)
        self.consecutive_trades = 0
        self.realized_pnl = 0.0
        self.cumulative_losses = 0.0
        self.last_completed = None
        self.analysis = analyze_market(self.data.get_candles(), fast_period=self.settings.sma_fast,
                                       slow_period=self.settings.sma_slow, rsi_period=self.settings.rsi_period)


def create_app(service: TradingService | None = None) -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.trading_service = service or TradingService()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/status")
    def status():
        return jsonify(app.trading_service.snapshot())

    @app.post("/api/agent/start")
    def start_agent():
        return jsonify(app.trading_service.start())

    @app.post("/api/agent/stop")
    def stop_agent():
        return jsonify(app.trading_service.stop())

    @app.post("/api/trade")
    def manual_trade():
        payload = request.get_json(silent=True) or {}
        result = app.trading_service.trader.execute_trade(
            payload.get("direction", ""), app.trading_service.data.latest_price(),
            payload.get("investment", app.trading_service.settings.investment),
            payload.get("duration_seconds", app.trading_service.settings.duration_seconds),
            app.trading_service.data.asset,
        )
        if not result["success"]:
            return jsonify({"error": result["message"]}), 400
        app.trading_service.ensure_worker()
        return jsonify({"trade": result["trade"], "balance": result["balance"]}), 201

    @app.post("/api/asset")
    def select_asset():
        payload = request.get_json(silent=True) or {}
        try:
            app.trading_service.select_asset(payload.get("asset", ""))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(app.trading_service.snapshot())

    @app.patch("/api/settings")
    def update_settings():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "A JSON settings object is required."}), 400
        try:
            app.trading_service.update_settings(payload)
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(app.trading_service.snapshot())

    @app.post("/api/settings/reset")
    def reset_settings():
        app.trading_service.reset_settings()
        return jsonify(app.trading_service.snapshot())

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "Not found."}), 404

    return app


app = create_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
