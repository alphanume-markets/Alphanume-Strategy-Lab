# Do Dividend-Capture Strategies Actually Work?

Dividend capture is a coin flip if you take every name, because plenty of stocks drop by more than the dividend on the ex-date and never recover. The money is in the names that give back *less* than they pay and snap back fast. You only know a name behaves that way from its past ex-dates, so the screen is point-in-time: each event is judged on that ticker's prior history alone (trailing 5-day recovery rate and average drop ratio), then measured on what it actually paid. That keeps the backtest honest and tradeable instead of scoring events on outcomes you couldn't have known on the ex-date.

**Endpoints:** `dividend-capture` (Alphanume). No price vendor needed — the endpoint carries the ex-day give-back, recovery flags, and the forward calendar directly.

**Data:** `backtest.py` defaults to a rolling ~28-day window so it runs on a free key. On the Free tier's short window the descriptive quadrant (the figure and the headline print) is fully populated, but the point-in-time screened book is thin — a month rarely gives any name the 4+ prior ex-dates the screen needs. Raise `LOOKBACK_DAYS` with a Pro key to build the full point-in-time books and reproduce the post's numbers. The `production.py` forward calendar uses `upcoming=true`, which bypasses the Free-tier delay, so the live watchlist works on a free key too.

## Run it
1. `pip install requests pandas matplotlib`
2. Paste your Alphanume key (free at https://www.alphanume.com/) into `API_KEY` in both files.
3. `python backtest.py` — prints the point-in-time screened-vs-unscreened summary and saves `dividend_capture_fast_recovery.png`.
4. `python production.py` — writes `dividend_capture_watchlist_<date>.csv`, the upcoming ex-dates worth trading.

_Not investment advice. Not a signal service. A reference implementation for API-based research._
