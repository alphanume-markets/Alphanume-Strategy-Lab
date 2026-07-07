"""
The Dividend-Capture Screen That Only Keeps Names That Bounce Back Fast
======================================================================

Dividend capture looks like free money and usually isn't: plenty of stocks drop
by more than the dividend on the ex-date and never recover, so the average trade
is a coin flip. The edge is in the names that give back less than they pay and
snap back fast. But you only know a name behaves that way from its PAST ex-dates,
so the screen has to be point-in-time: judge each event on the ticker's prior
history only, exactly the way production.py does, then measure what that event
actually paid. That keeps the backtest honest and tradeable.

What it does:
  1. Pull the dividend-capture history for the rolling lookback window.
  2. Keep settled ex-dividend events with the fields the screen needs, and order each name by ex-date.
  3. For each event, build point-in-time stats from ONLY that ticker's PRIOR ex-dates (trailing 5-day recovery rate and average drop ratio).
  4. Screen point-in-time and compare the screened book against the unscreened eligible baseline.
  5. Print the summary, led by the low-drop/fast-recovery quadrant split.
  6. Save the quadrant figure that motivates the screen.

Output: a printed summary and "dividend_capture_fast_recovery.png" next to this script.
"""

import requests
import pandas as pd
import pytz
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Paste your Alphanume API key here. Grab a free one at https://www.alphanume.com/
API_KEY = "alp_your_key_here"

BASE = "https://api.alphanume.com/v1"
LOOKBACK_DAYS = 28             # rolling history window. Free tier serves ~the last 30 days; with a Pro key set this to e.g. 900 to reproduce the post's full-history numbers.
MIN_PRIOR_EVENTS = 4           # need at least this many past ex-dates before trusting a name's record
RECOVERY_RATE_FLOOR = 0.60     # keep names that recovered within 5 days on at least this share of PAST ex-dates
DROP_RATIO_CEILING = 1.0       # and whose past ex-days gave back LESS than the dividend on average

start_date = (datetime.now(pytz.timezone("America/New_York")) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")

# 1. Pull the dividend-capture history from Alphanume.
dividend_capture_request = requests.get(f"{BASE}/dividend-capture?date_gte={start_date}&api_key={API_KEY}").json()
dividend_capture_dataset = pd.json_normalize(dividend_capture_request["data"])

# 2. Keep settled events that carry the fields the screen needs, and order each name by ex-date.
dividend_events = dividend_capture_dataset.dropna(subset=["net_capture_pct", "drop_ratio_close", "recovered_within_5d"]).copy()
dividend_events["net_capture_pct"] = pd.to_numeric(dividend_events["net_capture_pct"], errors="coerce")
dividend_events["drop_ratio_close"] = pd.to_numeric(dividend_events["drop_ratio_close"], errors="coerce")
dividend_events["recovered_5d"] = dividend_events["recovered_within_5d"].astype(str).str.strip().str.lower().isin(["true", "1", "1.0", "yes"]).astype(float)
dividend_events = dividend_events.dropna(subset=["net_capture_pct", "drop_ratio_close"])
dividend_events = dividend_events.sort_values(["ticker", "date"]).reset_index(drop=True)

# 3. For each event, build point-in-time stats from ONLY that ticker's PRIOR ex-dates.
#    Shifting the expanding mean by one row keeps the current event out of its own screen.
events_by_ticker = dividend_events.groupby("ticker", group_keys=False)
dividend_events["prior_event_count"] = events_by_ticker.cumcount()
dividend_events["prior_recovery_rate"] = events_by_ticker["recovered_5d"].apply(lambda s: s.shift(1).expanding().mean())
dividend_events["prior_avg_drop_ratio"] = events_by_ticker["drop_ratio_close"].apply(lambda s: s.shift(1).expanding().mean())

# 4. Screen point-in-time, then compare the screened book against the unscreened eligible baseline.
eligible_book = dividend_events[dividend_events["prior_event_count"] >= MIN_PRIOR_EVENTS].copy()
screened_book = eligible_book[
    (eligible_book["prior_recovery_rate"] >= RECOVERY_RATE_FLOOR)
    & (eligible_book["prior_avg_drop_ratio"] < DROP_RATIO_CEILING)
].copy()

# 5. Print the summary. The quadrant split (names that drop little AND recover fast vs everything else)
#    is cross-sectional over every event, so it leads and holds even on a short Free window. The
#    point-in-time books below are thin on a Free 30-day window (few names have 4+ prior ex-dates in a
#    month); widen LOOKBACK_DAYS with a Pro key to fill them in and reproduce the post's numbers.
money_quadrant = (dividend_events["drop_ratio_close"] < 1.0) & (dividend_events["recovered_5d"] == 1.0)
print(f"window: {start_date} to today over {len(dividend_events)} settled events, {dividend_events['ticker'].nunique()} tickers")
print(f"low drop + fast recovery: avg net capture {dividend_events.loc[money_quadrant, 'net_capture_pct'].mean():+.3f}%   everything else: {dividend_events.loc[~money_quadrant, 'net_capture_pct'].mean():+.3f}%")
print(f"unscreened eligible:      {len(eligible_book):>6}   avg net capture {eligible_book['net_capture_pct'].mean():+.3f}%   win rate {(eligible_book['net_capture_pct'] > 0).mean() * 100:.1f}%")
print(f"screened (point-in-time): {len(screened_book):>6}   avg net capture {screened_book['net_capture_pct'].mean():+.3f}%   win rate {(screened_book['net_capture_pct'] > 0).mean() * 100:.1f}%")

# 6. Plot what motivates the screen: the low-drop, fast-recovery quadrant is where the money is.
quadrant_capture = pd.Series({
    "everything else": dividend_events.loc[~money_quadrant, "net_capture_pct"].mean(),
    "low drop + fast recovery": dividend_events.loc[money_quadrant, "net_capture_pct"].mean(),
})

plt.figure(figsize=(9, 5))
plt.bar(quadrant_capture.index, quadrant_capture.values, color=["#9AA5AD", "#E8603C"])
plt.axhline(0, color="black", linewidth=1)
plt.title("The money is in names that drop little and recover fast", fontsize=14, fontweight="bold")
plt.ylabel("Average net capture (%)")
plt.tight_layout()
plt.savefig("dividend_capture_fast_recovery.png", dpi=150)
print("saved dividend_capture_fast_recovery.png")
