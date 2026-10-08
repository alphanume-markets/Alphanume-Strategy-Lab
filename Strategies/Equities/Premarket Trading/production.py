"""
Shorting Pre-Market Pumps on TradeZero — live bot
=================================================

Every morning, Alphanume's Pre-Market Drop Risk model ranks the small caps that ran
hard before the bell by their odds of falling 5%+ from the open to the close. This
script shorts that basket into the opening auction on TradeZero and buys it back at
14:00 ET. Schedule it with cron: `entry` at 09:05 ET, `exit` at 14:00 ET.

What it does:
  check  Prints your TradeZero account and today's basket. Read-only.
  entry  1. Waits for today's basket (rows publish around 09:03 ET).
         2. Sizes each name: 30% of equity split across the basket, max 10% per name.
         3. Buys a locate for hard-to-borrow names, skipping any where the fee is over 5% of the position.
         4. Sends a market-on-open short sale for each name.
  exit   Covers every short with a limit order 1% above the last price, re-sent 1% higher
         every 30 seconds, for up to 10 rounds.

Assumes the TradeZero account only runs this bot: `exit` covers every short in the account.
"""

import math
import sys
import time
from datetime import datetime

import pytz
import requests

# Paste your keys here. Alphanume Pre-Market Drop Risk needs a Pro key: https://www.alphanume.com/pricing
ALPHANUME_API_KEY = "alp_your_key_here"
TRADEZERO_API_KEY_ID = "your_tradezero_key_id"
TRADEZERO_API_SECRET_KEY = "your_tradezero_secret"

ALPHANUME_URL = "https://api.alphanume.com/v1/premarket-drop-risk"
TRADEZERO_URL = "https://webapi.tradezero.com/v1/api"
TRADEZERO_HEADERS = {"TZ-API-KEY-ID": TRADEZERO_API_KEY_ID, "TZ-API-SECRET-KEY": TRADEZERO_API_SECRET_KEY}

DAILY_FRACTION_OF_EQUITY = 0.30    # share of the account shorted each day, split across the basket
MAX_FRACTION_PER_NAME = 0.10       # no single name gets more than this share of the account
MAX_LOCATE_COST_FRACTION = 0.05    # skip a name if its locate fee is more than this share of the position
MIN_PRICE = 1                      # skip sub-dollar names

OPENING_AUCTION_ROUTE = "ARCA"     # on our account only ARCA and NYSE offered AtTheOpening orders
COVER_ROUTE = "SMART"


def now_in_new_york():
    return datetime.now(pytz.timezone("America/New_York"))


def get_account():
    accounts = requests.get(f"{TRADEZERO_URL}/accounts", headers=TRADEZERO_HEADERS).json()["accounts"]
    return accounts[0]


def get_basket(date):
    response = requests.get(ALPHANUME_URL, params={"date": date, "min_price": MIN_PRICE, "api_key": ALPHANUME_API_KEY})
    return response.json()["data"]


def buy_locate(account_id, ticker, shares, price):
    locate_shares = math.ceil(shares / 100) * 100
    quote_id = f"{ticker}-{int(time.time())}"

    requests.post(
        f"{TRADEZERO_URL}/accounts/locates/quote",
        headers=TRADEZERO_HEADERS,
        json={"account": account_id, "symbol": ticker, "quantity": locate_shares, "quoteReqID": quote_id},
    )

    offer = None
    for _ in range(10):
        time.sleep(2)
        history = requests.get(f"{TRADEZERO_URL}/accounts/{account_id}/locates/history", headers=TRADEZERO_HEADERS).json()["locateHistory"]
        our_rows = [row for row in history if row["quoteReqID"].startswith(quote_id)]
        offers = [row for row in our_rows if str(row["locateStatus"]) in ("65", "Offered")]
        if offers:
            offer = offers[0]
            break
        if our_rows and all(str(row["locateStatus"]) in ("52", "56", "67", "Canceled", "Rejected", "Expired") for row in our_rows):
            print(f"{ticker}: locate rejected, skipping")
            return False

    if offer is None:
        print(f"{ticker}: no locate offer, skipping")
        requests.delete(f"{TRADEZERO_URL}/accounts/locates/cancel/accounts/{account_id}/quoteReqID/{quote_id}", headers=TRADEZERO_HEADERS)
        return False

    locate_cost = offer["locatePrice"] * locate_shares
    position_value = shares * price
    if locate_cost > MAX_LOCATE_COST_FRACTION * position_value:
        print(f"{ticker}: locate costs ${locate_cost:.2f} on a ${position_value:.2f} position, too expensive")
        requests.delete(f"{TRADEZERO_URL}/accounts/locates/cancel/accounts/{account_id}/quoteReqID/{quote_id}", headers=TRADEZERO_HEADERS)
        return False

    requests.post(
        f"{TRADEZERO_URL}/accounts/locates/accept",
        headers=TRADEZERO_HEADERS,
        json={"accountId": account_id, "quoteReqID": offer["quoteReqID"]},
    )

    for _ in range(5):
        time.sleep(2)
        history = requests.get(f"{TRADEZERO_URL}/accounts/{account_id}/locates/history", headers=TRADEZERO_HEADERS).json()["locateHistory"]
        accepted = [row for row in history if row["quoteReqID"] == offer["quoteReqID"]]
        if accepted and str(accepted[0]["locateStatus"]) in ("50", "Filled"):
            print(f"{ticker}: located {locate_shares} shares for ${locate_cost:.2f}")
            return True

    print(f"{ticker}: locate accepted but never filled, skipping")
    return False


def run_check():
    today = now_in_new_york().strftime("%Y-%m-%d")
    account = get_account()
    print(f"TradeZero account {account['account']} ({account['accountType']}), equity ${account['equity']:,.2f}")
    print(f"Alphanume basket for {today}: {[row['ticker'] for row in get_basket(today)]}")


def run_entry():
    today = now_in_new_york().strftime("%Y-%m-%d")
    account = get_account()
    account_id = account["account"]
    equity = account["equity"]

    # 1. Wait for today's basket. On market holidays it stays empty and the bot gives up at 09:20.
    basket = []
    while not basket and now_in_new_york().strftime("%H:%M") < "09:20":
        basket = get_basket(today)
        if not basket:
            time.sleep(10)

    if not basket:
        print(f"{today}: no names today")
        return

    # 2. Size every name the same, capped per name.
    dollars_per_name = min(DAILY_FRACTION_OF_EQUITY * equity / len(basket), MAX_FRACTION_PER_NAME * equity)
    print(f"{today}: {len(basket)} names, ${dollars_per_name:.2f} each")

    for row in basket:
        ticker = row["ticker"]
        price = row["px_at_trading"]
        shares = math.floor(dollars_per_name / price)
        if shares == 0:
            continue

        # 3. Hard-to-borrow names need a locate first.
        easy_to_borrow = requests.get(
            f"{TRADEZERO_URL}/accounts/{account_id}/is-easy-to-borrow/symbol/{ticker}", headers=TRADEZERO_HEADERS
        ).json()["isEasyToBorrow"]

        if not easy_to_borrow and not buy_locate(account_id, ticker, shares, price):
            continue

        # 4. Short into the opening auction.
        order = {
            "symbol": ticker,
            "securityType": "Stock",
            "side": "Sell",
            "openClose": "Open",
            "orderType": "Market",
            "timeInForce": "AtTheOpening",
            "orderQuantity": shares,
            "route": OPENING_AUCTION_ROUTE,
            "clientOrderId": f"{ticker}-short-{int(time.time())}",
        }
        result = requests.post(f"{TRADEZERO_URL}/accounts/{account_id}/order", headers=TRADEZERO_HEADERS, json=order).json()
        print(f"{ticker}: short {shares} at the open -> {result.get('orderStatus')} {result.get('text') or ''}")


def run_exit():
    account_id = get_account()["account"]

    for attempt in range(1, 11):
        # Cancel any unfilled covers from the last round, then re-read what's still short.
        open_orders = requests.get(f"{TRADEZERO_URL}/accounts/{account_id}/orders", headers=TRADEZERO_HEADERS).json()["orders"]
        for order in open_orders:
            if order["side"] == "Buy" and order["orderStatus"] in ("New", "PartiallyFilled", "PendingNew", "Accepted"):
                requests.delete(f"{TRADEZERO_URL}/accounts/{account_id}/orders/{order['clientOrderId']}", headers=TRADEZERO_HEADERS)
        time.sleep(3)

        positions = requests.get(f"{TRADEZERO_URL}/accounts/{account_id}/positions", headers=TRADEZERO_HEADERS).json()["positions"]
        shorts = {position["symbol"]: abs(int(position["shares"])) for position in positions if position["side"] == "Short"}
        if not shorts:
            print("all shorts covered")
            return

        # TradeZero serves no quotes, so the last price comes from its P&L feed.
        pnl_rows = requests.get(f"{TRADEZERO_URL}/accounts/{account_id}/pnl", headers=TRADEZERO_HEADERS).json()["pnl"]
        last_prices = {row["symbol"]: abs(row["exposure"]) / shorts[row["symbol"]] for row in pnl_rows if row["symbol"] in shorts}

        for ticker, shares in shorts.items():
            if ticker not in last_prices:
                continue
            limit_price = round(last_prices[ticker] * (1 + 0.01 * attempt), 2)
            order = {
                "symbol": ticker,
                "securityType": "Stock",
                "side": "Buy",
                "openClose": "Close",
                "orderType": "Limit",
                "limitPrice": limit_price,
                "timeInForce": "Day",
                "orderQuantity": shares,
                "route": COVER_ROUTE,
                "clientOrderId": f"{ticker}-cover-{int(time.time())}",
            }
            result = requests.post(f"{TRADEZERO_URL}/accounts/{account_id}/order", headers=TRADEZERO_HEADERS, json=order).json()
            print(f"{ticker}: cover {shares} at {limit_price} -> {result.get('orderStatus')}")

        time.sleep(30)

    print("!!! still short after 10 attempts, check the account")


if __name__ == "__main__":
    if sys.argv[1] == "check":
        run_check()
    elif sys.argv[1] == "entry":
        run_entry()
    elif sys.argv[1] == "exit":
        run_exit()
