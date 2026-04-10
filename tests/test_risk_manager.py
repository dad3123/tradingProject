import pytest
from risk_manager import calculate_trade_params, SymbolInfo


class TestCalculateTradeParams:
    def _symbol_info(self):
        return SymbolInfo(
            trade_tick_value=1.0,   # 1 USD per tick
            trade_tick_size=0.01,   # minimum price move
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
        )

    def test_buy_params(self):
        # account 10000, risk 1%, SL distance=100
        # risk_amount = 100 USD
        # sl_ticks = 100 / 0.01 = 10000
        # lots = 100 / (10000 * 1.0) = 0.01
        info = self._symbol_info()
        lots, sl, tp = calculate_trade_params(
            signal="BUY",
            entry_price=2000.0,
            trail=1900.0,        # SL 100 below entry
            account_balance=10000.0,
            risk_pct=1.0,
            rr_ratio=2.0,
            symbol_info=info,
        )
        assert abs(lots - 0.01) < 1e-9
        assert abs(sl - 1900.0) < 1e-9
        assert abs(tp - 2200.0) < 1e-9  # entry + 100*2

    def test_sell_params(self):
        info = self._symbol_info()
        lots, sl, tp = calculate_trade_params(
            signal="SELL",
            entry_price=2000.0,
            trail=2100.0,        # SL 100 above entry
            account_balance=10000.0,
            risk_pct=1.0,
            rr_ratio=2.0,
            symbol_info=info,
        )
        assert abs(lots - 0.01) < 1e-9
        assert abs(sl - 2100.0) < 1e-9
        assert abs(tp - 1800.0) < 1e-9  # entry - 100*2

    def test_lots_clamped_to_min(self):
        # Very large SL distance → lots will be extremely small → clamp to volume_min
        info = self._symbol_info()
        lots, sl, tp = calculate_trade_params(
            signal="BUY",
            entry_price=2000.0,
            trail=1000.0,        # SL distance=1000
            account_balance=100.0,
            risk_pct=1.0,
            rr_ratio=2.0,
            symbol_info=info,
        )
        assert lots >= info.volume_min

    def test_lots_clamped_to_max(self):
        info = self._symbol_info()
        lots, sl, tp = calculate_trade_params(
            signal="BUY",
            entry_price=2000.0,
            trail=1999.99,       # Tiny SL distance → huge lots → clamp to volume_max
            account_balance=1_000_000.0,
            risk_pct=10.0,
            rr_ratio=2.0,
            symbol_info=info,
        )
        assert lots <= info.volume_max
