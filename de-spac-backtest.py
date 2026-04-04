# -*- coding: utf-8 -*-
"""
Created in 2026

@author: Alphanume

De-SPAC Event Backtest

This script evaluates the performance of stocks following De-SPAC events
(using Alphanume’s De-SPAC dataset).

Core idea:
Companies that go public via SPAC mergers often represent an adversely
selected pool (i.e., they couldn’t IPO the traditional way). After the
deal closes and constraints lift, supply enters the market and prices
tend to drift lower.

Backtest logic:
- Enter position 1 trading day after De-SPAC event
- Track forward returns over multiple horizons
- Simulate equal-sized short positions
- Build cumulative capital curve

Data sources:
- Event data: Alphanume API
- Price data: Massive / Polygon

Note:
This is a baseline research backtest. It does NOT include:
- borrow costs / locate fees
- slippage / execution constraints
- position overlap controls
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

# NYSE calendar ensures all offsets are trading-day aligned
calendar = get_calendar("NYSE")

# Full set of trading dates (historical + forward buffer)
all_trading_dates = calendar.schedule(
    start_date="2001-01-01",
    end_date=datetime.now(pytz.timezone("America/New_York")) + timedelta(days=300)
).index.strftime("%Y-%m-%d").values

# Current date in NY timezone
today = datetime.now(pytz.timezone("America/New_York")).strftime("%Y-%m-%d")


# ---------------------------------------------------------
# API Keys
# ---------------------------------------------------------

# Replace with your API keys
alphanume_api_key = "ALPHANUME_API_KEY"
massive_api_key = "MASSIVE_API_KEY"


# ---------------------------------------------------------
# Pull De-SPAC Event Data
# ---------------------------------------------------------

# Query Alphanume De-SPAC endpoint
de_spac_request = requests.get(
    f"https://api.alphanume.com/v1/de-spac-events?api_key={alphanume_api_key}"
).json()

# Normalize JSON response into dataframe
de_spac_dataset = pd.json_normalize(de_spac_request["data"])

# No filtering — use full dataset
events_data = de_spac_dataset.copy().reset_index(drop=True)


# ---------------------------------------------------------
# Event Loop: Compute Forward Returns
# ---------------------------------------------------------

# Store processed event rows
event_info_list = []

# event = events_data.index[0]
for event in events_data.index:
    
    try:
    
        # Extract single event row
        event_info = events_data[events_data.index == event].copy()
        
        ticker = event_info["ticker"].iloc[0]
        event_date = event_info["date"].iloc[0]

        # Entry = next trading day after event
        next_day = np.sort(all_trading_dates[all_trading_dates > event_date])[0]

        # Pull ~3 months of forward data (~90 trading days window)
        forward_date = np.sort(all_trading_dates[all_trading_dates > event_date])[90]
        
        # Request daily price data from Massive / Polygon
        ticker_price_data = pd.json_normalize(
            requests.get(
                f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{next_day}/{forward_date}?adjusted=true&sort=asc&limit=50000&apiKey={massive_api_key}"
            ).json()["results"]
        ).set_index("t").sort_index()

        # Convert timestamps to NY timezone
        ticker_price_data.index = pd.to_datetime(
            ticker_price_data.index, unit="ms", utc=True
        ).tz_convert("America/New_York")

        # Compute cumulative return path from entry point
        ticker_price_data["returns"] = round(
            ((ticker_price_data["c"] - ticker_price_data["c"].iloc[0]) / ticker_price_data["c"].iloc[0]) * 100,
            2
        )
        
        # Extract fixed forward horizons
        forward_1w_return = ticker_price_data["returns"].iloc[min(len(ticker_price_data) - 1, 5)]
        forward_1m_return = ticker_price_data["returns"].iloc[min(len(ticker_price_data) - 1, 20)]
        forward_3m_return = ticker_price_data["returns"].iloc[min(len(ticker_price_data) - 1, 60)]
        
        # Attach forward returns to event row
        event_info["forward_1w_return"] = forward_1w_return
        event_info["forward_1m_return"] = forward_1m_return
        event_info["forward_3m_return"] = forward_3m_return
        
        # Store processed event
        event_info_list.append(event_info)
        
    except Exception as error:
        # Handles missing price data / API issues
        print(error)
        continue
    

# Combine all processed events
complete_event_data = pd.concat(event_info_list)


# ---------------------------------------------------------
# Backtest Construction
# ---------------------------------------------------------

# Sort chronologically for proper capital curve
all_trades = complete_event_data.copy().sort_values(by="date", ascending=True)

# Fixed position size per trade
size_per_name = 1000

# Starting capital
portfolio_start = 10000

# Select which return horizon to evaluate
choice_of_returns = "forward_1m_return"

# Short PnL calculation:
# negative forward returns → profit
all_trades["dollar_pnl"] = ((all_trades[choice_of_returns] / 100) * size_per_name) * -1  # short

# Cumulative capital over time
all_trades["capital"] = portfolio_start + all_trades["dollar_pnl"].cumsum()


# ---------------------------------------------------------
# Plot Equity Curve
# ---------------------------------------------------------

dates = pd.to_datetime(all_trades["date"])
capital = all_trades["capital"]

fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=200)

# Plot capital curve
ax.plot(dates, capital, linewidth=2.5)

# Title
ax.set_title(
    "Shorting New De-SPAC Listings",
    fontsize=20,
    pad=20
)

# Axis labels
ax.set_xlabel("Date", fontsize=14)
ax.set_ylabel("Capital ($)", fontsize=14)

# Rotate x-axis labels
plt.xticks(rotation=30)

# Clean chart aesthetics
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

# Light grid
ax.grid(alpha=0.15)

# Legend
ax.legend(["Gross Capital"], frameon=False, fontsize=12)

plt.tight_layout()
plt.show()
plt.close()