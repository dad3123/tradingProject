import logging
import os
import sys
import yaml

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("trading.log"),
    ],
)
logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def connect_mt5(cfg: dict) -> None:
    if mt5 is None:
        raise RuntimeError("MetaTrader5 is not installed")
    if not mt5.initialize():
        raise RuntimeError("MT5 initialize() failed")
    if not mt5.login(
        login=cfg['mt5']['login'],
        password=cfg['mt5']['password'],
        server=cfg['mt5']['server'],
    ):
        raise RuntimeError(f"MT5 login failed: {mt5.last_error()}")
    info = mt5.account_info()
    logger.info(f"Connected to MT5: account={info.login}, balance={info.balance} {info.currency}")


def _run_backtest() -> None:
    scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import backtest as backtest_mod
    backtest_mod.main()


def main():
    cfg = load_config()
    mode = cfg.get('mode', 'live')
    if mode not in ('live', 'backtest'):
        logger.warning(f"Unknown mode '{mode}', defaulting to 'live'")
        mode = 'live'
    logger.info(f"Mode: {mode}")

    if mode == 'backtest':
        _run_backtest()
        return

    import scheduler
    connect_mt5(cfg)

    try:
        scheduler.start(cfg)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        mt5.shutdown()
        logger.info("MT5 disconnected.")


if __name__ == "__main__":
    main()
