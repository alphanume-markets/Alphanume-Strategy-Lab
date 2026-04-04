# -*- coding: utf-8 -*-
"""
Created in 2026

@author: Alphanume

Multi-Endpoint Event-Driven Signal Extractor

This script pulls the latest event-driven datasets from the Alphanume API
(dilution, de-SPACs, defaults), filters for recent events, and formats them
into a clean, human-readable output of actionable signals.

Core idea:
Event → Timestamp → Tradeable Opportunity

Designed for:
- Daily monitoring
- Signal dashboards
- Lightweight automation pipelines
"""

import pandas as pd
import numpy as np
import requests
import pytz
import matplotlib.pyplot as plt

from datetime import datetime, timedelta
from pandas_market_calendars import get_calendar


def format_event_block(df, heading, date_col="date", ticker_col="ticker"):
    """
    Format a dataframe of events into a clean text block.

    Parameters
    ----------
    df : pd.DataFrame
        Event dataset containing at least a date and ticker column.
    heading : str
        Title of the event category (e.g., "Dilution").
    date_col : str
        Column name for event date.
    ticker_col : str
        Column name for ticker.

    Returns
    -------
    str
        Formatted string block:
        Heading
        YYYY-MM-DD - TICKER
    """
    
    # Handle empty datasets (no recent events)
    if df.empty:
        return f"{heading}\nNone\n"
    
    block_lines = [heading]
    
    # Ensure consistent date formatting
    temp = df.copy()
    temp[date_col] = pd.to_datetime(temp[date_col]).dt.strftime("%Y-%m-%d")
    
    # Build line-by-line event list
    for _, row in temp.iterrows():
        block_lines.append(f"{row[date_col]} - {row[ticker_col]}")
    
    return "\n".join(block_lines) + "\n"


# ---------------------------------------------------------
# Trading Calendar Setup
# ---------------------------------------------------------

# Use NYSE calendar to ensure trading-day aware filtering
calendar = get_calendar("NYSE")

# Generate full set of trading dates (historical + forward buffer)
all_trading_dates = calendar.schedule(
    start_date="2001-01-01",
    end_date=datetime.now(pytz.timezone("America/New_York")) + timedelta(days=300)
).index.strftime("%Y-%m-%d").values

# Current date in NY timezone
today = datetime.now(pytz.timezone("America/New_York")).strftime("%Y-%m-%d")

# Define "recent" as last 10 trading days
recent_date_cutoff = np.sort(all_trading_dates[all_trading_dates <= today])[-10]


# ---------------------------------------------------------
# API Key
# ---------------------------------------------------------

# Replace with your Alphanume API key
alphanume_api_key = "ALPHANUME_API_KEY"


# ---------------------------------------------------------
# Dilution Events
# ---------------------------------------------------------

# Pull dilution dataset
dilution_request = requests.get(
    f"https://api.alphanume.com/v1/dilution?api_key={alphanume_api_key}"
).json()

dilution_dataset = pd.json_normalize(dilution_request["data"])

# Filter for confirmed dilutive events only
dilution_events_data = (
    dilution_dataset[dilution_dataset["dilutive"] == 1]
    .copy()
    .sort_values(by="date", ascending=True)
    .reset_index(drop=True)
)

# Keep only recent events
recent_dilution_events = dilution_events_data[
    dilution_events_data["date"] >= recent_date_cutoff
].copy()


# ---------------------------------------------------------
# De-SPAC Events
# ---------------------------------------------------------

# Pull de-SPAC dataset
de_spac_request = requests.get(
    f"https://api.alphanume.com/v1/de-spac-events?api_key={alphanume_api_key}"
).json()

de_spac_dataset = pd.json_normalize(de_spac_request["data"])

# No additional filtering beyond recency
de_spac_events_data = de_spac_dataset.copy().reset_index(drop=True)

recent_de_spac_events = de_spac_events_data[
    de_spac_events_data["date"] >= recent_date_cutoff
].copy()


# ---------------------------------------------------------
# Corporate Default Events
# ---------------------------------------------------------

# Pull default dataset
default_request = requests.get(
    f"https://api.alphanume.com/v1/corporate-default-events?api_key={alphanume_api_key}"
).json()

default_dataset = pd.json_normalize(default_request["data"])

# Normalize column name for consistency across datasets
default_events_data = (
    default_dataset.copy()
    .rename(columns={"event_date": "date"})
    .sort_values(by="date", ascending=True)
    .reset_index(drop=True)
)

recent_default_events = default_events_data[
    default_events_data["date"] >= recent_date_cutoff
].copy()


# ---------------------------------------------------------
# Final Output (Actionable Event Feed)
# ---------------------------------------------------------

"""
Construct a consolidated event feed across all datasets.

Output format:

Dilution
YYYY-MM-DD - TICKER

De-SPACs
YYYY-MM-DD - TICKER

Defaults
YYYY-MM-DD - TICKER

This can be:
- Logged
- Sent to a dashboard
- Used as input for downstream trading logic
"""

final_script = "\n".join([
    format_event_block(recent_dilution_events, "Dilution"),
    format_event_block(recent_de_spac_events, "De-SPACs"),
    format_event_block(recent_default_events, "Defaults"),
])

# Print final actionable event stream
print(final_script)