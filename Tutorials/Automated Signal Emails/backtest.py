"""
Your First Cron Job: A Daily Movers Email
==========================================

A signal you have to remember to check is a signal you will forget. This is the
first half of turning one Alphanume endpoint into an automated morning email:
pull the latest next-day-movers list, rank it by the size of the expected move,
and format the top names into a plain-text table you can read at a glance. Run
this locally first to see exactly what the email body will look like before you
wire up sending in production.py.

What it does:
  1. Pull next-day-movers from Alphanume.
  2. Keep the latest date in the feed (today's watchlist).
  3. Sort by absolute_move and take the top 5 names.
  4. Format them into a plain-text table and print it as the email body.

Output: prints the top-movers table to stdout (the same text production.py emails).
"""

import requests
import pandas as pd

# Paste your Alphanume API key here. Grab a free one at https://www.alphanume.com/
API_KEY = "alp_your_key_here"

BASE = "https://api.alphanume.com/v1"
TOP_N = 5                      # how many names to put in the email (a daily slate is about 5)

# 1. Pull the next-day-movers feed from Alphanume.
movers_request = requests.get(f"{BASE}/next-day-movers?api_key={API_KEY}").json()
movers_dataset = pd.json_normalize(movers_request["data"])

# 2. Keep the latest date in the feed. That is the freshest watchlist. On the
#    newest date, return/absolute_move are null until the next session closes.
latest_date = movers_dataset["date"].max()
todays_movers = movers_dataset[movers_dataset["date"] == latest_date].copy()

# 3. Rank by the size of the expected move and take the top names.
todays_movers = todays_movers.sort_values("absolute_move", ascending=False, na_position="last")
top_movers = todays_movers.head(TOP_N)

# 4. Format the top names into a plain-text table and print it as the email body.
email_body = f"Alphanume next-day movers for {latest_date}\n\n"
email_body += f"{'Ticker':<8}{'Move %':>10}{'Abs Move %':>14}\n"
email_body += "-" * 32 + "\n"
for _, mover in top_movers.iterrows():
    move_pct = "pending" if pd.isna(mover["return"]) else f"{mover['return']:+.2f}"
    abs_move = "pending" if pd.isna(mover["absolute_move"]) else f"{mover['absolute_move']:.2f}"
    email_body += f"{mover['ticker']:<8}{move_pct:>10}{abs_move:>14}\n"

print(email_body)
