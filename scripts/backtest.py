"""
Backtest script: simulate HMA + Blackflag strategy on 6 months MT5 historical data.

Usage (requires Windows + MT5):
  python scripts/backtest.py
Output: backtest_results.txt in project root.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import yaml

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

from data_feed import get_ohlcv
from indicators.hma import hma
from indicators.blackflag import blackflag
from signal_engine import get_signal
from risk_manager import SymbolInfo, calculate_trade_params
from executor import get_symbol_info


# 最近6个月 15min K线根数（约17280根）
SIX_MONTHS_BARS = 17_280


@dataclass
class Trade:
    symbol: str
    direction: str          # "BUY" or "SELL"
    entry_time: Any
    entry_price: float
    lots: float
    sl: float
    tp: float
    entry_bar: int          # internal: bar index in df
    exit_time: Any = None
    exit_price: float = None
    exit_reason: str = None  # "止盈" | "止损" | "持仓中"
    pnl_points: float = None
    pnl_usd: float = None


def _simulate_trades(
    df: pd.DataFrame,
    signals: list,
    trail_arr: np.ndarray,
    warmup: int,
    cfg: dict,
    symbol_info: SymbolInfo,
    account_balance: float,
    symbol: str,
) -> list[Trade]:
    """
    Core simulation loop. Processes bars from warmup onward.
    Does NOT call MT5 — fully testable with synthetic data.

    Exit priority (when both SL and TP hit in same bar): SL first (pessimistic).
    No re-entry on the bar an existing trade exits.
    """
    risk_cfg = cfg['risk']
    trades = []
    current_trade = None  # type: Trade | None

    for i in range(warmup, len(df)):
        bar = df.iloc[i]
        just_exited = False

        # ── 1. Check exit for current open trade ──────────────────────────
        if current_trade is not None and i > current_trade.entry_bar:
            if current_trade.direction == "BUY":
                if bar['low'] <= current_trade.sl:
                    _close_trade(current_trade, df.index[i], current_trade.sl, "止损", symbol_info)
                    trades.append(current_trade)
                    current_trade = None
                    just_exited = True
                elif bar['high'] >= current_trade.tp:
                    _close_trade(current_trade, df.index[i], current_trade.tp, "止盈", symbol_info)
                    trades.append(current_trade)
                    current_trade = None
                    just_exited = True
            else:  # SELL
                if bar['high'] >= current_trade.sl:
                    _close_trade(current_trade, df.index[i], current_trade.sl, "止损", symbol_info)
                    trades.append(current_trade)
                    current_trade = None
                    just_exited = True
                elif bar['low'] <= current_trade.tp:
                    _close_trade(current_trade, df.index[i], current_trade.tp, "止盈", symbol_info)
                    trades.append(current_trade)
                    current_trade = None
                    just_exited = True

        # ── 2. Check entry signal (skip bar where we just exited) ─────────
        if current_trade is None and not just_exited and signals[i] != "HOLD":
            entry_price = float(df['close'].iloc[i])
            trail_val = float(trail_arr[i])
            try:
                lots, sl, tp = calculate_trade_params(
                    signal=signals[i],
                    entry_price=entry_price,
                    trail=trail_val,
                    account_balance=account_balance,
                    risk_pct=risk_cfg['risk_per_trade_pct'],
                    rr_ratio=risk_cfg['rr_ratio'],
                    symbol_info=symbol_info,
                )
            except ValueError:
                continue  # invalid SL (trail too close to price), skip

            current_trade = Trade(
                symbol=symbol,
                direction=signals[i],
                entry_time=df.index[i],
                entry_price=entry_price,
                lots=lots,
                sl=sl,
                tp=tp,
                entry_bar=i,
            )

    # ── 3. Handle position still open at end of data ──────────────────────
    if current_trade is not None:
        current_trade.exit_reason = "持仓中"
        trades.append(current_trade)

    return trades


def _close_trade(trade: Trade, exit_time, exit_price: float, reason: str, symbol_info: SymbolInfo) -> None:
    """Mutate trade in-place with exit info and pnl calculation."""
    trade.exit_time = exit_time
    trade.exit_price = exit_price
    trade.exit_reason = reason

    if trade.direction == "BUY":
        trade.pnl_points = exit_price - trade.entry_price
    else:
        trade.pnl_points = trade.entry_price - exit_price

    trade.pnl_usd = (trade.pnl_points / symbol_info.trade_tick_size) * symbol_info.trade_tick_value * trade.lots


def compute_stats(trades: list[Trade], account_balance: float) -> dict:
    """
    Compute summary statistics from a list of Trade objects.
    '持仓中' trades are excluded from all metrics except the 'open' count.
    Trades with pnl_usd == 0.0 are classified as losses (break-even = loss).
    """
    completed = [t for t in trades if t.exit_reason in ("止盈", "止损")]
    open_trades = [t for t in trades if t.exit_reason == "持仓中"]

    wins   = [t for t in completed if t.pnl_usd is not None and t.pnl_usd > 0]
    losses = [t for t in completed if t.pnl_usd is not None and t.pnl_usd <= 0]

    total_profit = float(sum(t.pnl_usd for t in wins))
    total_loss   = float(sum(t.pnl_usd for t in losses))
    net_pnl      = total_profit + total_loss

    n = len(completed)
    win_rate   = len(wins) / n * 100 if n else 0.0
    avg_profit = total_profit / len(wins)   if wins   else 0.0
    avg_loss   = total_loss   / len(losses) if losses else 0.0
    avg_lots   = sum(t.lots for t in completed) / n if n else 0.0

    # Max consecutive losses
    max_consec_loss = consec = 0
    for t in completed:
        if t.pnl_usd is not None and t.pnl_usd <= 0:
            consec += 1
            max_consec_loss = max(max_consec_loss, consec)
        else:
            consec = 0

    # Max drawdown (peak-to-trough of cumulative pnl)
    cumulative = peak = max_drawdown = 0.0
    for t in completed:
        if t.pnl_usd is not None:
            cumulative += t.pnl_usd
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_drawdown:
            max_drawdown = dd
    max_drawdown_pct = (max_drawdown / account_balance * 100) if account_balance > 0 else 0.0

    return {
        "total":            n,
        "open":             len(open_trades),
        "wins":             len(wins),
        "losses":           len(losses),
        "win_rate":         win_rate,
        "total_profit":     total_profit,
        "total_loss":       total_loss,
        "net_pnl":          net_pnl,
        "avg_profit":       avg_profit,
        "avg_loss":         avg_loss,
        "max_consec_loss":  max_consec_loss,
        "max_drawdown":     max_drawdown,
        "max_drawdown_pct": max_drawdown_pct,
        "avg_lots":         avg_lots,
    }


def write_report(
    symbol: str,
    trades: list[Trade],
    stats: dict,
    account_balance: float,
    start_time: Any,
    end_time: Any,
    output_path: str,
) -> None:
    """
    Append a backtest report for one symbol to output_path (UTF-8, append mode).
    Call once per symbol; main() removes the old file before the loop.
    """
    lines = []
    sep = "=" * 72

    start_str = start_time.strftime('%Y-%m-%d %H:%M') if hasattr(start_time, 'strftime') else str(start_time)
    end_str   = end_time.strftime('%Y-%m-%d %H:%M')   if hasattr(end_time, 'strftime')   else str(end_time)

    lines.append(sep)
    lines.append(f"回测报告 - {symbol}")
    lines.append(f"回测区间：{start_str} ~ {end_str}")
    lines.append(f"初始资金：${account_balance:,.2f}")
    lines.append(sep)
    lines.append("")

    # ── 交易明细 ──────────────────────────────────────────────────────────
    lines.append("【交易明细】")
    header = (
        f"{'#':<4} {'方向':<6} {'入场时间':<20} {'入场价':>10} {'手数':>6} "
        f"{'止损价':>10} {'止盈价':>10} {'出场时间':<20} {'出场价':>10} "
        f"{'出场原因':<8} {'盈亏(点数)':>12} {'盈亏(USD)':>12}"
    )
    lines.append(header)
    lines.append("-" * 130)

    for idx, t in enumerate(trades, 1):
        et  = t.entry_time.strftime('%Y-%m-%d %H:%M') if hasattr(t.entry_time, 'strftime') else str(t.entry_time)
        xt  = t.exit_time.strftime('%Y-%m-%d %H:%M')  if hasattr(t.exit_time, 'strftime')  else "—"
        xp  = f"{t.exit_price:>10.2f}" if t.exit_price  is not None else f"{'—':>10}"
        pp  = f"{t.pnl_points:>+12.2f}" if t.pnl_points is not None else f"{'—':>12}"
        pu  = f"{t.pnl_usd:>+12.2f}"   if t.pnl_usd    is not None else f"{'—':>12}"
        reason = t.exit_reason or "—"
        lines.append(
            f"{idx:<4} {t.direction:<6} {et:<20} {t.entry_price:>10.2f} {t.lots:>6.2f} "
            f"{t.sl:>10.2f} {t.tp:>10.2f} {xt:<20} {xp} "
            f"{reason:<8} {pp} {pu}"
        )

    lines.append("")

    # ── 汇总统计 ──────────────────────────────────────────────────────────
    lines.append("【汇总统计】")
    lines.append(f"总交易次数：  {stats['total']}")
    lines.append(f"盈利次数：    {stats['wins']}    胜率：{stats['win_rate']:.1f}%")
    lines.append(f"亏损次数：    {stats['losses']}")
    if stats['open']:
        lines.append(f"未出场次数：  {stats['open']}")
    lines.append("")
    lines.append(f"每笔平均手数：{stats['avg_lots']:.2f}")
    lines.append("")
    lines.append(f"总盈利：   +${stats['total_profit']:,.2f}")
    lines.append(f"总亏损：   -${abs(stats['total_loss']):,.2f}")
    lines.append(f"净盈亏：   {stats['net_pnl']:+,.2f} USD")
    lines.append("")
    lines.append(f"平均单笔盈利：${stats['avg_profit']:,.2f}")
    lines.append(f"平均单笔亏损：-${abs(stats['avg_loss']):,.2f}")
    lines.append("")
    lines.append(f"最大连续亏损次数：{stats['max_consec_loss']}")
    lines.append(f"最大回撤：       -${stats['max_drawdown']:,.2f} ({stats['max_drawdown_pct']:.1f}%)")
    lines.append("")
    lines.append(sep)
    lines.append("")
    lines.append("")

    with open(output_path, 'a', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def backtest_symbol(
    symbol: str,
    df: pd.DataFrame,
    cfg: dict,
    symbol_info: SymbolInfo,
    account_balance: float,
) -> list[Trade]:
    """
    Compute all indicators + signals on df, then simulate trades.
    df must include warmup bars (warmup = cfg['scheduler']['warmup_bars']).
    """
    hma_cfg  = cfg['indicators']['hma']
    bf_cfg   = cfg['indicators']['blackflag']
    warmup   = cfg['scheduler']['warmup_bars']
    source_col = hma_cfg.get('source', 'close')

    source = df[source_col].values
    high   = df['high'].values
    low    = df['low'].values
    close  = df['close'].values

    # Compute indicators on full array (causal, no look-ahead)
    hma1_arr = hma(source, hma_cfg['length1'])
    hma2_arr = hma(source, hma_cfg['length2'])
    hma3_arr = hma(source, hma_cfg['length3'])
    trend_arr, trail_arr = blackflag(
        high, low, close,
        atr_period=bf_cfg['atr_period'],
        atr_factor=bf_cfg['atr_factor'],
        trail_type=bf_cfg.get('trail_type', 'modified'),
    )

    # Precompute signals for each bar.
    # get_signal() only reads [-1] and [-2], so we pass a 2-element window
    # instead of growing slices, avoiding repeated view object creation.
    signals = ["HOLD"] * len(df)
    for i in range(1, len(df)):
        h1 = hma1_arr[i - 1 : i + 1]
        h2 = hma2_arr[i - 1 : i + 1]
        h3 = hma3_arr[i - 1 : i + 1]
        tr = trend_arr[i - 1 : i + 1]
        signals[i] = get_signal(h1, h2, h3, tr)

    return _simulate_trades(df, signals, trail_arr, warmup, cfg, symbol_info, account_balance, symbol)


def main() -> None:
    if mt5 is None:
        print("ERROR: MetaTrader5 is not installed. Run on Windows.")
        sys.exit(1)

    # ── Load config ───────────────────────────────────────────────────────
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    warmup = cfg['scheduler']['warmup_bars']
    total_bars = SIX_MONTHS_BARS + warmup + 1  # +1: drop the forming candle

    # ── Connect to MT5 ────────────────────────────────────────────────────
    if not mt5.initialize():
        print(f"MT5 initialize() failed: {mt5.last_error()}")
        sys.exit(1)
    if not mt5.login(
        login=cfg['mt5']['login'],
        password=cfg['mt5']['password'],
        server=cfg['mt5']['server'],
    ):
        print(f"MT5 login failed: {mt5.last_error()}")
        mt5.shutdown()
        sys.exit(1)

    account_info = mt5.account_info()
    if account_info is None:
        print("Cannot get account info")
        mt5.shutdown()
        sys.exit(1)
    account_balance = account_info.balance

    # ── Output file ───────────────────────────────────────────────────────
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "backtest_results.txt",
    )
    if os.path.exists(output_path):
        os.remove(output_path)

    # ── Run backtest per symbol ───────────────────────────────────────────
    try:
        for symbol in cfg['symbols']:
            print(f"[{symbol}] Fetching {total_bars} bars...")
            df = get_ohlcv(symbol, cfg['timeframe'], bars=total_bars)
            df = df.iloc[:-1]  # drop forming candle (consistent with live scheduler)

            symbol_info = get_symbol_info(symbol)

            print(f"[{symbol}] Simulating trades...")
            trades = backtest_symbol(symbol, df, cfg, symbol_info, account_balance)

            stats = compute_stats(trades, account_balance)
            start_time = df.index[warmup]
            end_time   = df.index[-1]

            write_report(symbol, trades, stats, account_balance, start_time, end_time, output_path)
            print(f"[{symbol}] Done: {stats['total']} trades, net PnL={stats['net_pnl']:+.2f} USD")
    finally:
        mt5.shutdown()

    print(f"\nBacktest complete. Results saved to: {output_path}")


if __name__ == "__main__":
    main()
