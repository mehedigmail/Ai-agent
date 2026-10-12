# Trade with Tahir AI Bot — Demo Terminal

A local Python dashboard recreation with an explainable technical-analysis signal engine, generated sample candles, and a virtual-funds-only position simulator. **This application does not connect to broker accounts and cannot place real-money trades.** The sample feed is synthetic and is not market data. Signals are informational examples, not financial advice or predictions of guaranteed outcomes.

## Requirements

- Python 3.10 or newer
- `pip`
- A browser on the same device, or a browser that can reach the host running Flask

## Install and start

From the project directory, run:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` in the device browser. On Android, use the Python environment/terminal provided by your IDE and open the same URL in the device browser. If the IDE runs its terminal in an isolated container or does not expose local ports, try `http://localhost:5000`; if neither address is reachable, that IDE does not expose its local Python server to the browser. Run the app in an environment that exposes port 5000 or use its port-forwarding feature. The app binds to `0.0.0.0:5000` for local-network access; only expose it on a trusted network.

For a simple CLI analysis (does not trade):

```sh
python main.py
```

Run tests from the project root:

```sh
python -m unittest discover -s tests -v
```

## Dashboard use

- Pick an asset in the top tabs or the trading panel. Every asset is generated sample data.
- Adjust investment and duration in the trade panel. UP/DOWN place a single virtual position.
- Start Trading runs an analysis loop; eligible BUY/SELL signals can open simulated positions. Stop Trading stops new agent activity; an already-open position remains visible and settles at expiry.
- A sample candle advances every second while the autonomous agent is on. The countdown, demo balance, signal, and trade history refresh without page reloads.
- Settings configure the starting virtual balance, stake, duration, sample source, SMA/RSI periods, maximum stake, maximum consecutive losses, and cumulative-loss stop. Reset restores defaults and clears demo history.

## Architecture

- `config.py`: validated defaults and settings.
- `data_engine.py`: OHLC candle schema, sample generator, and future provider protocol.
- `ai_brain.py`: SMA/RSI analysis; returns BUY, SELL, or WAIT with indicators and a reason.
- `execution.py`: locked DEMO-only virtual position simulator with deterministic settlement by supplied expiry price.
- `app.py`: Flask UI/API and background agent loop.
- `templates/index.html`, `static/style.css`, `static/app.js`: responsive single-page dashboard, canvas candlesticks, and API client.
- `tests/test_trading_app.py`: standard-library unit and API tests.

The autonomous agent uses seeded-generated sample candles and rule-based technical analysis, not a trained model. The “QuantumEdge AI v3.2” label is a UI model-status identity only; it does not imply an external or machine-learning model. Demo payout rate is illustrative. A future real-data provider must be implemented and evaluated separately; no real execution adapter is included.
