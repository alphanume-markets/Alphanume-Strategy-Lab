"""
IV-rank mean reversion
=======================

The first idea from the post: stretched implied vol comes back down.

This script pulls the IV/HV Rank feed for a basket of liquid names, places each
day's 30-day implied vol where it sits in that name's own trailing year (the
"IV rank", 0 = the year's low, 100 = the year's high), and then asks a simple
question: when a name's IV is high in its own range, what does that IV do over
the next month?

The answer is the whole point of using IV rank instead of eyeballing a raw vol
number. We bucket every (ticker, day) into IV-rank deciles and measure the
average forward change in IV. Stretched names (high rank) tend to fall. Quiet
names (low rank) tend to rise.

What it does:
  1. Pull /iv-rank history for each ticker in TICKERS.
  2. For each row, look 21 trading days ahead and compute the percent change in IV.
  3. Group by IV-rank decile and average that forward change.
  4. Print the decile table and save a bar chart.

Output: a printed table and "iv_rank_reversion.png" next to this script.
"""

import requests
import pandas as pd
import matplotlib.pyplot as plt

# Paste your Alphanume API key here. Grab a free one at https://www.alphanume.com/
API_KEY = "alp_your_key_here"

BASE = "https://api.alphanume.com/v1"
HORIZON_DAYS = 21   # one trading month forward

# A basket of liquid, optionable names. Edit this list however you like.
TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "AVGO", "NFLX",
    "INTC", "MU", "QCOM", "MRVL", "CRM", "ORCL", "ADBE", "CSCO", "TXN", "PYPL",
    "JPM", "BAC", "GS", "WFC", "C", "XOM", "CVX", "BA", "CAT", "GE",
    "DIS", "KO", "PEP", "WMT", "COST", "HD", "NKE", "PFE", "MRNA", "UNH",
]

# 1. Pull the IV/HV Rank history for every ticker and stack it into one table.
rows = []
for ticker in TICKERS:
    resp = requests.get(
        BASE + "/iv-rank",
        params={"ticker": ticker, "only_final": "true", "api_key": API_KEY},
    )
    rows += resp.json()["data"]
    print("pulled", ticker)

df = pd.DataFrame(rows)
df = df[["ticker", "date", "iv", "iv_rank"]].sort_values(["ticker", "date"])

# 2. Look one month ahead (within each ticker) and measure the percent change in IV.
df["iv_future"] = df.groupby("ticker")["iv"].shift(-HORIZON_DAYS)
df["iv_change_pct"] = (df["iv_future"] / df["iv"] - 1) * 100
df = df.dropna(subset=["iv_change_pct"])

# 3. Bucket into IV-rank deciles and average the forward change in each.
df["decile"] = pd.qcut(df["iv_rank"], 10, labels=False)
summary = df.groupby("decile").agg(
    avg_iv_rank=("iv_rank", "mean"),
    avg_iv_change_pct=("iv_change_pct", "mean"),
    n=("iv_change_pct", "size"),
)
print("\nForward IV change by IV-rank decile")
print(summary.round(2))

# 4. Plot it. Highest decile gets the accent color.
colors = ["#9AA5AD"] * len(summary)
colors[-1] = "#E8603C"
plt.figure(figsize=(9, 5))
plt.bar(summary["avg_iv_rank"], summary["avg_iv_change_pct"], width=8, color=colors)
plt.axhline(0, color="black", linewidth=1)
plt.title("Stretched implied vol comes back down", fontsize=14, fontweight="bold")
plt.xlabel("IV rank at entry (0 = year's low, 100 = year's high)")
plt.ylabel("Average IV change over next month (%)")
plt.tight_layout()
plt.savefig("iv_rank_reversion.png", dpi=150)
print("\nsaved iv_rank_reversion.png")
