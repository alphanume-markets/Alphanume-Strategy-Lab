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

# Create a complete daily date array far into the future.
# This is used for simple date arithmetic (e.g., "3 days before" / "1 day after")
# without relying on an exchange calendar.
complete_dates = pd.date_range(
    "2000-01-01",
    (datetime.now(pytz.timezone("America/New_York")) + timedelta(days=365)).strftime("%Y-%m-%d")
).strftime("%Y-%m-%d").values

# Tiingo API key for:
# - listing supported crypto tickers
# - pulling historical OHLCV price data (with resampling)
tiingo_api_key = "YOUR_TIINGO_API_KEY"

# =============================================================================
# Initial Universe Construction
# =============================================================================

# Keep 1 session active (same headers, etc.)
# In practice, requests.Session can reduce overhead for many sequential requests.
connection_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=500)
connection_session.mount('https://', adapter)

# Pull the full Tiingo crypto universe metadata (tickers + base/quote currencies)
ticker_request = connection_session.get(f"https://api.tiingo.com/tiingo/crypto?token={tiingo_api_key}").json()
all_tickers = pd.json_normalize(ticker_request) # full universe

# Filter to USDT-quoted products (e.g., btcusdt, ethusdt, etc.)
valid_ticker_data = all_tickers[all_tickers["quoteCurrency"] == "usdt"].copy()
ticker_sample = valid_ticker_data["ticker"].drop_duplicates().values

data_list = []
times = []

# For each USDT ticker:
# 1) Request exchange availability (includeRawExchangeData)
# 2) Extract which exchanges have raw data for that ticker
# 3) Build a mapping dataset of {ticker -> exchange}
for ticker in ticker_sample:

    try:

        start_time = datetime.now()

        ticker_exchanges_request = connection_session.get(
            f"https://api.tiingo.com/tiingo/crypto/prices?tickers={ticker}&includeRawExchangeData=true&token={tiingo_api_key}"
        ).json()

        # Some tickers may return an empty list; skip them
        if len(ticker_exchanges_request) < 1:
            continue

        # Normalize exchangeData into a DataFrame and use its columns as exchange identifiers
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
        # If a ticker fails (API hiccup / malformed response), print context and continue
        print(error)
        print(ticker_exchanges_request)
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

# Define a short lookback window (last ~10 days) for quick daily signal generation.
# (This script is designed for speed + daily rankings vs building a full research dataset.)
trading_dates = pd.date_range(
    (datetime.now(pytz.timezone("America/New_York")) - timedelta(days=10)).strftime("%Y-%m-%d"),
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
# 4) Forward-fill OHLCV fields to keep a dense panel for feature calculations
for sample_ticker in valid_tickers:

    try:

        start_time = datetime.now()

        prices_request = connection_session.get(
            f"https://api.tiingo.com/tiingo/crypto/prices?tickers={sample_ticker}&startDate={start_date}&endDate={end_date}&resampleFreq={timeframe}&exchanges={desired_exchange}&token={tiingo_api_key}"
        ).json()

        # Some tickers may return an empty list; skip them
        if len(prices_request) < 1:
            continue

        ticker_price_data = pd.json_normalize(prices_request[0]["priceData"])
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

        # Forward-fill core OHLCV fields so the panel stays dense
        cols_to_ffill = ["open", "high", "low", "close", "volume"]
        transormed_price_data[cols_to_ffill] = transormed_price_data[cols_to_ffill].ffill().copy()

        # Final formatting: explicit dt/date/ticker fields
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

# We generate a signal for the most recent date in coverage.
dates_in_coverage = np.sort(full_dataset["date"].drop_duplicates().values)
date = dates_in_coverage[-1]

# Volatility window: 6 bars of 4-hour data = 24-hour lookback window
vol_window_size = 6

# Pull a small range around the decision date (3 days back/forward)
prior_date = np.sort(complete_dates[(complete_dates < date)])[-3]
forward_date = np.sort(complete_dates[(complete_dates > date)])[3]

range_data = full_dataset[(full_dataset["date"] >= prior_date) & (full_dataset["date"] < forward_date)].copy()

# Point-in-time (PIT) snapshot:
# Take the latest bar per ticker for the decision date.
pit_data = (
    range_data[(range_data["date"] == date)]
        .copy()
        .sort_values(["dt", "ticker"])
        .drop_duplicates(subset=["ticker"], keep="last")
)

# PIT timestamp used to define the "decision time" cutoff.
# NOTE: rebalancing_hour is referenced here, so it is assumed to exist upstream in the environment.
pit_dt = (pd.to_datetime(date) + timedelta(hours=rebalancing_hour)).tz_localize("America/New_York")
pit_tickers = pit_data["ticker"].drop_duplicates().values

# Next day's PIT timestamp (used for forward window definition in related scripts)
next_pit_dt = (pit_dt + timedelta(days=1))

daily_performance_list = []
times = []

# For each ticker in the PIT cross-section:
# 1) Compute trailing realized volatility and liquidity proxies
# 2) Compute distance-from-VWAP signal
# 3) Store a single row of features for ranking/output
for pit_ticker in pit_tickers:

    try:

        start_time = datetime.now()

        ticker_data = range_data[range_data["ticker"] == pit_ticker].copy()

        # Use the available window in range_data for feature computation
        historical_ticker_data = ticker_data.copy().sort_values(by="dt", ascending=True)

        # Skip if insufficient history
        if len(historical_ticker_data) < vol_window_size:
            continue

        # Percent change series (used for std deviation / diagnostics)
        historical_ticker_data["pct_chg"] = round(historical_ticker_data["c"].pct_change() * 100, 2)

        # Log returns for realized variance calculations
        historical_ticker_data["log_chg"] = np.log(historical_ticker_data["c"] / historical_ticker_data["c"].shift(1))
        historical_ticker_data["log_chg_sq"] = historical_ticker_data["log_chg"] ** 2

        # Rolling realized variance over 24 hours (6 x 4-hour bars)
        historical_ticker_data["var_cum"] = historical_ticker_data["log_chg_sq"].rolling(window=vol_window_size).sum()

        # Realized vol (annualized) + daily realized vol (de-annualized)
        historical_ticker_data["realized_vol"] = round((np.sqrt(historical_ticker_data["var_cum"]) * np.sqrt(365) * 100), 2)
        historical_ticker_data["daily_realized_vol"] = round((historical_ticker_data["realized_vol"] / np.sqrt(365)), 2)

        # Expected vol proxy (use recent daily realized vol)
        historical_ticker_data["exp_vol"] = historical_ticker_data["daily_realized_vol"]

        # Central price proxy for VWAP-style smoothing
        historical_ticker_data["central_px"] = historical_ticker_data[["open", "high", "low", "c"]].mean(axis=1)

        # VWAP proxy:
        # central price * volume / volume simplifies to central price, then smoothed by rolling mean
        historical_ticker_data["vwap_px"] = (historical_ticker_data["central_px"] * historical_ticker_data["volume"]) / historical_ticker_data["volume"]
        historical_ticker_data["vwap"] = historical_ticker_data["vwap_px"].rolling(vol_window_size, min_periods=1).mean()

        # Notional liquidity proxy and rolling average notional
        historical_ticker_data["notional"] = historical_ticker_data["vwap_px"] * historical_ticker_data["volume"]
        historical_ticker_data["avg_notional"] = historical_ticker_data["notional"].rolling(vol_window_size, min_periods=1).mean()

        # Mean reversion signal: percent distance from (smoothed) VWAP
        historical_ticker_data["dist_from_vwap"] = round(((historical_ticker_data["c"] - historical_ticker_data["vwap"]) / historical_ticker_data["vwap"]) * 100, 2)

        # Rolling return across the available window (from first bar to last bar)
        historical_ticker_data["returns"] = round(((historical_ticker_data["c"] - historical_ticker_data["c"].iloc[0]) / historical_ticker_data["c"].iloc[0]) * 100, 2)
        rolling_return = historical_ticker_data["returns"].iloc[-1]

        # Simple risk-adjusted proxy using return std and sqrt(n) scaling (Sharpe-like)
        return_std = historical_ticker_data["pct_chg"].std()
        sharpe = round((rolling_return / (return_std * np.sqrt(len(historical_ticker_data)))), 2)

        # Grab final feature values for output/ranking
        avg_notional = historical_ticker_data["avg_notional"].iloc[-1]
        dist_from_vwap = historical_ticker_data["dist_from_vwap"].iloc[-1]
        exp_vol = historical_ticker_data["exp_vol"].iloc[-1]

        # Single-row feature record for this ticker
        ticker_performance_data = pd.DataFrame([{
            "date": date,
            "ticker": pit_ticker,
            "exp_vol": exp_vol,
            "sharpe": sharpe,
            "rolling_return": rolling_return,
            "avg_notional": avg_notional,
            "dist_from_vwap": dist_from_vwap
        }])

        daily_performance_list.append(ticker_performance_data)

        # Progress printing / rough ETA
        end_time = datetime.now()
        seconds_to_complete = (end_time - start_time).total_seconds()
        times.append(seconds_to_complete)
        iteration = round((np.where(pit_tickers == pit_ticker)[0][0] / len(pit_tickers)) * 100, 2)
        iterations_remaining = len(pit_tickers) - np.where(pit_tickers == pit_ticker)[0][0]
        average_time_to_complete = np.mean(times)
        estimated_completion_time = (datetime.now() + timedelta(seconds=int(average_time_to_complete * iterations_remaining)))
        time_remaining = estimated_completion_time - datetime.now()
        print(f"{iteration}% complete, {time_remaining} left, ETA: {estimated_completion_time}")

    except Exception as error:
        # If a single ticker fails, continue
        continue

# Combine the per-ticker feature rows into a cross-sectional snapshot and rank the signal
daily_performance_data = pd.concat(daily_performance_list).dropna()
daily_performance_data["ranked_dist"] = daily_performance_data["dist_from_vwap"].rank(pct=True)

# =============================================================================
# Forward Outputs
# =============================================================================

# Final output dataset for "today":
# - includes ranked signal
# - includes a standardized futures-style ticker format
# - includes a simple exit_date (next day) for operational use
full_cross_sectional_data = daily_performance_data.copy()

# Convert spot-style ticker (e.g., "btcusdt") into futures-style format (e.g., "BTC_USDT")
full_cross_sectional_data["futures_ticker"] = (
    full_cross_sectional_data["ticker"]
        .str.replace("usdt", "", regex=False)
        .str.upper()
    + "_USDT"
)

# Define exit date as the next calendar day (1 day forward)
full_cross_sectional_data["exit_date"] = full_cross_sectional_data["date"].apply(lambda x: complete_dates[complete_dates >= x][1])

# Select the top 10 names by ranked_dist (most extended vs VWAP)
top_decile_rankings = full_cross_sectional_data.sort_values(by="ranked_dist", ascending=False).head(10).copy()
top_decile_tickers = top_decile_rankings["ticker"].drop_duplicates().values

# Print a “trade sheet” style output:
# Date, futures-formatted ticker, and standardized exit date
for top_decile_ticker in top_decile_tickers:

    ticker_info = top_decile_rankings[top_decile_rankings["ticker"] == top_decile_ticker].copy()

    ticker_info_string = f"\nDate: {ticker_info['date'].iloc[0]} | Ticker: {ticker_info['futures_ticker'].iloc[0]} | Exit Date: {ticker_info['exit_date'].iloc[0]}"
    print(ticker_info_string)