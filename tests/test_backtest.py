import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import numpy as np
import pandas as pd
import pytest
from backtest import Trade, _simulate_trades, compute_stats, write_report
from risk_manager import SymbolInfo

SYMBOL_INFO = SymbolInfo(
    trade_tick_value=1.0,
    trade_tick_size=0.01,
    volume_min=0.01,
    volume_max=100.0,
    volume_step=0.01,
)
CFG = {'risk': {'risk_per_trade_pct': 1.0, 'rr_ratio': 2.0}}
ACCOUNT_BALANCE = 10000.0
WARMUP = 3


def _make_df(n, closes, highs=None, lows=None):
    if highs is None:
        highs = [c + 0.5 for c in closes]
    if lows is None:
        lows = [c - 0.5 for c in closes]
    times = pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC")
    return pd.DataFrame(
        {'open': closes, 'high': highs, 'low': lows, 'close': closes},
        index=times
    )


def test_buy_tp_exit():
    """BUY 信号触发，下一根 bar 的 high 触达 TP，交易以止盈出场。"""
    closes = [100.0] * 8
    highs  = [100.5] * 8
    lows   = [99.5]  * 8
    highs[4] = 105.0
    df = _make_df(8, closes, highs, lows)

    signals = ["HOLD"] * 8
    signals[3] = "BUY"
    trail_arr = np.zeros(8)
    trail_arr[3] = 98.0

    trades = _simulate_trades(df, signals, trail_arr, WARMUP, CFG, SYMBOL_INFO, ACCOUNT_BALANCE, "TEST")

    assert len(trades) == 1
    t = trades[0]
    assert t.direction == "BUY"
    assert t.exit_reason == "止盈"
    assert t.exit_price == pytest.approx(104.0)
    assert t.pnl_usd == pytest.approx(200.0)   # (4/0.01)*1.0*0.5=200
    assert t.exit_time == df.index[4]


def test_sell_sl_exit():
    """SELL 信号触发，下一根 bar 的 high 触达 SL，交易以止损出场。"""
    closes = [100.0] * 8
    highs  = [100.5] * 8
    lows   = [99.5]  * 8
    highs[5] = 103.0
    df = _make_df(8, closes, highs, lows)

    signals = ["HOLD"] * 8
    signals[3] = "SELL"
    trail_arr = np.zeros(8)
    trail_arr[3] = 102.0

    trades = _simulate_trades(df, signals, trail_arr, WARMUP, CFG, SYMBOL_INFO, ACCOUNT_BALANCE, "TEST")

    assert len(trades) == 1
    t = trades[0]
    assert t.direction == "SELL"
    assert t.exit_reason == "止损"
    assert t.exit_price == pytest.approx(102.0)
    assert t.pnl_usd == pytest.approx(-100.0)  # (−2/0.01)*1.0*0.5=−100


def test_no_reentry_while_in_position():
    """持仓期间出现信号不重复开仓；出场后当根 bar 也不立即重入。"""
    closes = [100.0] * 10
    highs  = [100.5] * 10
    lows   = [99.5]  * 10
    highs[8] = 105.0
    df = _make_df(10, closes, highs, lows)

    signals = ["HOLD"] * 10
    signals[3] = "BUY"
    signals[5] = "BUY"   # 持仓中，忽略
    signals[8] = "BUY"   # 出场当根 bar，just_exited 应阻止重入
    trail_arr = np.zeros(10)
    trail_arr[3] = 98.0
    trail_arr[5] = 98.0
    trail_arr[8] = 98.0

    trades = _simulate_trades(df, signals, trail_arr, WARMUP, CFG, SYMBOL_INFO, ACCOUNT_BALANCE, "TEST")

    assert len(trades) == 1   # 只有一笔交易


def test_open_position_at_end():
    """回测结束时仍有持仓，标记为 '持仓中'，pnl_usd 为 None。"""
    closes = [100.0] * 6
    df = _make_df(6, closes)   # highs=100.5，lows=99.5，不触 SL/TP

    signals = ["HOLD"] * 6
    signals[3] = "BUY"
    trail_arr = np.zeros(6)
    trail_arr[3] = 98.0   # SL=98.0，TP=104.0，均不被触达

    trades = _simulate_trades(df, signals, trail_arr, WARMUP, CFG, SYMBOL_INFO, ACCOUNT_BALANCE, "TEST")

    assert len(trades) == 1
    assert trades[0].exit_reason == "持仓中"
    assert trades[0].pnl_usd is None


def _make_trade(direction, exit_reason, pnl_usd, lots=0.5):
    """Helper: create a minimal Trade with given outcome."""
    t = pd.Timestamp("2025-01-01", tz="UTC")
    pnl_points = pnl_usd / 50.0  # arbitrary, for testing only
    return Trade(
        symbol="TEST", direction=direction,
        entry_time=t, entry_price=100.0, lots=lots,
        sl=98.0, tp=104.0, entry_bar=3,
        exit_time=t, exit_price=104.0 if pnl_usd > 0 else 98.0,
        exit_reason=exit_reason,
        pnl_points=pnl_points, pnl_usd=pnl_usd,
    )


def test_compute_stats_win_loss():
    """胜率、总盈利、总亏损、净盈亏计算正确。"""
    trades = [
        _make_trade("BUY",  "止盈", 200.0),
        _make_trade("SELL", "止损", -100.0),
        _make_trade("BUY",  "止盈", 150.0),
    ]
    stats = compute_stats(trades, account_balance=10000.0)

    assert stats["total"] == 3
    assert stats["wins"] == 2
    assert stats["losses"] == 1
    assert stats["win_rate"] == pytest.approx(200 / 3)   # 66.67%
    assert stats["total_profit"] == pytest.approx(350.0)
    assert stats["total_loss"] == pytest.approx(-100.0)
    assert stats["net_pnl"] == pytest.approx(250.0)


def test_compute_stats_open_trade_excluded():
    """'持仓中' 的交易不计入统计。"""
    trades = [
        _make_trade("BUY", "止盈", 200.0),
        Trade(symbol="TEST", direction="BUY",
              entry_time=pd.Timestamp("2025-01-02", tz="UTC"),
              entry_price=100.0, lots=0.5, sl=98.0, tp=104.0, entry_bar=5,
              exit_reason="持仓中"),
    ]
    stats = compute_stats(trades, account_balance=10000.0)

    assert stats["total"] == 1    # 只统计已出场的
    assert stats["open"] == 1


def test_compute_stats_max_consec_loss():
    """最大连续亏损次数计算正确。"""
    trades = [
        _make_trade("BUY", "止损", -100.0),
        _make_trade("BUY", "止损", -100.0),
        _make_trade("BUY", "止盈",  200.0),
        _make_trade("BUY", "止损", -100.0),
    ]
    stats = compute_stats(trades, account_balance=10000.0)
    assert stats["max_consec_loss"] == 2


def test_write_report_contains_required_fields(tmp_path):
    """报告文件包含所有用户要求的字段。"""
    t = pd.Timestamp("2025-01-01", tz="UTC")
    trades = [
        Trade(
            symbol="TEST", direction="BUY",
            entry_time=t, entry_price=100.0, lots=0.50,
            sl=98.0, tp=104.0, entry_bar=3,
            exit_time=t, exit_price=104.0, exit_reason="止盈",
            pnl_points=4.0, pnl_usd=200.0,
        ),
        Trade(
            symbol="TEST", direction="SELL",
            entry_time=t, entry_price=100.0, lots=0.50,
            sl=102.0, tp=96.0, entry_bar=5,
            exit_time=t, exit_price=102.0, exit_reason="止损",
            pnl_points=-2.0, pnl_usd=-100.0,
        ),
    ]
    stats = compute_stats(trades, account_balance=10000.0)
    output = str(tmp_path / "result.txt")

    write_report(
        symbol="TEST",
        trades=trades,
        stats=stats,
        account_balance=10000.0,
        start_time=t,
        end_time=t,
        output_path=output,
    )

    content = open(output, encoding="utf-8").read()
    assert "初始资金" in content
    assert "手数" in content
    assert "总盈利" in content
    assert "总亏损" in content
    assert "胜率" in content
    assert "止盈" in content
    assert "止损" in content
    assert "200" in content    # pnl_usd 正值出现
    assert "-100" in content   # pnl_usd 负值出现
    assert "10000" in content  # 初始资金
