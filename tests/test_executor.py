import pytest
from unittest.mock import patch, MagicMock, call
from executor import has_open_position, place_order, get_symbol_info
from risk_manager import SymbolInfo


class TestHasOpenPosition:
    @patch('executor.mt5')
    def test_returns_true_when_position_exists(self, mock_mt5):
        mock_mt5.positions_get.return_value = (MagicMock(),)  # non-empty tuple
        assert has_open_position("XAUUSD") is True

    @patch('executor.mt5')
    def test_returns_false_when_no_position(self, mock_mt5):
        mock_mt5.positions_get.return_value = ()
        assert has_open_position("XAUUSD") is False

    @patch('executor.mt5')
    def test_returns_false_when_none(self, mock_mt5):
        mock_mt5.positions_get.return_value = None
        assert has_open_position("XAUUSD") is False


class TestPlaceOrder:
    def _mock_mt5_buy(self, mock_mt5):
        mock_mt5.positions_get.return_value = ()
        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TYPE_SELL = 1
        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TIME_GTC = 1
        mock_mt5.ORDER_FILLING_IOC = 1
        tick = MagicMock()
        tick.ask = 2000.0
        tick.bid = 1999.5
        mock_mt5.symbol_info_tick.return_value = tick
        result = MagicMock()
        result.retcode = 10009  # TRADE_RETCODE_DONE
        mock_mt5.order_send.return_value = result
        return result

    @patch('executor.mt5')
    def test_buy_order_placed(self, mock_mt5):
        expected_result = self._mock_mt5_buy(mock_mt5)
        result = place_order("XAUUSD", "BUY", lots=0.01, sl=1900.0, tp=2200.0)
        assert mock_mt5.order_send.called
        assert result.retcode == 10009

    @patch('executor.mt5')
    def test_no_order_when_position_exists(self, mock_mt5):
        mock_mt5.positions_get.return_value = (MagicMock(),)
        result = place_order("XAUUSD", "BUY", lots=0.01, sl=1900.0, tp=2200.0)
        assert result is None
        mock_mt5.order_send.assert_not_called()


class TestGetSymbolInfo:
    @patch('executor.mt5')
    def test_returns_symbol_info(self, mock_mt5):
        info = MagicMock()
        info.trade_tick_value = 1.0
        info.trade_tick_size = 0.01
        info.volume_min = 0.01
        info.volume_max = 100.0
        info.volume_step = 0.01
        mock_mt5.symbol_info.return_value = info
        result = get_symbol_info("XAUUSD")
        assert isinstance(result, SymbolInfo)
        assert result.trade_tick_value == 1.0
