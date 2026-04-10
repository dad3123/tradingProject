from dataclasses import dataclass


@dataclass
class SymbolInfo:
    trade_tick_value: float   # Currency value per tick (in account currency)
    trade_tick_size: float    # Minimum price increment
    volume_min: float         # Minimum lot size
    volume_max: float         # Maximum lot size
    volume_step: float        # Lot size step

    def __post_init__(self):
        for field_name, value in [
            ("trade_tick_value", self.trade_tick_value),
            ("trade_tick_size", self.trade_tick_size),
            ("volume_min", self.volume_min),
            ("volume_max", self.volume_max),
            ("volume_step", self.volume_step),
        ]:
            if value <= 0:
                raise ValueError(f"SymbolInfo.{field_name} must be > 0, got {value}")


def calculate_trade_params(
    signal: str,
    entry_price: float,
    trail: float,
    account_balance: float,
    risk_pct: float,
    rr_ratio: float,
    symbol_info: SymbolInfo,
) -> tuple[float, float, float]:
    """
    Calculate lot size, stop-loss price, and take-profit price.

    Args:
        signal:          "BUY" or "SELL"
        entry_price:     Expected entry price (current market price)
        trail:           Blackflag trail line price (used as stop-loss)
        account_balance: Account equity (account currency)
        risk_pct:        Risk per trade as % of balance (e.g. 1.0 = 1%)
        rr_ratio:        TP/SL ratio (e.g. 2.0 = 2:1)
        symbol_info:     Symbol contract specifications

    Returns:
        (lots, sl_price, tp_price)
    """
    sl_distance = abs(entry_price - trail)
    if sl_distance < symbol_info.trade_tick_size:
        raise ValueError(
            f"SL distance ({sl_distance}) is smaller than tick size ({symbol_info.trade_tick_size}); "
            "cannot size position."
        )

    if signal == "BUY" and trail >= entry_price:
        raise ValueError(
            f"BUY trail ({trail}) must be below entry ({entry_price}); "
            "invalid SL direction"
        )
    if signal == "SELL" and trail <= entry_price:
        raise ValueError(
            f"SELL trail ({trail}) must be above entry ({entry_price}); "
            "invalid SL direction"
        )
    risk_amount = account_balance * (risk_pct / 100.0)

    # lots × (sl_distance / tick_size) × tick_value = risk_amount
    sl_in_ticks = sl_distance / symbol_info.trade_tick_size
    raw_lots = risk_amount / (sl_in_ticks * symbol_info.trade_tick_value)

    # Align to volume step and clamp to [min, max]
    step = symbol_info.volume_step
    lots = round(round(raw_lots / step) * step, 8)
    lots = max(lots, symbol_info.volume_min)
    lots = min(lots, symbol_info.volume_max)

    if signal == "BUY":
        sl = trail                               # SL below entry
        tp = entry_price + sl_distance * rr_ratio
    else:
        sl = trail                               # SL above entry
        tp = entry_price - sl_distance * rr_ratio

    return lots, round(sl, 8), round(tp, 8)
