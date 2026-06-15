"""
Vol-of-vol and the quality of the ride
======================================

The third idea from the post: vol-of-vol tells you how clean the reversion will
be once you are in the trade.

Vol-of-vol measures how unstable a name's volatility is (how much its IV wobbles
around over the last month). Here we take the exact same short you would actually
put on, the rich and stretched names (IV/HV ratio above 1 and IV rank >= 70), and
split them into two halves by vol-of-vol: the steadiest half and the most unstable
half. Then we look at how the trade paid out a month later.

Steady-vol names give a tight, predictable distribution of outcomes. Unstable-vol
names pay more on average, and win more often, but the spread of outcomes is much
wider. So vol-of-vol is a sizing dial: it tells you how bumpy the ride will be.

What it does:
  1. Pull /iv-rank, /iv-hv-premium, and /vol-of-vol for each ticker and merge them.
  2. Keep only the rich, stretched shorts (the trades you would take).
  3. Split them at the median vol-of-vol into a steady half and an unstable half.
  4. Print win rate, average, and spread for each half, and draw two histograms.

Output: a printed summary and "vol_of_vol_ride_quality.png" next to this script.
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

# 1. Pull the three feeds we need, one ticker at a time, into three tables.
rank_rows = []
prem_rows = []
vov_rows = []
for ticker in TICKERS:
    rank_rows += requests.get(
        BASE + "/iv-rank",
        params={"ticker": ticker, "only_final": "true", "api_key": API_KEY},
    ).json()["data"]
    prem_rows += requests.get(
        BASE + "/iv-hv-premium",
        params={"ticker": ticker, "only_final": "true", "api_key": API_KEY},
    ).json()["data"]
    vov_rows += requests.get(
        BASE + "/vol-of-vol",
        params={"ticker": ticker, "only_final": "true", "api_key": API_KEY},
    ).json()["data"]
    print("pulled", ticker)

rank = pd.DataFrame(rank_rows)[["ticker", "date", "iv", "iv_rank"]]
prem = pd.DataFrame(prem_rows)[["ticker", "date", "iv_hv_ratio"]]
vov = pd.DataFrame(vov_rows)[["ticker", "date", "iv_vov"]]

# 2. Merge, look one month ahead, and keep only the rich, stretched shorts.
df = rank.merge(prem, on=["ticker", "date"]).merge(vov, on=["ticker", "date"])
df = df.sort_values(["ticker", "date"])
df["iv_future"] = df.groupby("ticker")["iv"].shift(-HORIZON_DAYS)
df["vol_points_captured"] = (df["iv"] - df["iv_future"]) * 100
df = df.dropna(subset=["vol_points_captured"])
df = df[(df["iv_rank"] >= 70) & (df["iv_hv_ratio"] >= 1.0)]

# 3. Split the trades into a steady half and an unstable half by vol-of-vol.
median_vov = df["iv_vov"].median()
steady = df[df["iv_vov"] <= median_vov]["vol_points_captured"]
unstable = df[df["iv_vov"] > median_vov]["vol_points_captured"]

print("\nThe same short, split by vol-of-vol")
for name, series in [("Steady vol ", steady), ("Unstable vol", unstable)]:
    win_rate = (series > 0).mean() * 100
    print(f"  {name}: win rate {win_rate:5.1f}%   "
          f"avg {series.mean():+5.2f}   spread (std) {series.std():5.2f}   n={len(series)}")

# 4. Draw the two outcome distributions on the same axis.
plt.figure(figsize=(9, 5))
plt.hist(unstable, bins=40, range=(-30, 60), density=True,
         color="#E8603C", alpha=0.55, label="Unstable vol")
plt.hist(steady, bins=40, range=(-30, 60), density=True,
         color="#2F6F8F", alpha=0.80, label="Steady vol")
plt.axvline(0, color="black", linewidth=1, linestyle="--")
plt.title("Vol-of-vol tells you how clean the reversion will be",
          fontsize=14, fontweight="bold")
plt.xlabel("Vol points captured on the short (per trade)")
plt.ylabel("Share of trades")
plt.legend()
plt.tight_layout()
plt.savefig("vol_of_vol_ride_quality.png", dpi=150)
print("\nsaved vol_of_vol_ride_quality.png")
