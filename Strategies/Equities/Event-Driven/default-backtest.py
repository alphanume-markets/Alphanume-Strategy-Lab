# -*- coding: utf-8 -*-
"""
Created in 2026

@author: Alphanume

Corporate Default Event Backtest

This script pulls historical corporate default events from the Alphanume API,
measures forward stock performance after each event, and simulates a simple
equal-sized short strategy.

Core idea:
When a company formally defaults, misses debt obligations, or enters a severe
distress phase, equity often continues to reprice lower. This script tests
that event-driven short thesis across a historical sample.

Backtest logic:
- identify default events
- enter short position 1 trading day after the event
- hold for fixed forward windows
- track forward returns and cumulative capital

Data sources:
- Event data: Alphanume API
- Price data: Massive / Polygon

Note:
This is a baseline research backtest. It does NOT include:
- borrow costs / locate fees
- slippage / execution constraints
- minimum price filters
- overlap / portfolio-level position management
"""

import pandas as pd
import numpy as np
import requests
import pytz
import matplotlib.pyplot as plt

from datetime import datetime, timedelta
from pandas_market_calendars import get_calendar


# ---------------------------------------------------------
# Trading Calendar Setup
# ---------------------------------------------------------

# Use NYSE calendar so all event offsets are trading-day aware
calendar = get_calendar("NYSE")

# Full historical + forward trading-day index
all_trading_dates = calendar.schedule(
    start_date="2001-01-01",
    end_date=datetime.now(pytz.timezone("America/New_York")) + timedelta(days=300)
).index.strftime("%Y-%m-%d").values

# Current date in NY timezone
today = datetime.now(pytz.timezone("America/New_York")).strftime("%Y-%m-%d")


# ---------------------------------------------------------
# API Keys
# ---------------------------------------------------------

# Replace with your own API credentials
alphanume_api_key = "ALPHANUME_API_KEY"
massive_api_key = "MASSIVE_API_KEY"


# ---------------------------------------------------------
# Pull Corporate Default Event Data
# ---------------------------------------------------------

# Query the Alphanume corporate default endpoint
default_request = requests.get(
    f"https://api.alphanume.com/v1/corporate-default-events?api_key={alphanume_api_key}"
).json()

# Normalize JSON payload into tabular format
default_dataset = pd.json_normalize(default_request["data"])

# Sort events chronologically
events_data = default_dataset.copy().sort_values(by="event_date", ascending=True).reset_index(drop=True)


# ---------------------------------------------------------
# Event Loop: Compute Forward Returns
# ---------------------------------------------------------

# Store processed event rows here
event_info_list = []

# event = events_data.index[0]
for event in events_data.index:
    
    try:
        # Pull single event row
        event_info = events_data[events_data.index == event].copy()
        
        ticker = event_info["ticker"].iloc[0]
        event_date = event_info["event_date"].iloc[0]
        
        # Skip events that do not yet have enough forward history
        days_since_event = (pd.to_datetime(today) - pd.to_datetime(event_date)).days
        
        if days_since_event < 30:
            continue  # hasn't generated 30 days worth of data yet

        # Trade begins one trading day after the event
        next_day = np.sort(all_trading_dates[all_trading_dates > event_date])[0]

        # Pull roughly 3 months of forward price data
        forward_date = np.sort(all_trading_dates[all_trading_dates > event_date])[61]
        
        # Query daily aggregate price data from Massive / Polygon
        ticker_price_data = pd.json_normalize(
            requests.get(
                f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{next_day}/{forward_date}?adjusted=true&sort=asc&limit=50000&apiKey={massive_api_key}"
            ).json()["results"]
        ).set_index("t").sort_index()

        # Convert timestamp index to NY timezone
        ticker_price_data.index = pd.to_datetime(
            ticker_price_data.index, unit="ms", utc=True
        ).tz_convert("America/New_York")
        
        # Filter out malformed / incomplete price histories with large date gaps
        if ticker_price_data.index.to_series().diff().dt.days.max() >= 10:
            continue  # bad data

        # Compute cumulative return path from first post-event close
        ticker_price_data["returns"] = round(
            ((ticker_price_data["c"] - ticker_price_data["c"].iloc[0]) / ticker_price_data["c"].iloc[0]) * 100,
            2
        )
        
        # Fixed forward return horizons
        forward_1w_return = ticker_price_data["returns"].iloc[min(len(ticker_price_data) - 1, 5)]
        forward_1m_return = ticker_price_data["returns"].iloc[min(len(ticker_price_data) - 1, 20)]
        forward_3m_return = ticker_price_data["returns"].iloc[min(len(ticker_price_data) - 1, 60)]
        
        # Attach forward return metrics back to event row
        event_info["forward_1w_return"] = forward_1w_return
        event_info["forward_1m_return"] = forward_1m_return
        event_info["forward_3m_return"] = forward_3m_return
        
        # Store completed event record
        event_info_list.append(event_info)
        
    except Exception as error:  # price data not available
        continue


# Combine all processed events into one dataframe
complete_event_data = pd.concat(event_info_list)


# ---------------------------------------------------------
# Backtest Construction
# ---------------------------------------------------------

all_trades = complete_event_data.copy()

# Equal notional position size per name
size_per_name = 1000

# Starting portfolio capital
portfolio_start = 10000

# Choose which holding-period return to evaluate
choice_of_returns = "forward_1m_return"

# PnL for a short position:
# if forward return is negative, the short generates profit
all_trades["dollar_pnl"] = ((all_trades[choice_of_returns] / 100) * size_per_name) * -1  # short

# Build cumulative capital curve
all_trades["capital"] = portfolio_start + all_trades["dollar_pnl"].cumsum()


# ---------------------------------------------------------
# Plot Equity Curve
# ---------------------------------------------------------

dates = pd.to_datetime(all_trades["event_date"])
capital = all_trades["capital"]

fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=200)

# Main capital curve
ax.plot(dates, capital, linewidth=2.5)

# Plot title
ax.set_title(
    "Shorting New Default Events",
    fontsize=20,
    pad=20
)

# Axis labels
ax.set_xlabel("Date", fontsize=14)
ax.set_ylabel("Capital ($)", fontsize=14)

# Rotate x-axis labels for readability
plt.xticks(rotation=30)

# Clean up frame for presentation
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

# Light grid
ax.grid(alpha=0.15)

# Legend
ax.legend(["Gross Capital"], frameon=False, fontsize=12)

plt.tight_layout()
plt.show()
plt.close()


# ---------------------------------------------------------
# Simple Hit Rate
# ---------------------------------------------------------

# Fraction of trades where the stock was down over the chosen forward horizon
len(all_trades[all_trades[choice_of_returns] < 0]) / len(all_trades)