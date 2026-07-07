"""
The Dividend-Capture Screen — live watchlist
============================================

Runs against the forward ex-dividend calendar and writes the names worth trading
into the next couple of weeks: upcoming ex-dates whose history shows a small
ex-day give-back and a quick recovery, ranked by capture yield. Schedule it
(cron) to refresh the watchlist each morning.

What it does:
  1. Pull the dividend-capture history and reduce it to per-ticker recovery stats.
  2. Pull the forward ex-dividend calendar.
  3. Keep upcoming names whose history clears the drop and recovery thresholds.
  4. Rank by capture yield, write a dated watchlist CSV and print it.

Output: "dividend_capture_watchlist_<date>.csv" next to this script.
"""

import requests
import pandas as pd
import pytz
from datetime import datetime

# Paste your Alphanume API key here. Grab a free one at https://www.alphanume.com/
API_KEY = "alp_your_key_here"

BASE = "https://api.alphanume.com/v1"
HISTORY_START = "2026-01-01"   # how far back to build each name's recovery record (Pro for full history)
FUTURE_DAYS = 14               # how far ahead on the ex-dividend calendar to scan (max 120)
RECOVERY_RATE_FLOOR = 0.60     # keep names that recovered within 5 days on at least this share of past ex-dates

today = datetime.now(pytz.timezone("America/New_York")).strftime("%Y-%m-%d")

# 1. Pull history and reduce it to each ticker's average give-back and 5-day recovery rate.
history_request = requests.get(f"{BASE}/dividend-capture?date_gte={HISTORY_START}&api_key={API_KEY}").json()
history_dataset = pd.json_normalize(history_request["data"]).dropna(subset=["drop_ratio_close", "recovered_within_5d"])
historical_stats = history_dataset.groupby("ticker").agg(
    avg_drop_ratio=("drop_ratio_close", "mean"),
    recovery_rate_5d=("recovered_within_5d", "mean"),
).reset_index()

# 2. Pull the forward ex-dividend calendar (upcoming=true bypasses the Free-tier delay).
upcoming_request = requests.get(f"{BASE}/dividend-capture?upcoming=true&future_days={FUTURE_DAYS}&api_key={API_KEY}").json()
upcoming_dataset = pd.json_normalize(upcoming_request["data"])

# 3. Join history onto the calendar and keep names that historically behave.
upcoming_with_history = upcoming_dataset.merge(historical_stats, on="ticker", how="inner")
watchlist = upcoming_with_history[
    (upcoming_with_history["avg_drop_ratio"] < 1.0)
    & (upcoming_with_history["recovery_rate_5d"] >= RECOVERY_RATE_FLOOR)
].copy()

# 4. Rank by capture yield, write the dated watchlist and print it.
watchlist = watchlist.sort_values("capture_yield_pct", ascending=False)
watchlist = watchlist[["date", "ticker", "capture_yield_pct", "cum_close", "breakeven_price", "avg_drop_ratio", "recovery_rate_5d"]]

output_path = f"dividend_capture_watchlist_{today}.csv"
watchlist.to_csv(output_path, index=False)
print(watchlist.to_string(index=False))
print(f"saved {output_path}")
