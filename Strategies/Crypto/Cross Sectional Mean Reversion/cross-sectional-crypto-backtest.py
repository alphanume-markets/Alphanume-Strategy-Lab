# -*- coding: utf-8 -*-
"""
@author: Alphanume Strategy Lab
"""

import pandas as pd
import numpy as np
import requests
import pytz
import matplotlib.pyplot as plt

from datetime import datetime, timedelta

# =============================================================================
# Core-Requisites
# =============================================================================

# Create a “complete” daily date array far into the future.
# This is used for simple date arithmetic (e.g., "3 days before" / "3 days after")
# without having to rely on an exchange calendar.
complete_dates = pd.date_range("2000-01-01", (datetime.now(pytz.timezone("America/New_York")) + timedelta(days=365)).strftime("%Y-%m-%d")).strftime("%Y-%m-%d").values

# Tiingo API key for:
# - listing supported crypto tickers
# - pulling OHLCV price history (with resampling)
tiingo_api_key = "YOUR_TIINGO_API_KEY"

# =============================================================================
# Initial Universe Construction
# =============================================================================

# Keep 1 session active (same headers, etc.)
# In practice, requests.Session can reduce overhead for many sequential requests.
connection_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=500)
connection_session.mount('https://', adapter)

# Pull the full Tiingo crypto universe metadata (tickers + base/quote currencies, etc.)
ticker_request = connection_session.get(f"https://api.tiingo.com/tiingo/crypto?token={tiingo_api_key}").json()
all_tickers = pd.json_normalize(ticker_request) # full universe

# Filter to USDT-quoted products (e.g., BTCUSDT, ETHUSDT, etc.)
valid_ticker_data = all_tickers[all_tickers["quoteCurrency"] == "usdt"].copy()
ticker_sample = valid_ticker_data["ticker"].drop_duplicates().values

data_list = []
times = []

# For each USDT ticker:
# 1) Request raw exchange data availability
# 2) Extract which exchanges support the ticker
# 3) Build a mapping dataset of {ticker -> exchange}
for ticker in ticker_sample:

    try:

        start_time = datetime.now()

        # Pull exchange availability for this ticker (includeRawExchangeData exposes "exchangeData")
        ticker_exchanges_request = connection_session.get(
            f"https://api.tiingo.com/tiingo/crypto/prices?tickers={ticker}&includeRawExchangeData=true&token={tiingo_api_key}"
        ).json()

        # Normalize the exchangeData structure to inspect available exchange columns
        ticker_exchanges = pd.json_normalize(ticker_exchanges_request[0]["exchangeData"])
        ticker_exchanges_array = ticker_exchanges.columns

        # Store one row per ticker per exchange
        ticker_data = pd.DataFrame({"ticker": ticker, "exchanges": ticker_exchanges_array})
        data_list.append(ticker_data)

        # Progress printing / rough ETA
        end_time = datetime.now()
        seconds_to_complete = (end_time - start_time).total_seconds()
        times.append(seconds_to_complete)
        iteration = round((np.where(ticker_sample == ticker)[0][0] / len(ticker_sample)) * 100, 2)
        iterations_remaining = len(ticker_sample) - np.where(ticker_sample == ticker)[0][0]
        average_time_to_complete = np.mean(times)
        estimated_completion_time = (datetime.now() + timedelta(seconds=int(average_time_to_complete * iterations_remaining)))
        time_remaining = estimated_completion_time - datetime.now()
        print(f"{iteration}% complete, {time_remaining} left, ETA: {estimated_completion_time}")

    except Exception as error:
        # If a single ticker fails, skip it (missing exchange data / API hiccup)
        continue

# Combine the mapping into a single dataset of all tickers and their supported exchanges
tickers_and_exchanges = pd.concat(data_list)

# Select a universe based on exchange availability.
# Here: keep only tickers that have data on MEXC.
exchange_sample = (
    tickers_and_exchanges[tickers_and_exchanges["exchanges"] == "MEXC"]
        .copy()
        .drop_duplicates(subset=["ticker"])
)

valid_tickers = exchange_sample["ticker"].drop_duplicates().values

# =============================================================================
# Historical Data Collection
# =============================================================================

# Define the historical window to collect.
# Here: ~2 years through tomorrow (tomorrow used as a safe "inclusive end" boundary).
trading_dates = pd.date_range(
    (datetime.now(pytz.timezone("America/New_York")) - timedelta(days=365 * 2)).strftime("%Y-%m-%d"),
    (datetime.now(pytz.timezone("America/New_York")) + timedelta(days=1)).strftime("%Y-%m-%d")
).strftime("%Y-%m-%d").values

start_date = trading_dates[0]
end_date = trading_dates[-1]

# Universe definition for the dataset:
# - desired_exchange: exchange that defines the universe and data source
# - timeframe: Tiingo resample frequency
# - dataset_frequency: pandas frequency used for reindexing/filling missing bars
desired_exchange = "MEXC"
timeframe = "4hour"
dataset_frequency = "4h"

# Keep 1 session active (same headers, etc.)
connection_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=500)
connection_session.mount('https://', adapter)

ohlc_data_list = []
times = []

# For each valid ticker:
# 1) Pull 4-hour OHLCV from Tiingo for the selected exchange
# 2) Convert timestamps to NY time
# 3) Reindex to a complete 4-hour grid (fills missing bars)
# 4) Forward-fill OHLCV fields to keep a dense panel for cross-sectional calculations
for sample_ticker in valid_tickers:

    try:

        start_time = datetime.now()

        # Pull resampled OHLCV for the exchange and timeframe
        prices_request = connection_session.get(
            f"https://api.tiingo.com/tiingo/crypto/prices?tickers={sample_ticker}&startDate={start_date}&endDate={end_date}&resampleFreq={timeframe}&exchanges={desired_exchange}&token={tiingo_api_key}"
        ).json()

        # Normalize the priceData block into a DataFrame
        ticker_price_data = pd.json_normalize(prices_request[0]["priceData"])

        # Convert to a timezone-aware NY datetime column
        ticker_price_data["dt"] = pd.to_datetime(ticker_price_data["date"], utc=True).dt.tz_convert("America/New_York")

        # Prepare for reindexing on a continuous 4-hour grid
        pre_transformed_price_data = ticker_price_data.set_index("dt").copy()

        # Build a complete 4-hour index from first to last timestamp
        full_range = pd.date_range(
            start=pre_transformed_price_data.index.min(),
            end=pre_transformed_price_data.index.max(),
            freq=dataset_frequency
        )

        # Reindex onto the continuous grid (introduces NaNs where bars are missing)
        transormed_price_data = pre_transformed_price_data.reindex(full_range)

        # Forward-fill core OHLCV fields so the panel stays dense.
        # (This makes later rolling features and cross-sectional computations easier.)
        cols_to_ffill = ["open", "high", "low", "close", "volume"]
        transormed_price_data[cols_to_ffill] = transormed_price_data[cols_to_ffill].ffill().copy()

        # Final formatting: explicit dt/date/ticker fields for merging/ranking later
        processed_price_data = transormed_price_data.copy().reset_index().rename(columns={"index": "dt"})
        processed_price_data["date"] = processed_price_data["dt"].dt.strftime("%Y-%m-%d")
        processed_price_data["ticker"] = sample_ticker

        ohlc_data_list.append(processed_price_data)

        # Progress printing / rough ETA
        end_time = datetime.now()
        seconds_to_complete = (end_time - start_time).total_seconds()
        times.append(seconds_to_complete)
        iteration = round((np.where(valid_tickers == sample_ticker)[0][0] / len(valid_tickers)) * 100, 2)
        iterations_remaining = len(valid_tickers) - np.where(valid_tickers == sample_ticker)[0][0]
        average_time_to_complete = np.mean(times)
        estimated_completion_time = (datetime.now() + timedelta(seconds=int(average_time_to_complete * iterations_remaining)))
        time_remaining = estimated_completion_time - datetime.now()
        print(f"{iteration}% complete, {time_remaining} left, ETA: {estimated_completion_time}")

    except Exception as error:
        # If a ticker fails (missing data / malformed response), log and continue
        print(error)
        print(prices_request)
        continue

# Combine all tickers into one panel and normalize column naming
full_dataset = pd.concat(ohlc_data_list).rename(columns={"close": "c"})

# =============================================================================
# Modeling
# =============================================================================

# We'll form daily “decision dates” based on the dates present in the panel.
dates_in_coverage = np.sort(full_dataset["date"].drop_duplicates().values)
dates_to_model = dates_in_coverage[10:]  # skip earliest window so rolling features have time to form

# Rebalancing time (hour) used for point-in-time snapshots.
# Note: pit_data below uses date-level selection, while pit_dt sets a specific timestamp for calculations.
rebalancing_hour = 20

# Volatility window: 6 bars of 4-hour data = 24-hour realized variance/vol calculations
vol_window_size = 6 # 4-hour data, so a 24-hour lookback window for calculations

cross_sectional_data_list = []
times = []

# For each modeling date:
# 1) Pull a small range of data around the date (prior/forward)
# 2) Create a point-in-time snapshot (pit_dt) for each ticker
# 3) Compute features from the trailing window up to pit_dt
# 4) Compute forward returns from pit_dt to the next pit_dt (one day forward)
# 5) Store cross-sectional feature/return rows for later ranking and backtesting
for date in dates_to_model:

    try:

        start_time = datetime.now()

        # Expand the range window around the decision date (3 days back/forward)
        prior_date = np.sort(complete_dates[(complete_dates < date)])[-3]
        forward_date = np.sort(complete_dates[(complete_dates > date)])[3]

        # Pull the local time range for feature construction and forward return measurement
        range_data = full_dataset[(full_dataset["date"] >= prior_date) & (full_dataset["date"] < forward_date)].copy()
        range_data["hour"] = range_data["dt"].dt.hour

        # Point-in-time snapshot selection:
        # Here we take one row per ticker for the given date.
        # (Alternative commented line indicates intent to use a specific hour-based snapshot.)
        # pit_data = range_data[(range_data["date"] == date) & (range_data["hour"] == rebalancing_hour)].copy()
        pit_data = range_data[(range_data["date"] == date)].copy().drop_duplicates(subset=["ticker"])

        # Define point-in-time timestamp for feature cutoff
        pit_dt = (pd.to_datetime(date) + timedelta(hours=rebalancing_hour)).tz_localize("America/New_York")
        pit_tickers = pit_data["ticker"].drop_duplicates().values

        # Next day's point-in-time timestamp (used for forward return window)
        next_pit_dt = (pit_dt + timedelta(days=1))

        daily_performance_list = []

        # For each ticker in the point-in-time cross-section:
        # - compute trailing features up to pit_dt
        # - compute 1-day forward return from pit_dt to next_pit_dt
        for pit_ticker in pit_tickers:

            try:

                ticker_data = range_data[range_data["ticker"] == pit_ticker].copy()

                # Trailing history up to pit_dt (feature window)
                historical_ticker_data = ticker_data[ticker_data["dt"] <= pit_dt].copy().sort_values(by="dt", ascending=True)

                # Skip tickers with insufficient history for rolling calculations
                if len(historical_ticker_data) < vol_window_size:
                    continue

                # Simple percent change (used for std dev and diagnostic measures)
                historical_ticker_data["pct_chg"] = round(historical_ticker_data["c"].pct_change() * 100, 2)

                # Log returns for realized variance calculations
                historical_ticker_data["log_chg"] = np.log(historical_ticker_data["c"] / historical_ticker_data["c"].shift(1))
                historical_ticker_data["log_chg_sq"] = historical_ticker_data["log_chg"] ** 2

                # Rolling realized variance over the last 24 hours (6 x 4-hour bars)
                historical_ticker_data["var_cum"] = historical_ticker_data["log_chg_sq"].rolling(window=vol_window_size).sum()

                # Realized volatility (annualized) and its daily (de-annualized) counterpart
                historical_ticker_data["realized_vol"] = round((np.sqrt(historical_ticker_data["var_cum"]) * np.sqrt(365) * 100), 2)
                historical_ticker_data["daily_realized_vol"] = round((historical_ticker_data["realized_vol"] / np.sqrt(365)), 2)

                # Expected vol proxy (here: use recent daily realized vol as expectation)
                historical_ticker_data["exp_vol"] = historical_ticker_data["daily_realized_vol"]
                historical_ticker_data["central_px"] = historical_ticker_data[["open", "high", "low", "c"]].mean(axis=1)

                # VWAP-style proxy:
                # central price * volume / volume simplifies to central price, then smoothed via rolling mean
                historical_ticker_data["vwap_px"] = (historical_ticker_data["central_px"] * historical_ticker_data["volume"]) / historical_ticker_data["volume"]
                historical_ticker_data["vwap"] = historical_ticker_data["vwap_px"].rolling(vol_window_size, min_periods=1).mean()

                # Notional liquidity proxy (price * volume) smoothed over the same window
                historical_ticker_data["notional"] = historical_ticker_data["vwap_px"] * historical_ticker_data["volume"]
                historical_ticker_data["avg_notional"] = historical_ticker_data["notional"].rolling(vol_window_size, min_periods=1).mean()

                # Mean reversion signal: percent distance from (smoothed) VWAP
                historical_ticker_data["dist_from_vwap"] = round(((historical_ticker_data["c"] - historical_ticker_data["vwap"]) / historical_ticker_data["vwap"]) * 100, 2)

                # Rolling return over the trailing window (from first bar to last bar)
                historical_ticker_data["returns"] = round(((historical_ticker_data["c"] - historical_ticker_data["c"].iloc[0]) / historical_ticker_data["c"].iloc[0]) * 100, 2)
                rolling_return = historical_ticker_data["returns"].iloc[-1]

                # Simple risk-adjusted proxy:
                # use std dev of percent changes and scale by sqrt(n) for a rough Sharpe-like measure
                return_std = historical_ticker_data["pct_chg"].std()
                sharpe = round((rolling_return / (return_std * np.sqrt(len(historical_ticker_data)))), 2)

                # Grab final feature values at pit_dt
                avg_notional = historical_ticker_data["avg_notional"].iloc[-1]
                dist_from_vwap = historical_ticker_data["dist_from_vwap"].iloc[-1]
                exp_vol = historical_ticker_data["exp_vol"].iloc[-1]

                # =============================================================================
                #         Forward Calcs
                # =============================================================================

                # Forward window: from pit_dt to next_pit_dt (one day)
                forward_ticker_data = ticker_data[(ticker_data["dt"] >= pit_dt) & (ticker_data["dt"] <= next_pit_dt)].copy().sort_values(by="dt", ascending=True)
                forward_ticker_data["returns"] = round(((forward_ticker_data["c"] - forward_ticker_data["c"].iloc[0]) / forward_ticker_data["c"].iloc[0]) * 100, 2)

                # Forward realized return over the hold window
                forward_ticker_returns = forward_ticker_data["returns"].iloc[-1]

                # Single-row “modeling record” for this ticker and date
                ticker_performance_data = pd.DataFrame([{
                    "date": date,
                    "ticker": pit_ticker,
                    "exp_vol": exp_vol,
                    "sharpe": sharpe,
                    "rolling_return": rolling_return,
                    "avg_notional": avg_notional,
                    "dist_from_vwap": dist_from_vwap,
                    "forward_returns": forward_ticker_returns
                }])

                daily_performance_list.append(ticker_performance_data)

            except Exception as error:
                # If a single ticker fails, print error and continue
                print(error)
                continue

        # Combine all tickers for the day into a cross-sectional panel
        daily_performance_data = pd.concat(daily_performance_list).dropna()

        # Rank the signal cross-sectionally (percentile rank)
        # Higher ranked_dist means more extended vs VWAP (as defined by dist_from_vwap).
        daily_performance_data["ranked_dist"] = daily_performance_data["dist_from_vwap"].rank(pct=True)

        cross_sectional_data_list.append(daily_performance_data)

        # Progress printing / rough ETA
        end_time = datetime.now()
        seconds_to_complete = (end_time - start_time).total_seconds()
        times.append(seconds_to_complete)
        iteration = round((np.where(dates_to_model == date)[0][0] / len(dates_to_model)) * 100, 2)
        iterations_remaining = len(dates_to_model) - np.where(dates_to_model == date)[0][0]
        average_time_to_complete = np.mean(times)
        estimated_completion_time = (datetime.now() + timedelta(seconds=int(average_time_to_complete * iterations_remaining)))
        time_remaining = estimated_completion_time - datetime.now()
        print(f"{iteration}% complete, {time_remaining} left, ETA: {estimated_completion_time}")

    except Exception as error:
        # If a date fails entirely, skip it
        continue

# =============================================================================
# Backtesting
# =============================================================================

# Combine all daily cross-sectional panels into one dataset
full_cross_sectional_data = pd.concat(cross_sectional_data_list)
cross_sectional_dates = full_cross_sectional_data["date"].drop_duplicates().values

trade_list = []

# Simple rules-based backtest:
# For each date:
# 1) Rank tickers by ranked_dist
# 2) Take top 10
# 3) Record the average forward return of that basket
for oos_date in cross_sectional_dates:

    oos_data = full_cross_sectional_data[full_cross_sectional_data["date"] == oos_date].copy()

    ranked_basket = oos_data.sort_values(by="ranked_dist", ascending=False).head(10)

    basket_outcome = pd.DataFrame([{"date": oos_date, "basket_return": ranked_basket["forward_returns"].mean()}])

    trade_list.append(basket_outcome)

all_trades = pd.concat(trade_list)

# Translate basket return into dollar PnL for a $10,000 notional.
# NOTE: The sign here flips the return; this reflects the intended direction
# given how ranked_dist is defined and selected.
all_trades["dollar_pnl"] = 10000 * (all_trades["basket_return"] / -100)

# Equity curve
all_trades["capital"] = 10000 + (all_trades["dollar_pnl"].cumsum())

# Plot capital over time
fig, ax = plt.subplots(figsize=(10, 6), dpi=200)
plt.xticks(rotation=45)
plt.suptitle("Cross-Sectional Mean Reversion")
plt.title(f"{desired_exchange} Exchange Universe")
plt.plot(pd.to_datetime(all_trades["date"]), all_trades["capital"].values)

# Light aesthetic cleanup (remove box, reduce visual noise)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

ax.grid(axis="y", alpha=0.25)
ax.grid(axis="x", alpha=0)

plt.legend(["Gross Equity"])
plt.xlabel("Date")
plt.ylabel("Growth of Capital")
plt.show()
plt.close()