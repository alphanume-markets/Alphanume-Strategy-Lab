"""
Stack the filters, stack the edge
=================================

The second idea from the post: selling vol indiscriminately is a coin flip, and
each screen you stack on top moves the odds in your favor.

We measure a short volatility position the simple way: you sell 30-day implied
vol today, and a month later you mark it against where IV ended up. If IV fell,
the short made money. We express that as "vol points captured" = (IV now minus
IV in a month), in vol points.

Then we compare three ways of choosing what to sell:
  1. Sell everything (no screen at all).
  2. Sell only rich vol (IV/HV ratio in the top 25% of names, so implied is well
     above realized and you are actually being paid).
  3. Sell rich vol that is also stretched high in its own range (IV rank >= 70).

The point is that the edge stacks. Each filter is one number from one feed.

What it does:
  1. Pull /iv-rank (for iv and iv_rank) and /iv-hv-premium (for the IV/HV ratio).
  2. Merge them, then look 21 trading days ahead to get the vol points captured.
  3. Average the captured vol under each of the three screens.
  4. Print the three numbers and save a bar chart.

Output: a printed summary and "stacked_filter_edge.png" next to this script.
"""

import requests
import pandas as pd
import matplotlib.pyplot as plt

# Paste your Alphanume API key here. Grab a free one at https://www.alphanume.com/
API_KEY = "alp_your_key_here"

BASE = "https://api.alphanume.com/v1"
HORIZON_DAYS = 21   # one trading month forward

TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "AVGO", "NFLX",
    "INTC", "MU", "QCOM", "MRVL", "CRM", "ORCL", "ADBE", "CSCO", "TXN", "PYPL",
    "JPM", "BAC", "GS", "WFC", "C", "XOM", "CVX", "BA", "CAT", "GE",
    "DIS", "KO", "PEP", "WMT", "COST", "HD", "NKE", "PFE", "MRNA", "UNH",
]

# 1. Pull the two feeds we need, one ticker at a time, into two tables.
rank_rows = []
prem_rows = []
for ticker in TICKERS:
    rank_rows += requests.get(
        BASE + "/iv-rank",
        params={"ticker": ticker, "only_final": "true", "api_key": API_KEY},
    ).json()["data"]
    prem_rows += requests.get(
        BASE + "/iv-hv-premium",
        params={"ticker": ticker, "only_final": "true", "api_key": API_KEY},
    ).json()["data"]
    print("pulled", ticker)

rank = pd.DataFrame(rank_rows)[["ticker", "date", "iv", "iv_rank"]]
prem = pd.DataFrame(prem_rows)[["ticker", "date", "iv_hv_ratio"]]

# 2. Merge the feeds, then look one month ahead to get the vol points captured.
df = rank.merge(prem, on=["ticker", "date"]).sort_values(["ticker", "date"])
df["iv_future"] = df.groupby("ticker")["iv"].shift(-HORIZON_DAYS)
df["vol_points_captured"] = (df["iv"] - df["iv_future"]) * 100
df = df.dropna(subset=["vol_points_captured"])

# 3. Apply the three screens and average the captured vol under each.
rich_cutoff = df["iv_hv_ratio"].quantile(0.75)   # the top 25% richest names
sell_everything = df["vol_points_captured"]
rich_only = df[df["iv_hv_ratio"] >= rich_cutoff]["vol_points_captured"]
rich_and_stretched = df[
    (df["iv_hv_ratio"] >= rich_cutoff) & (df["iv_rank"] >= 70)
]["vol_points_captured"]

labels = ["Sell everything", "Rich vol only", "Rich + high IV rank"]
values = [sell_everything.mean(), rich_only.mean(), rich_and_stretched.mean()]

print("\nAverage vol points captured, by how you screen")
for label, value in zip(labels, values):
    print(f"  {label:22s} {value:+.2f}")

# 4. Plot the ladder. The fully screened bar gets the accent color.
colors = ["#9AA5AD", "#9AA5AD", "#E8603C"]
plt.figure(figsize=(9, 5))
bars = plt.bar(labels, values, color=colors, width=0.6)
plt.axhline(0, color="black", linewidth=1)
plt.title("Stack the filters, stack the edge", fontsize=14, fontweight="bold")
plt.ylabel("Avg vol points captured on the short")
for bar, value in zip(bars, values):
    plt.text(bar.get_x() + bar.get_width() / 2, value,
             f"{value:+.1f}", ha="center",
             va="bottom" if value >= 0 else "top", fontweight="bold")
plt.tight_layout()
plt.savefig("stacked_filter_edge.png", dpi=150)
print("\nsaved stacked_filter_edge.png")
