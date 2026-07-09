"""
Your First Cron Job: A Daily Movers Email — live sender
=======================================================

The same top-movers table as backtest.py, wired up to actually land in your
inbox. Run this file on a schedule and it hits the Alphanume endpoint, formats
the day's names, and sends them to you over SMTP before the open.

Put it on a server that stays awake. On PythonAnywhere (Developer tier), upload
this file, then Tasks -> add a Scheduled Task pointing at it, set to run once a
day at a pre-open UTC time (PythonAnywhere schedules in UTC). See README.md for
the free-tier caveats. On your own always-on box, a crontab line works too:

    0 8 * * 1-5 /usr/bin/python3 /path/to/production.py >> /path/to/movers.log 2>&1

What it does:
  1. Pull today's next-day-movers signal from Alphanume.
  2. Sort by absolute_move and build the top-5 plain-text table.
  3. Send it as an email over SMTP and print a confirmation.

Output: an email in your inbox and a one-line confirmation to stdout (the log).
"""

import requests
import pandas as pd
import smtplib
from email.message import EmailMessage

# Paste your Alphanume API key here. Grab a free one at https://www.alphanume.com/
API_KEY = "alp_your_key_here"

BASE = "https://api.alphanume.com/v1"
TOP_N = 5                                    # how many names to put in the email (a daily slate is about 5)

# Email settings. For Gmail, use an App Password (not your login password) and
# leave the host/port as-is. Other providers: swap in their SMTP host and port.
SMTP_HOST = "smtp.gmail.com"                 # your mail provider's SMTP server
SMTP_PORT = 465                              # 465 for SSL
SMTP_USER = "your_email@gmail.com"           # the account that sends the email
SMTP_PASSWORD = "your_app_password_here"     # an app password, never your login password
EMAIL_TO = "your_email@gmail.com"            # where the watchlist should land

# 1. Pull today's next-day-movers signal and keep the latest date in the feed.
movers_request = requests.get(f"{BASE}/next-day-movers?api_key={API_KEY}").json()
movers_dataset = pd.json_normalize(movers_request["data"])
latest_date = movers_dataset["date"].max()
todays_movers = movers_dataset[movers_dataset["date"] == latest_date].copy()

# 2. Sort by the size of the expected move and build the top-10 table.
top_movers = todays_movers.sort_values("absolute_move", ascending=False, na_position="last").head(TOP_N)
email_body = f"Alphanume next-day movers for {latest_date}\n\n"
email_body += f"{'Ticker':<8}{'Move %':>10}{'Abs Move %':>14}\n"
email_body += "-" * 32 + "\n"
for _, mover in top_movers.iterrows():
    move_pct = "pending" if pd.isna(mover["return"]) else f"{mover['return']:+.2f}"
    abs_move = "pending" if pd.isna(mover["absolute_move"]) else f"{mover['absolute_move']:.2f}"
    email_body += f"{mover['ticker']:<8}{move_pct:>10}{abs_move:>14}\n"

# 3. Send it over SMTP and print a confirmation to the log.
message = EmailMessage()
message["Subject"] = f"Next-Day Movers - {latest_date}"
message["From"] = SMTP_USER
message["To"] = EMAIL_TO
message.set_content(email_body)

with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
    server.login(SMTP_USER, SMTP_PASSWORD)
    server.send_message(message)

print(f"sent {len(top_movers)} movers for {latest_date} to {EMAIL_TO}")
