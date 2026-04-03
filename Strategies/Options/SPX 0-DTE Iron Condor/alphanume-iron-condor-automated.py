# -*- coding: utf-8 -*-
"""
@author: Alphanume Strategy Lab

Automated SPX 0-DTE Iron Condor — Signal to Execution

This script runs the full daily pipeline for an SPX 0-DTE iron condor strategy:

1. Pull the latest S&P 500 risk regime and 0-DTE strike band data from the Alphanume API.
2. Verify that today's trading session data is available.
3. Extract the lower strike, upper strike, and risk regime for the current session.
4. Retrieve the live options chain and map strikes to contract symbols via the broker API (tastytrade).
5. Pull real-time bid/ask quotes for each leg via Massive (formerly Polygon.io).
6. Construct the iron condor spread and compute natural, mid, and optimal limit prices.
7. Validate and submit the order to the exchange via the tastytrade API.

Designed to be scheduled daily (e.g., via PythonAnywhere) for autonomous execution.
"""

import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pytz

from datetime import datetime, timedelta
from pandas_market_calendars import get_calendar # install pandas_market_calendars

# =============================================================================
# Core-Requisites
# =============================================================================

# Replace this placeholder with your own API keys
massive_api_key = "MASSIVE_API_KEY"
alphanume_api_key = "ALPHANUME_API_KEY"

# Load NYSE trading calendar so the script references valid market trading days
calendar = get_calendar("NYSE")

# Build a short recent window of trading dates and use the latest one as "today"
# This avoids weekend / holiday issues when checking whether today's data is available
trading_dates = calendar.schedule(start_date = (datetime.now(pytz.timezone("America/New_York")) - timedelta(days=10)), end_date = (datetime.now(pytz.timezone("America/New_York")))).index.strftime("%Y-%m-%d").values
today = trading_dates[-1]

# Pull S&P 500 risk regime data from Alphanume
risk_regime_request = requests.get(f"https://api.alphanume.com/v1/sp500-risk-regime?api_key={alphanume_api_key}").json()
risk_regime_data = pd.json_normalize(risk_regime_request["data"])

# Pull SPX 0-DTE strike band data from Alphanume
# This dataset provides the lower and upper containment strikes for each session
spx_strike_request = requests.get(f"https://api.alphanume.com/v1/spx-0dte-strike-band?api_key={alphanume_api_key}").json()
spx_strike_data = pd.json_normalize(spx_strike_request["data"])

# Merge strike band data with risk regime data so both are available on the same row per date
strike_and_regime_data = pd.merge(left=spx_strike_data, right=risk_regime_data, on="date")

# Get the full set of dates currently available in the merged dataset
available_dates = strike_and_regime_data["date"].sort_values().values

# Use the most recent available model date
date = available_dates[-1]

# Check whether the latest dataset date matches today's trading date
# If not, the model output for the current session may not have been published yet
if date != today:
    print(f"Data is not yet available for the current trading session. Latest available date: {date} | Current trading date: {today}")
else:
    print(f"Data is up to date for the current trading session: {date}")

# Extract the strike band row corresponding to the selected date
daily_strike_data = strike_and_regime_data[strike_and_regime_data["date"] == date].copy()

# Lower and upper containment strikes from the Alphanume model
lower_strike = daily_strike_data["lower_strike"].iloc[0]
upper_strike = daily_strike_data["upper_strike"].iloc[0]

# Retrieve the market regime for the same date
risk_regime_on_date = daily_strike_data[daily_strike_data["date"] == date].copy()
daily_risk_regime = daily_strike_data["risk_regime"].iloc[0]

# =============================================================================
# Live Trade Output String
# =============================================================================

# Output a simple daily reference string showing the current signal context
# This is intended as a production-style signal summary, not an execution report
print(f"\n{date} | SPX 0-DTE Iron Condor | Regime: {daily_risk_regime} | Short Put Reference: {lower_strike} | Short Call Reference: {upper_strike}")

# =============================================================================
# Tastytrade Integration
# =============================================================================

client_id = "your_client_id"
client_secret = "your_client_secret"

refresh_token = "your_refresh_token"

base_url = 'https://api.tastyworks.com'

access_token_params = {"grant_type": "refresh_token", "refresh_token": refresh_token, "client_secret": client_secret}

access_token_request = requests.post(f"{base_url}/oauth/token", params = access_token_params).json()
access_token = access_token_request["access_token"]

headers = {'Authorization': 'Bearer ' + access_token,'Content-Type': 'application/json'}

# Pull account information and verify balance

accounts = requests.get(f"{base_url}/customers/me/accounts", headers = headers).json()
account_number = accounts["data"]["items"][0]["account"]["account-number"]

balances = requests.get(f"{base_url}/accounts/{account_number}/balances", headers = headers).json()["data"]

option_buying_power = np.float64(balances["derivative-buying-power"])
print(f"Buying Power: ${option_buying_power}")

# =============================================================================
# Pulling the options chain via Tastytrade    
# =============================================================================

option_url = f"https://api.tastyworks.com/option-chains/SPXW/nested"

option_chain = pd.json_normalize(requests.get(option_url,  headers = headers).json()["data"]["items"][0]["expirations"][0]["strikes"])
option_chain["strike_price"] = option_chain["strike-price"].astype(float)

short_put_option = option_chain[option_chain["strike_price"] == lower_strike].copy()
long_put_option = option_chain[option_chain["strike_price"] == (lower_strike-5)].copy()

short_call_option = option_chain[option_chain["strike_price"] == upper_strike].copy()
long_call_option = option_chain[option_chain["strike_price"] == (upper_strike+5)].copy()

short_put_ticker = short_put_option["put"].iloc[0]
long_put_ticker = long_put_option["put"].iloc[0]

short_call_ticker = short_call_option["call"].iloc[0]
long_call_ticker = long_call_option["call"].iloc[0]

# =============================================================================
# Pulling the options chain via Massive
# =============================================================================

puts = pd.json_normalize(requests.get(f"https://api.massive.com/v3/reference/options/contracts?underlying_ticker=SPX&contract_type=put&as_of={date}&expiration_date={date}&limit=1000&apiKey={massive_api_key}").json()["results"])
puts = puts[puts["ticker"].str.contains("SPXW")].copy()

short_put = puts[puts["strike_price"] == lower_strike].copy()
long_put = puts[puts["strike_price"] == (lower_strike-5)].copy()

calls = pd.json_normalize(requests.get(f"https://api.massive.com/v3/reference/options/contracts?underlying_ticker=SPX&contract_type=call&as_of={date}&expiration_date={date}&limit=1000&apiKey={massive_api_key}").json()["results"])
calls = calls[calls["ticker"].str.contains("SPXW")].copy()

short_call = calls[calls["strike_price"] == upper_strike].copy()
long_call = calls[calls["strike_price"] == (upper_strike+5)].copy()

# =============================================================================
# Get most recent bid/ask
# =============================================================================

short_put_quote = pd.json_normalize(requests.get(f"https://api.massive.com/v3/quotes/{short_put['ticker'].iloc[0]}?&sort=timestamp&order=desc&limit=10&apiKey={massive_api_key}").json()["results"]).set_index("sip_timestamp").sort_index().tail(1)
short_put_quote.index = pd.to_datetime(short_put_quote.index, unit = "ns", utc = True).tz_convert("America/New_York")
short_put_quote["mid_price"] = round((short_put_quote["bid_price"] + short_put_quote["ask_price"]) / 2, 2)

long_put_quote = pd.json_normalize(requests.get(f"https://api.massive.com/v3/quotes/{long_put['ticker'].iloc[0]}?&sort=timestamp&order=desc&limit=10&apiKey={massive_api_key}").json()["results"]).set_index("sip_timestamp").sort_index().tail(1)
long_put_quote.index = pd.to_datetime(long_put_quote.index, unit = "ns", utc = True).tz_convert("America/New_York")
long_put_quote["mid_price"] = round((long_put_quote["bid_price"] + long_put_quote["ask_price"]) / 2, 2)

short_call_quote = pd.json_normalize(requests.get(f"https://api.massive.com/v3/quotes/{short_call['ticker'].iloc[0]}?&sort=timestamp&order=desc&limit=10&apiKey={massive_api_key}").json()["results"]).set_index("sip_timestamp").sort_index().tail(1)
short_call_quote.index = pd.to_datetime(short_call_quote.index, unit = "ns", utc = True).tz_convert("America/New_York")
short_call_quote["mid_price"] = round((short_call_quote["bid_price"] + short_call_quote["ask_price"]) / 2, 2)

long_call_quote = pd.json_normalize(requests.get(f"https://api.massive.com/v3/quotes/{long_call['ticker'].iloc[0]}?&sort=timestamp&order=desc&limit=10&apiKey={massive_api_key}").json()["results"]).set_index("sip_timestamp").sort_index().tail(1)
long_call_quote.index = pd.to_datetime(long_call_quote.index, unit = "ns", utc = True).tz_convert("America/New_York")
long_call_quote["mid_price"] = round((long_call_quote["bid_price"] + long_call_quote["ask_price"]) / 2, 2)

# =============================================================================
# Format into the iron condor spread
# =============================================================================

spread = pd.concat([short_put_quote.reset_index().add_prefix("short_put_"), long_put_quote.reset_index().add_prefix("long_put_"),
                    short_call_quote.reset_index().add_prefix("short_call_"), long_call_quote.reset_index().add_prefix("long_call_")], axis = 1)#.dropna()

natural_price = round((spread["short_put_bid_price"].iloc[0] - spread["long_put_ask_price"].iloc[0]) + (spread["short_call_bid_price"].iloc[0] - spread["long_call_ask_price"].iloc[0]), 2)
mid_price = round((spread["short_put_mid_price"].iloc[0] - spread["long_put_mid_price"].iloc[0]) + (spread["short_call_mid_price"].iloc[0] - spread["long_call_mid_price"].iloc[0]), 2)

optimal_price = round(np.int64(round((mid_price - .05) / .05, 2)) * .05, 2)

order_details = {
    "time-in-force": "Day",
    "order-type": "Limit",
    "price": optimal_price,
    "price-effect": "Credit",
    "legs": [{"action": "Buy to Open",
          "instrument-type": "Equity Option",
          "symbol": f"{long_put_ticker}",
          "quantity": 1},
        
          {"action": "Sell to Open",
          "instrument-type": "Equity Option",
          "symbol": f"{short_put_ticker}",
          "quantity": 1},
          
          {"action": "Buy to Open",
          "instrument-type": "Equity Option",
          "symbol": f"{long_call_ticker}",
          "quantity": 1},
          
          {"action": "Sell to Open",
          "instrument-type": "Equity Option",
          "symbol": f"{short_call_ticker}",
          "quantity": 1}]
    
                }

# Do an order dry-run to make sure the trade will go through (i.e., verifies balance, valid symbol, etc. )

validate_order = requests.post(f"https://api.tastyworks.com/accounts/{account_number}/orders/dry-run", json = order_details, headers = headers)
validation_text = validate_order.text
print(validation_text)

submit_order = requests.post(f"{base_url}/accounts/{account_number}/orders", json = order_details, headers = headers)
order_submission_text = submit_order.text
