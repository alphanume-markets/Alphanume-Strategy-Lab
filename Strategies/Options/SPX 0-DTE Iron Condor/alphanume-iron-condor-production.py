# -*- coding: utf-8 -*-
"""
@author: Alphanume Strategy Lab

This script generates a live SPX 0-DTE iron condor signal using Alphanume datasets.

High-level workflow:
1. Pull the latest available S&P 500 risk regime data from the Alphanume API.
2. Pull the latest available SPX 0-DTE strike band data from the Alphanume API.
3. Check whether the latest available dataset date matches today's trading date.
4. If data is current, extract the lower strike, upper strike, and risk regime for the day.
5. Output a simple live trade reference string for the current session.

This production-style example is designed to surface the daily strike band and regime context,
not to simulate execution or estimate real-time fill prices.
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

# Replace this placeholder with your own API key
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
print(f"{date} | SPX 0-DTE Iron Condor | Regime: {daily_risk_regime} | Short Put Reference: {lower_strike} | Short Call Reference: {upper_strike}")
