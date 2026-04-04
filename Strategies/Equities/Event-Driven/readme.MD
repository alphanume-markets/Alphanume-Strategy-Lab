# Event-Driven Short Strategies (Equities — Dilution, De-SPACs, Defaults)

This repository implements a multi-strategy event-driven framework focused on systematically shorting equities following structurally negative corporate events.

Instead of relying on price-based signals or technical indicators, these strategies are built on **discrete, timestamped market events** — such as dilution filings, De-SPAC completions, and corporate defaults.

The objective is to demonstrate how point-in-time event datasets can be transformed into **repeatable, testable trading strategies**.

---

## Strategy Overview

**Asset Class:** Equities  
**Strategy Type:** Event-driven (short bias)  
**Data Frequency:** Daily bars  
**Entry Timing:** First trading day after event  
**Holding Period:** Fixed forward windows (1 week, 1 month, 3 months)  

Each strategy follows the same structure:

1. Identify a specific market event  
2. Collect all historical occurrences  
3. Align entry timing to avoid lookahead bias  
4. Measure forward returns  
5. Aggregate performance across events  

---

## Core Idea

Markets do not move randomly.

They react to **information becoming public**.

In many cases, that information is:

- explicitly disclosed  
- timestamped  
- economically meaningful  

This framework treats events as signals:

> **Event → Outcome → Trade**

Rather than modeling price behavior directly, the strategies focus on **what caused the move in the first place**.

---

## Event Categories

### 1. Dilution

- Company issues or registers new shares (e.g., S-1 filings)
- Increases float and introduces new supply
- Often leads to sustained downward price pressure

This strategy shorts stocks following confirmed dilutive events.

---

### 2. De-SPACs

- Private company merges into a public SPAC shell
- Often represents an adversely selected group (could not IPO traditionally)
- Post-merger unlocks and selling pressure drive repricing

This strategy shorts stocks following De-SPAC completion events.

---

### 3. Corporate Defaults

- Company misses debt obligations or enters financial distress
- Signals severe deterioration in fundamentals
- Equity often continues trending lower after the event

This strategy shorts stocks following default-related filings.

---

## Event Timing & Execution Assumptions

To avoid lookahead bias:

- Trades are entered **one trading day after the event date**
- Forward returns are measured from the first available post-event price

This ensures:

- No use of future information  
- Realistic reaction-based execution  
- Reproducible results  

---

## Backtest Methodology

Each event is processed independently:

1. Extract event date and ticker  
2. Align to the next valid trading day  
3. Pull forward price data (Polygon / Massive)  
4. Compute cumulative returns  
5. Extract fixed forward horizons:
   - 1 week  
   - 1 month  
   - 3 months  

Portfolio construction:

- Equal position size per event  
- Short exposure (inverse PnL)  
- Capital tracked cumulatively across events  

---

## Data Integrity Considerations

The implementation includes basic safeguards:

- Trading calendar alignment (NYSE)  
- Forward-only return calculation  
- Filtering of incomplete or malformed price series  

However, this is still a **research-grade backtest**, not a production simulation.

---

## Required Data

This framework requires:

- **Alphanume event datasets**
  - Dilution  
  - De-SPAC Events  
  - Corporate Default Events  

- **Daily OHLCV data**
  - Polygon / Massive (or equivalent)

An API key is required to reproduce results.

---

## Output

Each script produces:

- Event-level forward return metrics  
- Aggregated trade dataset  
- Cumulative capital curve (equity curve)  
- Simple hit rate statistics  

Results are fully deterministic and reproducible.

---

## Adjustable Parameters

Key parameters that can be modified:

- Holding period (1w / 1m / 3m)  
- Position size per trade  
- Portfolio starting capital  
- Event filters (e.g., market cap, liquidity)  

These allow extension into more realistic trading systems.

---

## Limitations

This implementation does **not** account for:

- Borrow costs / locate availability  
- Short-sale restrictions (e.g., low-priced stocks)  
- Slippage and execution latency  
- Overlapping position constraints  
- Liquidity filters  

These factors are especially relevant for:

- nano-cap dilution trades  
- distressed default names  

---

## Research Philosophy

Most strategies attempt to extract signal from price.

This framework starts earlier.

It focuses on:

- **what happened**
- **when it happened**
- **what tends to happen next**

These events are:

- public  
- timestamped  
- economically grounded  

Yet often underutilized in systematic trading.

The goal is not to present a finished product, but to demonstrate a process:

> turning real-world market events into structured, tradeable signals.

---

## Disclaimer

This is not investment advice or a signal service.  
It is a reproducible research framework.
