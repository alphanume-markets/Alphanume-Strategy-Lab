# -*- coding: utf-8 -*-
"""
@author: Alphanume Strategy Lab

This script demonstrates a simple historical backtest of an SPX 0-DTE iron condor strategy.

High-level workflow:
1. Pull "smart strike" bands for SPX 0-DTE from the Alphanume API.
2. Pull daily S&P 500 risk regime data from the Alphanume API.
3. For each trading day:
   - Identify out-of-the-money put and call spreads outside the strike band.
   - Estimate entry prices using midpoints of option quotes around the chosen trade time.
   - Hold the position until expiration (same day).
   - Calculate PnL using the SPX closing price.
4. Aggregate results and plot the resulting equity curve.
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

# Replace these placeholders with your own API keys
massive_api_key = "MASSIVE_API_KEY"
alphanume_api_key = "ALPHANUME_API_KEY"

# Load NYSE trading calendar so we only work with valid market trading days
calendar = get_calendar("NYSE")

# Generate a full list of trading days (useful reference range)
all_trading_dates = calendar.schedule(start_date = "2001-01-01", end_date = datetime.now(pytz.timezone("America/New_York"))+timedelta(days=30)).index.strftime("%Y-%m-%d").values

# Backtest window — trading days from 2024 onward
trading_dates = calendar.schedule(start_date = "2024-01-01", end_date = (datetime.now(pytz.timezone("America/New_York"))-timedelta(days=1))).index.strftime("%Y-%m-%d").values

# Pull S&P 500 risk regime data from Alphanume
risk_regime_request = requests.get(f"https://api.alphanume.com/v1/sp500-risk-regime?api_key={alphanume_api_key}").json()
risk_regime_data = pd.json_normalize(risk_regime_request["data"])

# Pull daily SPX 0-DTE strike band data from Alphanume
# This provides the lower and upper strike levels used to construct spreads
spx_strike_request = requests.get(f"https://api.alphanume.com/v1/spx-0dte-strike-band?api_key={alphanume_api_key}").json()
spx_strike_data = pd.json_normalize(spx_strike_request["data"])

# Merge strike band data with risk regime data so both are available per date
strike_and_regime_data = pd.merge(left=spx_strike_data, right=risk_regime_data, on="date")

# Overwrite trading_dates with only dates available in the merged dataset
trading_dates = strike_and_regime_data["date"].sort_values().values

# =========================================================================================================

# Underlying index ticker used for end-of-day SPX data
ticker = "I:SPX"

# Root ticker used when requesting SPX option contracts
options_ticker = "SPX"

# Time of day when the strategy enters the trade
trade_time = "10:30"

# Distance between short and long strike legs in number of strikes
spread_width = 1

# Store results for each daily trade
trade_list = []

# Track runtime duration per iteration (used for ETA estimates)
times = []

# Create a persistent HTTP session for efficiency across many API calls
# This prevents opening a new connection for every request
connection_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=500)
connection_session.mount('https://', adapter)

# date = trading_dates[-5] # np.where(trading_dates==date)
for date in trading_dates:

    try:

        start_time = datetime.now()
        
        # Extract the strike band row corresponding to the current trading day
        daily_strike_data = strike_and_regime_data[strike_and_regime_data["date"] == date].copy()
        
        # Lower and upper containment strikes from the Alphanume model
        lower_strike = daily_strike_data["lower_strike"].iloc[0]
        upper_strike = daily_strike_data["upper_strike"].iloc[0]
        
        # Since this is a 0-DTE strategy, expiration date is the same day
        exp_date = date

        # Build the timestamp representing the trade entry time
        minute_timestamp = (pd.to_datetime(date).tz_localize("America/New_York") + timedelta(hours = pd.Timestamp(trade_time).time().hour, minutes = pd.Timestamp(trade_time).time().minute))

        # Convert timestamps into nanoseconds for Polygon quote filtering
        quote_timestamp = minute_timestamp.value
        close_timestamp = (pd.to_datetime(date).tz_localize("America/New_York") + timedelta(hours = 16, minutes = 0)).value
        
        # Put Spread

        # Pull all SPX put option contracts expiring on the current date
        valid_puts = pd.json_normalize(connection_session.get(f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={options_ticker}&contract_type=put&as_of={date}&expiration_date={exp_date}&limit=1000&apiKey={massive_api_key}").json()["results"])

        # Restrict to SPXW contracts (weekly-style SPX options used for 0-DTE trading)
        valid_puts = valid_puts[valid_puts["ticker"].str.contains("SPXW")].copy()

        # Select out-of-the-money puts below the model's lower strike
        otm_puts = valid_puts[valid_puts["strike_price"] <= lower_strike].sort_values("strike_price", ascending = False)

        # Short the nearest OTM put and hedge with the next strike lower
        short_put = otm_puts.iloc[[0]]
        long_put = otm_puts.iloc[[spread_width]]

        short_put_strike = short_put["strike_price"].iloc[0]
        long_put_strike = long_put["strike_price"].iloc[0]

        # Pull quote data for the short put from entry time until close
        short_put_quotes = pd.json_normalize(connection_session.get(f"https://api.polygon.io/v3/quotes/{short_put['ticker'].iloc[0]}?timestamp.gte={quote_timestamp}&timestamp.lt={close_timestamp}&order=asc&limit=5000&sort=timestamp&apiKey={massive_api_key}").json()["results"]).set_index("sip_timestamp")

        # Convert nanosecond timestamps into New York time
        short_put_quotes.index = pd.to_datetime(short_put_quotes.index, unit = "ns", utc = True).tz_convert("America/New_York")

        # Estimate fill price using midpoint between bid and ask
        short_put_quotes["mid_price"] = round((short_put_quotes["bid_price"] + short_put_quotes["ask_price"]) / 2, 2)

        # Keep only quotes occurring before or at the trade entry minute
        short_put_quotes = short_put_quotes[short_put_quotes.index.strftime("%Y-%m-%d %H:%M") <= minute_timestamp.strftime("%Y-%m-%d %H:%M")].copy()

        # Use median of quotes around that minute as robust entry estimate
        short_put_quote = short_put_quotes.median(numeric_only=True).to_frame().copy().T
        short_put_quote["t"] = minute_timestamp.strftime("%Y-%m-%d %H:%M")

        # Repeat the same process for the long put hedge leg
        long_put_quotes = pd.json_normalize(connection_session.get(f"https://api.polygon.io/v3/quotes/{long_put['ticker'].iloc[0]}?timestamp.gte={quote_timestamp}&timestamp.lt={close_timestamp}&order=asc&limit=5000&sort=timestamp&apiKey={massive_api_key}").json()["results"]).set_index("sip_timestamp")
        long_put_quotes.index = pd.to_datetime(long_put_quotes.index, unit = "ns", utc = True).tz_convert("America/New_York")
        long_put_quotes["mid_price"] = round((long_put_quotes["bid_price"] + long_put_quotes["ask_price"]) / 2, 2)
        long_put_quotes = long_put_quotes[long_put_quotes.index.strftime("%Y-%m-%d %H:%M") <= minute_timestamp.strftime("%Y-%m-%d %H:%M")].copy()

        long_put_quote = long_put_quotes.median(numeric_only=True).to_frame().copy().T
        long_put_quote["t"] = minute_timestamp.strftime("%Y-%m-%d %H:%M")
                   
        # Call Spread
        
        # Pull all SPX call option contracts expiring on the current date
        valid_calls = pd.json_normalize(connection_session.get(f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={options_ticker}&contract_type=call&as_of={date}&expiration_date={exp_date}&limit=1000&apiKey={massive_api_key}").json()["results"])
        valid_calls = valid_calls[valid_calls["ticker"].str.contains("SPXW")].copy()
        
        # Select out-of-the-money calls above the model's upper strike
        otm_calls = valid_calls[valid_calls["strike_price"] >= upper_strike].sort_values("strike_price", ascending = True)
        
        # Short the nearest OTM call and hedge with the next strike higher
        short_call = otm_calls.iloc[[0]]
        long_call = otm_calls.iloc[[spread_width]]
        
        short_call_strike = short_call["strike_price"].iloc[0]
        long_call_strike = long_call["strike_price"].iloc[0]
        
        short_call_ticker = short_call["ticker"].iloc[0]
        long_call_ticker  = long_call["ticker"].iloc[0]
        
        # Retrieve quote data for short call
        short_call_quotes = pd.json_normalize(connection_session.get(f"https://api.polygon.io/v3/quotes/{short_call['ticker'].iloc[0]}?timestamp.gte={quote_timestamp}&timestamp.lt={close_timestamp}&order=asc&limit=5000&sort=timestamp&apiKey={massive_api_key}").json()["results"]).set_index("sip_timestamp")
        short_call_quotes.index = pd.to_datetime(short_call_quotes.index, unit = "ns", utc = True).tz_convert("America/New_York")
        short_call_quotes["mid_price"] = round((short_call_quotes["bid_price"] + short_call_quotes["ask_price"]) / 2, 2)
        short_call_quotes = short_call_quotes[short_call_quotes.index.strftime("%Y-%m-%d %H:%M") <= minute_timestamp.strftime("%Y-%m-%d %H:%M")].copy()
        
        short_call_quote = short_call_quotes.median(numeric_only=True).to_frame().copy().T
        short_call_quote["t"] = minute_timestamp.strftime("%Y-%m-%d %H:%M")
        
        # Retrieve quote data for long call hedge
        long_call_quotes = pd.json_normalize(connection_session.get(f"https://api.polygon.io/v3/quotes/{long_call['ticker'].iloc[0]}?timestamp.gte={quote_timestamp}&timestamp.lt={close_timestamp}&order=asc&limit=5000&sort=timestamp&apiKey={massive_api_key}").json()["results"]).set_index("sip_timestamp")
        long_call_quotes.index = pd.to_datetime(long_call_quotes.index, unit = "ns", utc = True).tz_convert("America/New_York")
        long_call_quotes["mid_price"] = round((long_call_quotes["bid_price"] + long_call_quotes["ask_price"]) / 2, 2)
        long_call_quotes = long_call_quotes[long_call_quotes.index.strftime("%Y-%m-%d %H:%M") <= minute_timestamp.strftime("%Y-%m-%d %H:%M")].copy()
        
        long_call_quote = long_call_quotes.median(numeric_only=True).to_frame().copy().T
        long_call_quote["t"] = minute_timestamp.strftime("%Y-%m-%d %H:%M")

        # Combine put spread and call spread into a single iron condor record
        spread = pd.concat([short_put_quote.add_prefix("short_put_"), long_put_quote.add_prefix("long_put_"),
                            short_call_quote.add_prefix("short_call_"), long_call_quote.add_prefix("long_call_")], axis = 1).dropna()

        # Total credit collected from both spreads
        spread["spread_value"] = (spread["short_put_mid_price"] - spread["long_put_mid_price"]) + (spread["short_call_mid_price"] - spread["long_call_mid_price"])
        
        
        # Credit collected from each side
        put_cost = (spread["short_put_mid_price"].iloc[0] - spread["long_put_mid_price"].iloc[0])
        call_cost = (spread["short_call_mid_price"].iloc[0] - spread["long_call_mid_price"].iloc[0])

        # Total credit received when selling the iron condor
        cost = spread["spread_value"].iloc[0]
        
        # Max loss calculations
        put_max_loss = abs(short_put["strike_price"].iloc[0] - long_put["strike_price"].iloc[0]) - put_cost
        call_max_loss = abs(short_call["strike_price"].iloc[0] - long_call["strike_price"].iloc[0]) - call_cost
        max_loss = np.maximum(abs(short_put["strike_price"].iloc[0] - long_put["strike_price"].iloc[0]), abs(short_call["strike_price"].iloc[0] - long_call["strike_price"].iloc[0])) - cost
        
        # Pull SPX closing value for the day
        eod_underlying_data = pd.json_normalize(connection_session.get(f"https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{date}/{date}?sort=asc&apiKey={massive_api_key}").json()["results"])
        closing_value = eod_underlying_data["c"].iloc[0]

        # Intrinsic value of the short legs at expiration
        put_intrinsic  = np.maximum(short_put_strike - closing_value, 0)
        call_intrinsic = np.maximum(closing_value - short_call_strike, 0)
        
        # Final PnL calculation
        put_final_pnl  = put_cost  - put_intrinsic
        call_final_pnl = call_cost - call_intrinsic
        
        gross_pnl = np.maximum(put_final_pnl + call_final_pnl, -max_loss)
        
        # Retrieve the market regime for that day
        risk_regime_on_date = risk_regime_data[risk_regime_data["date"] == date].copy()
        daily_risk_regime = risk_regime_on_date["risk_regime"].iloc[0]
        
        # Save trade-level information
        trade_data = pd.DataFrame([{"date": date, "cost": cost, "gross_pnl": gross_pnl,
                                    "ticker": ticker,
                                    "long_strike" :long_put_strike,
                                    "short_put_strike": short_put_strike,
                                    "closing_value": closing_value,
                                    "short_call_strike": short_call_strike,
                                    "long_call_strike": long_call_strike,
                                    "daily_risk_regime": daily_risk_regime,
                                    "max_loss": max_loss}])

        trade_list.append(trade_data)

        # Runtime monitoring and ETA estimation
        end_time = datetime.now()
        seconds_to_complete = (end_time - start_time).total_seconds()
        times.append(seconds_to_complete)
        iteration = round((np.where(trading_dates==date)[0][0]/len(trading_dates))*100,2)
        iterations_remaining = len(trading_dates) - np.where(trading_dates==date)[0][0]
        average_time_to_complete = np.mean(times)
        estimated_completion_time = (datetime.now() + timedelta(seconds = int(average_time_to_complete*iterations_remaining)))
        time_remaining = estimated_completion_time - datetime.now()
        print(f"{iteration}% complete, {time_remaining} left, ETA: {estimated_completion_time}")

    except Exception as data_error:
        # Skip problematic dates and continue the loop
        print(data_error)
        continue

# =============================================================================
# Backtest
# =============================================================================

# Combine all daily trades
all_trades = pd.concat(trade_list).drop_duplicates(subset=["date"]).sort_values(by="date", ascending=True)
all_trades["date"] = pd.to_datetime(all_trades["date"])

# Initial portfolio capital
portfolio_size = 10000

# Number of contracts traded per day
contracts_traded = 1

all_trades["contracts"] = contracts_traded

# Convert option point PnL into dollar PnL (SPX multiplier = 100)
all_trades["dollar_pnl"] = (all_trades["gross_pnl"] * 100) * all_trades["contracts"]

# Equity curve
all_trades["capital"] = portfolio_size + all_trades["dollar_pnl"].cumsum()

## Curve Plotting

fig, ax = plt.subplots(figsize=(12, 6))

# Plot cumulative PnL
ax.plot(
    all_trades["date"],
    all_trades["capital"],
    linewidth=1.5
)

# Shade where risk_regime == 1
ax.fill_between(
    all_trades["date"],
    all_trades["capital"].min(),
    all_trades["capital"].max(),
    where=all_trades["daily_risk_regime"] == 1,
    alpha=0.2
)


plt.legend(["Smart-Strike", "Regime"])

ax.set_title(f"S&P 500 0-DTE Iron Condor Strategy")
ax.set_xlabel("Date")
ax.set_ylabel("Growth of Capital")

plt.show()