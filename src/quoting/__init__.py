"""Phase 4 quoting layer — Kalshi order plumbing + mode-aware quoters.

Public surface populated incrementally across plans 04-01 (auth +
order manager + market data), 04-02 (portfolio exposure registry),
04-03 (kill switches), through 04-08 (reconciliation + E2E).
"""
from src.quoting.kalshi_auth import load_private_key, sign_request
from src.quoting.kill_switches import (
    KillSwitchAggregator,
    kill_switch_api_error,
    kill_switch_brier,
    kill_switch_deviation,
    kill_switch_market_invalid,
    kill_switch_staleness,
)
from src.quoting.market_data import (
    KalshiWsMarketData,
    MarketDataSource,
    MarketQuote,
    SyntheticMarketData,
    make_quote,
)
from src.quoting.order_manager import KalshiOrderManager, Quote, StrategyId
from src.quoting.portfolio import PortfolioState

__all__ = [
    "KalshiOrderManager",
    "KalshiWsMarketData",
    "KillSwitchAggregator",
    "MarketDataSource",
    "MarketQuote",
    "PortfolioState",
    "Quote",
    "StrategyId",
    "SyntheticMarketData",
    "kill_switch_api_error",
    "kill_switch_brier",
    "kill_switch_deviation",
    "kill_switch_market_invalid",
    "kill_switch_staleness",
    "load_private_key",
    "make_quote",
    "sign_request",
]
