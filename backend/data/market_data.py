"""Fetch a U.S. stock snapshot. Install yfinance before running this module."""

import argparse
import json
import math
import re

import yfinance as yf


class MarketDataError(RuntimeError):
    """Yahoo Finance could not provide market data for the requested stock."""


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _change_pct(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return (current / previous - 1) * 100


def fetch_stock_data(symbol: str) -> dict:
    """Return JSON-ready prices and fundamentals for a U.S.-listed stock."""
    symbol = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z]{1,6}(?:[.-][A-Z]{1,3})?", symbol):
        raise ValueError("Expected a U.S. stock symbol such as NVDA or BRK.B.")
    symbol = symbol.replace(".", "-")

    ticker = yf.Ticker(symbol)
    try:
        info = ticker.get_info()
    except Exception as exc:
        raise MarketDataError(f"Could not fetch the stock profile for {symbol}.") from exc
    if not info:
        raise MarketDataError(f"Yahoo Finance returned no stock profile for {symbol}.")
    if info.get("market") != "us_market" or info.get("quoteType") != "EQUITY":
        raise ValueError(f"{symbol} is not a U.S.-listed stock in Yahoo Finance.")

    try:
        history = ticker.history(period="6mo", interval="1d", auto_adjust=False)
        statement = ticker.get_income_stmt(freq="quarterly")
    except Exception as exc:
        raise MarketDataError(f"Could not fetch market data for {symbol}.") from exc

    if "Close" not in history or (closes := history["Close"].dropna()).empty:
        raise MarketDataError(f"Yahoo Finance returned no daily prices for {symbol}.")

    latest_close = _number(closes.iloc[-1])
    previous_close = _number(closes.iloc[-2]) if len(closes) >= 2 else None
    sma_50 = _number(closes.tail(50).mean()) if len(closes) >= 50 else None

    quarters = []
    for period_end, values in statement.sort_index(axis=1, ascending=False).items():
        revenue = _number(values.get("TotalRevenue"))
        net_income = _number(values.get("NetIncome"))
        quarters.append({
            "period_end": period_end.date().isoformat(),
            "revenue": revenue,
            "net_income": net_income,
        })

    revenue_change_pct = None
    if len(quarters) >= 2:
        revenue_change_pct = _change_pct(quarters[0]["revenue"], quarters[1]["revenue"])

    return {
        "symbol": symbol,
        "name": info.get("longName") or info.get("shortName"),
        "exchange": info.get("fullExchangeName") or info.get("exchange"),
        "price_currency": info.get("currency"),
        "session_date": closes.index[-1].date().isoformat(),
        "latest_session_price": latest_close,
        "session_change_pct": _change_pct(latest_close, previous_close),
        "sma_50": sma_50,
        "market_cap": _number(info.get("marketCap")),
        "trailing_pe": _number(info.get("trailingPE")),
        "financial_currency": info.get("financialCurrency"),
        "quarterly_financials": quarters,
        "revenue_qoq_pct": revenue_change_pct,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch financial data for a U.S. stock.")
    parser.add_argument("symbol", help="Stock symbol, for example NVDA or BRK.B")
    args = parser.parse_args()
    try:
        snapshot = fetch_stock_data(args.symbol)
    except ValueError as exc:
        parser.error(str(exc))
    except MarketDataError as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(snapshot, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
