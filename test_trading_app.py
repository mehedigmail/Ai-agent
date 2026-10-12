import math
import unittest
from datetime import datetime, timezone

from ai_brain import analyze_market, calculate_rsi
from app import TradingService, create_app
from config import Settings, default_settings
from data_engine import Candle, DataEngine
from execution import DemoTrader


class AnalysisTests(unittest.TestCase):
    def test_insufficient_and_invalid_data_return_wait(self):
        self.assertEqual(analyze_market([1, 2])['signal'], 'WAIT')
        self.assertEqual(analyze_market([1, 0, 3])['signal'], 'WAIT')
        self.assertEqual(analyze_market([1, math.nan])['signal'], 'WAIT')

    def test_indicators_and_direction(self):
        rising = [10 + index * 0.05 + (0.16 if index % 2 else -0.16) for index in range(30)]
        falling = [10 - index * 0.05 - (0.16 if index % 2 else -0.16) for index in range(30)]
        self.assertEqual(analyze_market(rising)['signal'], 'BUY')
        self.assertEqual(analyze_market(falling)['signal'], 'SELL')
        self.assertIsNotNone(analyze_market(rising)['indicators']['fast_sma'])
        self.assertGreater(calculate_rsi(rising, 14), 50.0)


class DataTests(unittest.TestCase):
    def test_sample_series_is_labeled_and_consistent(self):
        engine = DataEngine(seed=5)
        candles = engine.get_candles()
        self.assertEqual(len(candles), 80)
        self.assertIn('SAMPLE', candles[-1].source)
        self.assertEqual(engine.latest_price(), candles[-1].close)

    def test_invalid_candle_prices_and_time_rejected(self):
        with self.assertRaises(ValueError):
            Candle(datetime.now(timezone.utc).isoformat(), 1, 0.5, 0.8, 0.9).validate()
        with self.assertRaises(ValueError):
            Candle('not-a-date', 1, 2, 0.5, 1.5).validate()
        with self.assertRaises(ValueError):
            Candle(datetime.now(timezone.utc).isoformat(), '1', 2, 0.5, 1.5).validate()


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.trader = DemoTrader(1000, max_investment=300, payout_rate=0.8)
        self.now = datetime(2025, 1, 1, tzinfo=timezone.utc)

    def test_invalid_investment_insufficient_balance_and_overlap(self):
        self.assertFalse(self.trader.execute_trade('UP', 10, 0)['success'])
        self.assertFalse(self.trader.execute_trade('UP', 10, 400)['success'])
        self.trader.balance = 50
        self.assertIn('Insufficient', self.trader.execute_trade('UP', 10, 100)['message'])
        self.trader.balance = 1000
        self.assertTrue(self.trader.execute_trade('UP', 10, 100, now=self.now)['success'])
        self.assertFalse(self.trader.execute_trade('DOWN', 10, 100, now=self.now)['success'])

    def test_up_win_down_win_loss_draw_balance_and_history(self):
        self.trader.execute_trade('UP', 10, 100, now=self.now)
        result = self.trader.settle_position(11, self.now)
        self.assertEqual(result['trade']['result'], 'WIN')
        self.assertEqual(self.trader.balance, 1080)
        self.trader.execute_trade('DOWN', 10, 100, now=self.now)
        result = self.trader.settle_position(9, self.now)
        self.assertEqual(result['trade']['result'], 'WIN')
        self.assertEqual(self.trader.balance, 1160)
        self.trader.execute_trade('UP', 10, 100, now=self.now)
        result = self.trader.settle_position(9, self.now)
        self.assertEqual(result['trade']['result'], 'LOSS')
        self.assertEqual(self.trader.balance, 1060)
        self.assertEqual(len(self.trader.get_history()), 3)
        self.trader.execute_trade('UP', 10, 100, now=self.now)
        self.assertEqual(self.trader.settle_position(10, self.now)['trade']['result'], 'DRAW')
        self.assertEqual(self.trader.balance, 1060)

    def test_start_stop_state(self):
        self.assertEqual(self.trader.start_agent()['state'], 'ANALYZING')
        self.assertEqual(self.trader.stop_agent()['state'], 'STOPPED')
        self.assertFalse(self.trader.snapshot()['agent_running'])


class SettingsTests(unittest.TestCase):
    def test_invalid_settings_rejected(self):
        with self.assertRaises(ValueError):
            Settings.from_mapping({'investment': float('nan')})
        with self.assertRaises(ValueError):
            Settings.from_mapping({'duration_seconds': 30.5})
        with self.assertRaises(ValueError):
            Settings.from_mapping({'data_source': 'LIVE'})


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.service = TradingService(default_settings())
        self.client = create_app(self.service).test_client()

    def test_dashboard_status_and_settings_api(self):
        page = self.client.get('/')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'Trade with Tahir', page.data)
        response = self.client.get('/api/status')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['mode'], 'DEMO ONLY')
        self.assertIn('SAMPLE', response.json['data_label'])
        self.assertEqual(self.client.post('/api/agent/start').json['agent_running'], True)
        self.assertEqual(self.client.post('/api/agent/stop').json['agent_running'], False)
        self.assertEqual(self.client.patch('/api/settings', json={'investment': -4}).status_code, 400)
        self.assertEqual(self.client.patch('/api/settings', json={'sma_fast': 4, 'sma_slow': 15}).status_code, 200)
        self.assertEqual(self.client.post('/api/settings/reset').status_code, 200)

    def test_trade_and_asset_api_validation(self):
        self.assertEqual(self.client.post('/api/trade', json={'direction': 'UP', 'investment': -5}).status_code, 400)
        trade = self.client.post('/api/trade', json={'direction': 'UP', 'investment': 100, 'duration_seconds': 5})
        self.assertEqual(trade.status_code, 201)
        self.assertEqual(self.client.post('/api/trade', json={'direction': 'DOWN'}).status_code, 400)
        self.assertEqual(self.client.post('/api/asset', json={'asset': 'NOT_REAL'}).status_code, 400)
        self.assertEqual(self.client.post('/api/asset', json={'asset': 'BTC/USD'}).status_code, 400)  # position open

    def test_expired_manual_position_settles_after_agent_is_stopped(self):
        service = self.service
        opened = datetime(2020, 1, 1, tzinfo=timezone.utc)
        trade = service.trader.execute_trade('UP', service.data.latest_price(), 100, 5, now=opened)
        self.assertTrue(trade['success'])
        snapshot = service.step(now=datetime(2020, 1, 1, 0, 0, 10, tzinfo=timezone.utc))
        self.assertIsNone(snapshot['open_position'])
        self.assertEqual(len(snapshot['history']), 1)
        self.assertEqual(snapshot['state'], 'DEMO TRADE COMPLETED')


if __name__ == '__main__':
    unittest.main()
