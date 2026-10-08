"""
Shorting Pre-Market Pumps — gross backtest
==========================================

Small caps that rip in pre-market on a press release or a reverse split tend to give
it back once the regular session opens. Alphanume's Pre-Market Drop Risk model ranks
those names each morning by their odds of falling 5%+ from the open to the close.
This script shorts every $1+ name in equal size at the open, covers at the close, and
adds up the days.

It's a gross backtest: no locate fees, no slippage, no position limits. Look at the
worst day before you size anything.

What it does:
  1. Pull the full Pre-Market Drop Risk history.
  2. Average each day's open-to-close return across the basket and flip the sign (we're short).
  3. Print the summary and the worst days.
  4. Save the cumulative return chart.

Output: a printed summary and "premarket_drop_risk_backtest.png" next to this script.
"""

import requests
import pandas as pd
import matplotlib.pyplot as plt

# Paste your Alphanume API key here. Pre-Market Drop Risk needs a Pro key: https://www.alphanume.com/pricing
API_KEY = "alp_your_key_here"

BASE = "https://api.alphanume.com/v1"
MIN_PRICE = 1    # skip sub-dollar names, same as production.py

# 1. Pull the full history. Leaving out the date returns every row.
premarket_request = requests.get(f"{BASE}/premarket-drop-risk?min_price={MIN_PRICE}&api_key={API_KEY}").json()
history = pd.json_normalize(premarket_request["data"]).dropna(subset=["intraday_return_pct"])

# 2. One number per day: the basket's average open-to-close move, flipped for the short side.
daily_short_return = -history.groupby("date")["intraday_return_pct"].mean().sort_index()
daily_short_return.index = pd.to_datetime(daily_short_return.index)
cumulative_return = daily_short_return.cumsum()

# 3. Summary.
print(f"Days: {len(daily_short_return)} ({daily_short_return.index[0]:%Y-%m-%d} to {daily_short_return.index[-1]:%Y-%m-%d})")
print(f"Names per day: {history.groupby('date').size().mean():.1f}")
print(f"Average day: {daily_short_return.mean():+.2f}%")
print(f"Winning days: {(daily_short_return > 0).mean():.0%}")
print(f"Shorts where the stock fell: {(history['intraday_return_pct'] < 0).mean():.0%}")
print(f"Cumulative (sum of daily %): {cumulative_return.iloc[-1]:+.0f}%")
print("\nWorst days:")
print(daily_short_return.nsmallest(5).round(1).to_string())

# 4. Chart.
plt.figure(figsize=(10, 5))
plt.plot(cumulative_return.index, cumulative_return.values)
plt.axhline(0, color="gray", linewidth=0.8)
plt.title("Pre-Market Drop Risk: equal-weight short, open to close, gross")
plt.ylabel("Cumulative return (sum of daily %)")
plt.tight_layout()
plt.savefig("premarket_drop_risk_backtest.png", dpi=150)
plt.show()
