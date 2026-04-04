# -*- coding: utf-8 -*-
"""
Created in 2026

@author: Alphanume

Dilution Event Backtest

This script pulls historical dilution events from the Alphanume API,
filters for confirmed dilutive events, and measures forward stock
performance after each event.

The backtest then simulates a simple equal-sized short strategy:
- short each dilutive name
- hold for a fixed forward window
- track cumulative capital over time

Price data is sourced from Massive / Polygon.
Event data is sourced from Alphanume.

This is meant to be a clean research baseline, not a full production
simulation with borrow costs, execution slippage, or position overlap controls.
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
# Pull Dilution Event Data
# ---------------------------------------------------------

# Query the Alphanume dilution endpoint
dilution_request = requests.get(
    f"https://api.alphanume.com/v1/dilution?api_key={alphanume_api_key}"
).json()

# Normalize JSON payload into tabular format
dilution_dataset = pd.json_normalize(dilution_request["data"])

# Keep only confirmed dilutive events and sort chronologically
events_data = (
    dilution_dataset[dilution_dataset["dilutive"] == 1]
    .copy()
    .sort_values(by="date", ascending=True)
    .reset_index(drop=True)
)


# ---------------------------------------------------------
# Event Loop: Compute Forward Returns
# ---------------------------------------------------------

# Store processed event rows here
event_info_list = []

# event = events_data.index[50]
for event in events_data.index:
    
    try:
        
        # Pull the single event row
        event_info = events_data[events_data.index == event].copy()
        
        ticker = event_info["ticker"].iloc[0]
        event_date = event_info["date"].iloc[0]
        
        # Skip very recent events that do not yet have enough forward data
        days_since_event = (pd.to_datetime(today) - pd.to_datetime(event_date)).days
        
        if days_since_event < 30:
            continue  # hasn't generated 30 days worth of data yet

        # Trade starts one trading day after the event
        next_day = np.sort(all_trading_dates[all_trading_dates > event_date])[0]

        # Pull ~3 months of forward daily price data
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
        
        # Drop cases where price history has suspicious large date gaps
        if ticker_price_data.index.to_series().diff().dt.days.max() >= 10:
            continue  # bad data

        # Compute forward return path from first available post-event close
        ticker_price_data["returns"] = round(
            ((ticker_price_data["c"] - ticker_price_data["c"].iloc[0]) / ticker_price_data["c"].iloc[0]) * 100,
            2
        )
        
        # Grab fixed-horizon forward returns
        forward_1w_return = ticker_price_data["returns"].iloc[min(len(ticker_price_data) - 1, 5)]
        forward_1m_return = ticker_price_data["returns"].iloc[min(len(ticker_price_data) - 1, 20)]
        forward_3m_return = ticker_price_data["returns"].iloc[min(len(ticker_price_data) - 1, 60)]
        
        # Attach forward returns back onto the event row
        event_info["forward_1w_return"] = forward_1w_return
        event_info["forward_1m_return"] = forward_1m_return
        event_info["forward_3m_return"] = forward_3m_return
        
        # Save completed event record
        event_info_list.append(event_info)
        
    except Exception as error:  # price data not available or malformed response
        print(error)
        continue
    

# Combine all processed events into one dataframe
complete_event_data = pd.concat(event_info_list)


# ---------------------------------------------------------
# Backtest Construction
# ---------------------------------------------------------

all_trades = complete_event_data.copy()

# Equal notional position sizing per trade
size_per_name = 1000

# Starting portfolio capital
portfolio_start = 10000

# Select which holding-period return to evaluate
choice_of_returns = "forward_1m_return"

# PnL for a short position:
# if forward return is negative, short makes money
all_trades["dollar_pnl"] = ((all_trades[choice_of_returns] / 100) * size_per_name) * -1  # short

# Cumulative capital curve
all_trades["capital"] = portfolio_start + all_trades["dollar_pnl"].cumsum()


# ---------------------------------------------------------
# Plot Equity Curve
# ---------------------------------------------------------

dates = pd.to_datetime(all_trades["date"])
capital = all_trades["capital"]

fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=200)

# Main capital curve
ax.plot(dates, capital, linewidth=2.5)

# Plot title
ax.set_title(
    "Shorting Newly Diluted Stocks",
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

# Light grid to improve readability
ax.grid(alpha=0.15)

# Legend
ax.legend(["Gross Capital"], frameon=False, fontsize=12)

plt.tight_layout()
plt.show()
plt.close()


# ---------------------------------------------------------
# Simple Hit Rate
# ---------------------------------------------------------

# Fraction of events where the stock was down over the chosen forward horizon
len(all_trades[all_trades[choice_of_returns] < 0]) / len(all_trades)