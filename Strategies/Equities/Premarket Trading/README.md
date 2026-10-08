# Pre-Market Quantitative Trading on TradeZero

Every morning, a handful of beaten-down small caps rip in pre-market on a press release, a reverse split, or just noise, and a lot of them give it back once the regular session opens. [Alphanume](https://www.alphanume.com/)'s [Pre-Market Drop Risk](https://www.alphanume.com/premarket-drop-risk) model ranks those names by their odds of falling 5% or more from the open to the close. The trade shorts that basket into the opening auction and covers at 14:00 ET, so there's no overnight borrow, only a one-time locate fee on hard-to-borrow names.

`production.py` is a trimmed-down version of the bot we run live on TradeZero. It sizes the basket, buys locates (skipping any over 5% of the position), sends market-on-open short sales, and covers in the afternoon with limit orders that step up 1% every 30 seconds.

**Endpoints:** `premarket-drop-risk` (Alphanume, [Pro](https://www.alphanume.com/pricing)). TradeZero's trading API for locates, orders, and positions. No price vendor needed: the basket carries the pre-market price for sizing, and the cover prices come from TradeZero's own P&L feed.

**Risk:** `backtest.py` is gross of locate fees and slippage, and it includes October 15, 2024, when DRUG ran +1,369% open to close. At this bot's sizing, that one day would have cost roughly 80% of the account. There's no stop. Start small.

## Run it
1. `pip install requests pandas matplotlib pytz`
2. Paste your [Alphanume Pro](https://www.alphanume.com/pricing) key into `API_KEY` in `backtest.py`, and your Alphanume key plus TradeZero key ID and secret into the top of `production.py`.
3. `python backtest.py`: prints the summary and worst days, and saves `premarket_drop_risk_backtest.png`.
4. `python production.py check`: read-only. Prints your TradeZero account and today's basket so you know both keys work.
5. Schedule the live bot (times in ET, e.g. on a small Linux server with its clock set to `America/New_York`):
   ```
   5 9 * * 1-5  cd /path/to/folder && python production.py entry >> bot.log 2>&1
   0 14 * * 1-5 cd /path/to/folder && python production.py exit  >> bot.log 2>&1
   ```

Want to build on other signals? Browse the rest of [Alphanume's datasets](https://www.alphanume.com/datasets).

Getting TradeZero API keys: [developer.tradezero.com](https://developer.tradezero.com/docs/documentation/api-keys). Paper accounts treat every stock as easy to borrow, so they never exercise the locate step. The `exit` job covers every short in the account, so run the bot on an account dedicated to it.

_Not investment advice. Not a signal service. A reference implementation for API-based research._
