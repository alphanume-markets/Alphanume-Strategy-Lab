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
# 1) Alphanume (point-in-time market cap history)
# 2) Polygon.io (Massive) (daily grouped bars for the full US equity market)
alphanume_api_key = "YOUR_ALPHANUME_API_KEY"
polygon_api_key = "YOUR_POLYGON_API_KEY"

# NYSE calendar is used to create a clean list of valid trading dates
calendar = get_calendar("NYSE")

# all_trading_dates: long history of trading sessions (used for “prior date” lookups)
# trading_dates: window we actually want to test (starting 2024-01-01 through yesterday)
all_trading_dates = calendar.schedule(start_date="2001-01-01", end_date=datetime.now(pytz.timezone("America/New_York")) + timedelta(days=30)).index.strftime("%Y-%m-%d").values

trading_dates = calendar.schedule(start_date="2024-01-01", end_date=(datetime.today() - timedelta(days=1))).index.strftime("%Y-%m-%d").values

# We query market cap starting one session BEFORE our backtest start
# so that the first backtest day has a valid point-in-time universe from the prior session.
query_lookback_date = np.sort(all_trading_dates[all_trading_dates < trading_dates[0]])[-1]

# =============================================================================
# Point-in-Time Market Cap Dataset
# =============================================================================

# We fetch Alphanume's historical market cap dataset using cursor pagination.
# This gives us a point-in-time market cap snapshot per date and ticker.
market_cap_data_list = []
market_cap_base_url = f"https://api.alphanume.com/v1/historical-market-cap?date_gte={query_lookback_date}&api_key={alphanume_api_key}"
market_cap_request_url = market_cap_base_url

# Cursor starts empty; API returns "next_cursor" until has_more == False.
next_cursor = []

while next_cursor is not None:

    try:
        # Request a single “page” of results
        market_cap_request = requests.get(market_cap_request_url).json()

        # Data payload for this page
        market_cap_data = market_cap_request["data"]

        # If empty page is returned, stop
        if len(market_cap_data) < 1:
            break

        # Accumulate this page
        market_cap_data_list.append(market_cap_data)

        # Stop if the API indicates there is no next page
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
        # If anything fails (network / response issues), print and exit
        print(market_cap_request)
        break

# Flatten list-of-pages into a single DataFrame and sort in chronological order
market_cap_dataset = (
    pd.DataFrame([row for page in market_cap_data_list for row in page])
      .sort_values(by=["date", "ticker"], ascending=True)
)

# Create a discrete bucket for market cap class (used later for universe slicing)
market_cap_dataset["market_cap_class"] = market_cap_dataset["market_cap"].apply(market_cap_mapping)

# =============================================================================
# Grouped Return Calcs.
# =============================================================================

# Keep 1 session active (same headers, etc.)
# In practice, requests.Session can reduce overhead vs creating a new connection repeatedly.
connection_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=500)
connection_session.mount('https://', adapter)

# We skip the first date because we need a prior-date universe (point-in-time filter)
data_dates = np.sort(market_cap_dataset["date"].drop_duplicates().values)[1:]

data_list = []
times = []

# For each trading date:
# 1) Build point-in-time universe from the prior session’s market cap file
# 2) Pull Polygon grouped bars (daily OHLCV by ticker)
# 3) Keep only tickers in the prior session universe
# 4) Merge in market cap + market cap class (point-in-time)
for date in data_dates:

    try:

        start_time = datetime.now()

        # Determine the immediately prior trading session
        prior_date = np.sort(all_trading_dates[all_trading_dates < date])[-1]

        # Point-in-time universe (as-of prior session)
        prior_day_mc_data = market_cap_dataset[market_cap_dataset["date"] == prior_date].copy()
        prior_day_mc_tickers = prior_day_mc_data["ticker"].drop_duplicates().values

        # Pull Polygon daily grouped bars (entire market) for this date
        # NOTE: We normalize to a DataFrame indexed by millisecond timestamp.
        grouped_equity_data = (
            pd.json_normalize(
                requests.get(
                    f"https://api.massive.com/v2/aggs/grouped/locale/us/market/stocks/{date}?adjusted=true&include_otc=false&apiKey={polygon_api_key}"
                ).json()["results"]
            )
            .set_index("t")
            .sort_index()
            .rename(columns={"T": "ticker"})
        )

        # Convert timestamp index to NY time and derive a clean date column
        grouped_equity_data["dt"] = pd.to_datetime(grouped_equity_data.index, unit="ms").tz_localize("America/New_York")
        grouped_equity_data["date"] = grouped_equity_data["dt"].dt.strftime("%Y-%m-%d")

        # A simple liquidity proxy (shares * vwap)
        grouped_equity_data["notional_volume"] = grouped_equity_data["v"] * grouped_equity_data["vw"]

        # Filter to only tickers that existed in the prior-day market cap universe (point-in-time)
        valid_equity_data = grouped_equity_data[(grouped_equity_data["ticker"].isin(prior_day_mc_tickers))].copy()
        valid_equity_data = valid_equity_data[["date", "ticker", "o", "h", "l", "c", "v", "vw", "notional_volume"]].copy()

        # Merge market cap fields onto the day’s OHLCV data (still point-in-time from prior session)
        final_equity_data = pd.merge(
            left=valid_equity_data,
            right=prior_day_mc_data[["ticker", "market_cap", "market_cap_class"]],
            on="ticker"
        )

        # Collect this date’s fully filtered + enriched panel
        data_list.append(final_equity_data)

        # Progress printing / rough ETA
        end_time = datetime.now()
        seconds_to_complete = (end_time - start_time).total_seconds()
        times.append(seconds_to_complete)
        iteration = round((np.where(data_dates == date)[0][0] / len(data_dates)) * 100, 2)
        iterations_remaining = len(data_dates) - np.where(data_dates == date)[0][0]
        average_time_to_complete = np.mean(times)
        estimated_completion_time = (datetime.now() + timedelta(seconds=int(average_time_to_complete * iterations_remaining)))
        time_remaining = estimated_completion_time - datetime.now()
        print(f"{iteration}% complete, {time_remaining} left, ETA: {estimated_completion_time}")

    except Exception as error:
        # If a single day fails, print and continue (avoid losing entire run)
        print(error)
        continue

# =============================================================================
# Cross-Sectional Rankings
# =============================================================================

# Combine all dates into a single panel, then sort by (ticker, date) for rolling features
full_dataset_original = pd.concat(data_list)
full_dataset = full_dataset_original.copy().sort_values(["ticker", "date"])

# Rolling 10-day average price feature per ticker.
# This is a “reference anchor” for mean reversion distance calculations.
full_dataset["avg_px"] = (
    full_dataset
        .groupby("ticker")["c"]
        .rolling(window=10, min_periods=10)
        .mean()
        .reset_index(level=0, drop=True)
)

# Only process dates where the rolling feature is available,
# and step through time in 10-session increments.
covered_dates = np.sort(full_dataset["date"].drop_duplicates().values)
dates_to_process = covered_dates[10:: 10]

processed_data_list = []
times = []

# For each “signal date”:
# 1) Build the signal using that date’s close vs its rolling average
# 2) Rank within the cross-section
# 3) Look forward to the next rebalance date and compute forward returns
for covered_date in dates_to_process[:-1]:

    start_time = datetime.now()

    # Next rebalance/measurement date (forward label)
    forward_date = np.sort(dates_to_process[dates_to_process > covered_date])[0]

    # Universe selection: restrict to a specific market cap class (here: nano caps)
    # This is where the strategy "lives" and where mean reversion effects may be strongest.
    time_t_data = full_dataset[(full_dataset["date"] == covered_date) & (full_dataset["market_cap_class"] == 0)].copy()

    # Distance from rolling average (percent)
    # Negative distance means price is below its rolling average (potential rebound candidate)
    time_t_data["dist_from_avg"] = round(((time_t_data["c"] - time_t_data["avg_px"]) / time_t_data["avg_px"]) * 100, 2)

    # Cross-sectional rank of distance (percentile rank)
    time_t_data["ranked_dist"] = time_t_data["dist_from_avg"].rank(pct=True)

    # Z-score version of the same distance signal for standardized comparisons
    time_t_data["z_dist"] = round(((time_t_data["dist_from_avg"] - time_t_data["dist_from_avg"].mean()) / time_t_data["dist_from_avg"].std()), 2)

    # Forward date prices for realized “next period” returns
    forward_t_data = full_dataset[full_dataset["date"] == forward_date].copy()

    # Merge forward close onto the signal universe
    combined_t_data = pd.merge(left=time_t_data, right=forward_t_data[["ticker", "c"]], on="ticker")

    # Forward returns from signal-date close to forward-date close (percent)
    combined_t_data["forward_returns"] = round(((combined_t_data["c_y"] - combined_t_data["c_x"]) / combined_t_data["c_x"]) * 100, 2)

    # Cross-sectional rank of forward returns (for later analysis / diagnostics)
    combined_t_data["ranked_forward_returns"] = combined_t_data["forward_returns"].rank(pct=True)

    processed_data_list.append(combined_t_data)

    # Progress printing / rough ETA
    end_time = datetime.now()
    seconds_to_complete = (end_time - start_time).total_seconds()
    times.append(seconds_to_complete)
    iteration = round((np.where(dates_to_process == covered_date)[0][0] / len(dates_to_process)) * 100, 2)
    iterations_remaining = len(dates_to_process) - np.where(dates_to_process == covered_date)[0][0]
    average_time_to_complete = np.mean(times)
    estimated_completion_time = (datetime.now() + timedelta(seconds=int(average_time_to_complete * iterations_remaining)))
    time_remaining = estimated_completion_time - datetime.now()
    print(f"{iteration}% complete, {time_remaining} left, ETA: {estimated_completion_time}")

# Collate all signal/forward-return observations into one modeling dataset
complete_processed_data = pd.concat(processed_data_list)

# =============================================================================
# Historical Basket Selection
# =============================================================================

# NOTE: This section builds a "rule-based basket" using historical signals.
# For each signal date, we take the top 10 names by ranked_dist (most extended vs average).
complete_processed_data = pd.concat(processed_data_list)

dates_to_model = np.sort(complete_processed_data["date"].drop_duplicates().values)

top_list = []

# For each prediction date:
# 1) Filter to that date’s cross-sectional signal set
# 2) Sort by ranked_dist and take top 10
# 3) Save selections for backtesting aggregation
for prediction_date in dates_to_model:

    out_of_sample_data = complete_processed_data[complete_processed_data["date"] == prediction_date].copy().dropna()

    top_prediction_sample = out_of_sample_data.sort_values(by="ranked_dist", ascending=False).head(10)

    top_list.append(top_prediction_sample)

top_prediction_data = pd.concat(top_list)

# =============================================================================
# Backtest Results
# =============================================================================

# Aggregate returns across the selected basket at each date (equal-weight via mean)
all_trades = top_prediction_data.copy()
all_trades = all_trades.groupby("date").mean(numeric_only=True).reset_index()

# Translate average forward return into a dollar PnL series on a $10,000 notional.
# NOTE: The sign here flips the return; this reflects the strategy’s intended direction
# given how ranked_dist is defined and selected.
all_trades["dollar_pnl"] = 10000 * (all_trades["forward_returns"] / -100)

# Equity curve
all_trades["capital"] = 10000 + all_trades["dollar_pnl"].cumsum()

# Plot capital over time
plt.figure(figsize=(10, 6), dpi=200)
plt.xticks(rotation=45)
plt.title(f"Cross-Sectional Mean Reversion")
plt.plot(pd.to_datetime(all_trades["date"]), all_trades["capital"])
plt.legend(["Gross Equity"])
plt.xlabel("Date")
plt.ylabel("Growth of Capital")
plt.show()
plt.close()