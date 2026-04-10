import logging

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

from risk_manager import SymbolInfo

logger = logging.getLogger(__name__)

MAGIC_NUMBER = 20260101  # Identifies orders placed by this system


def get_symbol_info(symbol: str) -> SymbolInfo:
    """Get symbol contract specifications from MT5."""
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"Cannot get symbol info for {symbol}")
    return SymbolInfo(
        trade_tick_value=info.trade_tick_value,
        trade_tick_size=info.trade_tick_size,
        volume_min=info.volume_min,
        volume_max=info.volume_max,
        volume_step=info.volume_step,
    )


def has_open_position(symbol: str) -> bool:
    """Check if symbol has any open positions (prevents duplicate orders)."""
    positions = mt5.positions_get(symbol=symbol)
    return bool(positions)


def place_order(
    symbol: str,
    signal: str,
    lots: float,
    sl: float,
    tp: float,
) -> object | None:
    """
    Send a market order to MT5.

    Returns:
        MT5 order_send result, or None if position already exists.
    """
    if has_open_position(symbol):
        logger.info(f"[{symbol}] Already has open position, skipping order.")
        return None

    if signal == "BUY":
        order_type = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).ask
    else:
        order_type = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(symbol).bid

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       symbol,
        "volume":       lots,
        "type":         order_type,
        "price":        price,
        "sl":           sl,
        "tp":           tp,
        "deviation":    20,
        "magic":        MAGIC_NUMBER,
        "comment":      "hma_blackflag_auto",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != 10009:
        logger.error(
            f"[{symbol}] Order failed: retcode={result.retcode}, comment={result.comment}"
        )
    else:
        logger.info(f"[{symbol}] {signal} order placed: {lots} lots, SL={sl}, TP={tp}")
    return result
