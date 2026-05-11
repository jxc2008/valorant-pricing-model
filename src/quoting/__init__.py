"""Phase 4 quoting layer — Kalshi order plumbing + mode-aware quoters.

Public surface populated incrementally across plans 04-01 (auth +
order manager + market data), 04-02 (portfolio exposure registry),
04-03 (kill switches), through 04-08 (reconciliation + E2E).
"""
from src.quoting.fill_ledger import (
    HypotheticalFill,
    append_fill,
    maybe_record_mm_fill,
    simulate_touched,
)
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
from src.quoting.mm_quoter import compute_half_spread, quote_mm_between_round
from src.quoting.mode_selector import TradingMode, trading_mode
from src.quoting.order_manager import KalshiOrderManager, Quote, StrategyId
from src.quoting.portfolio import PortfolioState

__all__ = [
    "HypotheticalFill",
    "KalshiOrderManager",
    "KalshiWsMarketData",
    "KillSwitchAggregator",
    "MarketDataSource",
    "MarketQuote",
    "PortfolioState",
    "Quote",
    "StrategyId",
    "SyntheticMarketData",
    "TradingMode",
    "append_fill",
    "compute_half_spread",
    "kill_switch_api_error",
    "kill_switch_brier",
    "kill_switch_deviation",
    "kill_switch_market_invalid",
    "kill_switch_staleness",
    "load_private_key",
    "make_quote",
    "maybe_record_mm_fill",
    "quote_mm_between_round",
    "sign_request",
    "simulate_touched",
    "trading_mode",
]
