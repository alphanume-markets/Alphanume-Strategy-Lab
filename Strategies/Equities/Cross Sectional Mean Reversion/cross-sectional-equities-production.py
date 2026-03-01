# -*- coding: utf-8 -*-
"""
@author: Alphanume Strategy Lab
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
import pytz

from datetime import datetime, timedelta
from pandas_market_calendars import get_calendar

def market_cap_mapping(market_cap):
    """
    Map a raw market cap value into a discrete 'market cap class' bucket.
    This is used later to filter / segment the universe point-in-time.

    Output classes:
        5 = Mega cap   (>= $200B)
        4 = Large cap  ($10B - $200B)
        3 = Mid cap    ($2B - $10B)
        2 = Small cap  ($250M - $2B)
        1 = Micro cap  ($50M - $250M)
        0 = Nano cap   (< $50M)
    """

    if market_cap >= 200e+9: # above $200b (mega cap)
        return 5
    elif (market_cap >= 10e+9) and (market_cap < 200e+9): #$10b-$200b (large cap)
        return 4
    elif (market_cap >= 2e+9) and (market_cap < 10e+9): #$10b-$200b (mid cap)
        return 3
    elif (market_cap >= 0.25e+9) and (market_cap < 2e+9): # $0.25B-$2b (small cap)
        return 2
    elif (market_cap >= 0.05e+9) and (market_cap < 0.25e+9): # $0.05B-$0.25b (micro cap)
        return 1
    elif (market_cap < 0.05e+9): # < $50m (nano cap)
        return 0
    else:
        return np.nan

# =============================================================================
# Core-Requisites
# =============================================================================

# API keys for:
# 1) Alphanume (market cap dataset)
# 2) Polygon.io (Massive) (daily OHLCV data per ticker)
alphanume_api_key = "YOUR_ALPHANUME_API_KEY"
polygon_api_key = "YOUR_POLYGON_API_KEY"

# NYSE calendar is used for:
# - determining valid trading sessions
# - computing "lookback dates" and "exit dates" using session offsets
calendar = get_calendar("NYSE")

# all_trading_dates: long history of sessions (used for consistent date arithmetic)
# trading_dates: short recent window (last ~7 calendar days worth of sessions through today)
all_trading_dates = calendar.schedule(start_date="2001-01-01", end_date=datetime.now(pytz.timezone("America/New_York")) + timedelta(days=30)).index.strftime("%Y-%m-%d").values

trading_dates = calendar.schedule(start_date=(datetime.today() - timedelta(days=7)), end_date=(datetime.today())).index.strftime("%Y-%m-%d").values

# Query market cap starting one session before our "current window" begins
# so the latest snapshot is point-in-time relative to the trading dates we evaluate.
query_lookback_date = np.sort(all_trading_dates[all_trading_dates < trading_dates[0]])[-1]

# =============================================================================
# Point-in-Time Market Cap Dataset
# =============================================================================

# Pull Alphanume historical market cap via cursor pagination.
# We then keep the most recent snapshot per ticker (point-in-time “latest known”).
market_cap_data_list = []
market_cap_base_url = f"https://api.alphanume.com/v1/historical-market-cap?date_gte={query_lookback_date}&api_key={alphanume_api_key}"
market_cap_request_url = market_cap_base_url

# Cursor starts empty; API returns next_cursor while has_more == True
next_cursor = []

while next_cursor is not None:

    try:

        # Request a single “page” of market cap records
        market_cap_request = requests.get(market_cap_request_url).json()

        market_cap_data = market_cap_request["data"]

        # If empty page is returned, stop
        if len(market_cap_data) < 1:
            break

        # Accumulate this page
        market_cap_data_list.append(market_cap_data)

        # Stop if there is no next page
        if market_cap_request["has_more"] == False:
            break

        # Retrieve cursor and construct next request URL
        next_cursor = market_cap_request["next_cursor"]

        market_cap_request_url = (
            market_cap_base_url
            + "&"
            + f"cursor_date={next_cursor['date']}"
            + "&"
            + f"cursor_ticker={next_cursor['ticker']}"
        )

    except Exception as error:
        # If request fails (network / response issues), print and exit
        print(market_cap_request)
        break

# Flatten list-of-pages into a DataFrame, sort, then keep latest row per ticker.
# drop_duplicates(... keep="last") means we keep the most recent market cap snapshot for each ticker.
market_cap_dataset = (
    pd.DataFrame([row for page in market_cap_data_list for row in page])
      .sort_values(by=["date", "ticker"], ascending=True)
      .drop_duplicates(subset=["ticker"], keep="last")
)

# Discretize market cap to a class bucket (used to select the target universe)
market_cap_dataset["market_cap_class"] = market_cap_dataset["market_cap"].apply(market_cap_mapping)

# =============================================================================
# Grouped Return Calcs.
# =============================================================================

# Define the universe: here we focus on nano caps (market_cap_class == 0)
desired_universe = market_cap_dataset[market_cap_dataset["market_cap_class"] == 0].copy()
tickers = desired_universe["ticker"].drop_duplicates().values

# "Today" is the most recent session in trading_dates
trading_date = trading_dates[-1] # today

# Look back 20 sessions (~1 trading month) for computing rolling features
trading_lookback_date = np.sort(all_trading_dates[all_trading_dates < trading_date])[-20] # 1 calendar month lookback window

# Keep 1 session active (same headers, etc.)
# In practice, requests.Session can reduce overhead for many sequential requests.
connection_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=500)
connection_session.mount('https://', adapter)

data_list = []
times = []

# For each ticker in the chosen universe:
# 1) Pull last ~20 sessions of daily bars (Polygon)
# 2) Compute a 10-day rolling average close
# 3) Compute distance-from-average on the most recent day only
# 4) Store the most recent row for cross-sectional ranking
for ticker in tickers:

    try:

        start_time = datetime.now()

        # Pull daily OHLCV bars for the ticker across the lookback window
        underlying_data = (
            pd.json_normalize(
                requests.get(
                    f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{trading_lookback_date}/{trading_date}?adjusted=true&sort=asc&limit=50000&apiKey={polygon_api_key}"
                ).json()["results"]
            )
            .set_index("t")
        )

        # Convert millisecond timestamps to NY time
        underlying_data.index = pd.to_datetime(underlying_data.index, unit="ms", utc=True).tz_convert("America/New_York")

        # Add explicit date and ticker fields for convenience
        underlying_data["date"] = underlying_data.index.strftime("%Y-%m-%d")
        underlying_data["ticker"] = ticker

        # Rolling 10-day average close (used as a mean-reversion anchor)
        underlying_data["avg_px"] = underlying_data["c"].rolling(window=10).mean()

        # Percent distance from the rolling average
        # Negative => below average; positive => above average
        underlying_data["dist_from_avg"] = round(((underlying_data["c"] - underlying_data["avg_px"]) / underlying_data["avg_px"]) * 100, 2)

        # Keep only the latest row (today’s snapshot) for cross-sectional comparison
        final_equity_data = underlying_data.tail(1).copy()

        data_list.append(final_equity_data)

        # Progress printing / rough ETA
        end_time = datetime.now()
        seconds_to_complete = (end_time - start_time).total_seconds()
        times.append(seconds_to_complete)
        iteration = round((np.where(tickers == ticker)[0][0] / len(tickers)) * 100, 2)
        iterations_remaining = len(tickers) - np.where(tickers == ticker)[0][0]
        average_time_to_complete = np.mean(times)
        estimated_completion_time = (datetime.now() + timedelta(seconds=int(average_time_to_complete * iterations_remaining)))
        time_remaining = estimated_completion_time - datetime.now()
        print(f"{iteration}% complete, {time_remaining} left, ETA: {estimated_completion_time}")

    except Exception as error:
        # If a single ticker fails (missing data, API issue), print and continue
        print(error, ticker)
        continue

# =============================================================================
# Cross-Sectional Rankings
# =============================================================================

# Combine the per-ticker "today snapshot" rows into one cross-sectional dataset
full_dataset_original = pd.concat(data_list)

# Restrict to the most recent trading session date (sanity filter)
full_dataset = full_dataset_original[full_dataset_original["date"] == trading_date].copy()

# Exclude OTC stocks if the Polygon field is present in the response
full_dataset = full_dataset[full_dataset["otc"] != True].copy() # exclude OTC stocks

# Define an "exit date" 10 sessions in the future.
# This creates a standardized holding period / forward window for the signal.
full_dataset["exit_date"] = full_dataset["date"].apply(lambda x: all_trading_dates[all_trading_dates >= x][10])

# Cross-sectional percentile rank of distance from average
full_dataset["ranked_dist"] = full_dataset["dist_from_avg"].rank(pct=True)

# Z-score version of the same signal for standardized comparisons
full_dataset["z_dist"] = round(((full_dataset["dist_from_avg"] - full_dataset["dist_from_avg"].mean()) / full_dataset["dist_from_avg"].std()), 2)

# Top 10 tickers by ranked_dist (most extended vs their moving average within the universe)
top_decile_rankings = full_dataset.sort_values(by="ranked_dist", ascending=False).head(10).copy()

top_decile_tickers = top_decile_rankings["ticker"].drop_duplicates().values

# Print a simple “trade sheet” style output:
# Date, ticker, current price, and the standardized exit date.
for top_decile_ticker in top_decile_tickers:

    ticker_info = top_decile_rankings[top_decile_rankings["ticker"] == top_decile_ticker].copy()

    ticker_info_string = f"\nDate: {trading_date} | Ticker: {top_decile_ticker} | Px: {ticker_info['c'].iloc[0]} | Exit Date: {ticker_info['exit_date'].iloc[0]}"
    print(ticker_info_string)