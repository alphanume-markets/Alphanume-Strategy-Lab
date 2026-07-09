# Your First Cron Job: A Daily Movers Email

A signal you have to remember to check is a signal you will forget. This tutorial turns one Alphanume endpoint into an automated morning email: it pulls the latest `next-day-movers` slate, ranks it by the size of the expected move, formats the day's names into a plain-text table, and sends it to your inbox on a daily schedule before the open.

**Endpoints:** `next-day-movers` (Alphanume). No price vendor needed.

**Data:** `next-day-movers` is on the Free tier (30-day delayed), so the whole tutorial runs on a free key. The list refreshes daily at 3:30 PM ET; `return` and `absolute_move` are `null` on the newest date until the next session closes.

## Run it
1. `pip install requests pandas`
2. Paste your Alphanume key (free at https://www.alphanume.com/) into `API_KEY` in both files.
3. `python backtest.py` — prints the top-movers table so you can see the exact email body before sending anything.
4. Fill in the SMTP settings at the top of `production.py`. For Gmail, use an [App Password](https://myaccount.google.com/apppasswords) (2-Step Verification must be on), never your login password. The code defaults to Gmail over SSL (`smtp.gmail.com:465`). For Outlook (`smtp-mail.outlook.com:587`) or Zoho (`smtp.zoho.com:587`), swap `smtplib.SMTP_SSL(...)` for `smtplib.SMTP(...)` plus a `server.starttls()` call before `login`.
5. `python production.py` — sends the table to your inbox once, so you can confirm it works.

## Schedule it
Run it on a server that stays awake so the email fires every morning on its own. [PythonAnywhere](https://www.pythonanywhere.com/) is the gentlest on-ramp:

1. Upload `production.py` and paste in your Alphanume key and app password.
2. Create a **Scheduled Task** (Tasks tab) pointing at the file, set to run once a day.
3. Pick the time in **UTC** (that's how PythonAnywhere schedules) and choose a pre-open slot, e.g. before 9:30 AM ET.

This needs the paid **Developer tier ($10/month)**. As of 2026 the free tier will not run it: new free accounts get no scheduled tasks (moved to Developer in Jan 2026), free accounts can't reach `api.alphanume.com` (allowlist only), and free accounts can only SMTP through Gmail. The Developer tier clears all three (20 daily tasks, unrestricted outbound, any SMTP provider).

On your own always-on box, a crontab line works too:

```
0 8 * * 1-5 /usr/bin/python3 /path/to/production.py >> /path/to/movers.log 2>&1
```

The `>> movers.log 2>&1` appends the confirmation line (and any errors) to a log so you can confirm it fired.

_Not investment advice. Not a signal service. A reference implementation for API-based research._
