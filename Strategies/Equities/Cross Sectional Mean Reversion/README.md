# Cross-Sectional Mean Reversion (Equities — Nano Cap Universe)

This strategy implements a cross-sectional mean reversion framework applied exclusively to nano-cap US equities, selected using point-in-time market capitalization data.

It ranks stocks based on their deviation from a rolling price anchor and evaluates forward returns over a defined rebalance interval.

The objective is to demonstrate how point-in-time structured datasets can be used to construct reproducible small-cap systematic strategies.

---

## Strategy Overview

**Asset Class:** Equities  
**Universe:** US-listed nano-cap stocks  
**Market Cap Filter:** < $50 million (point-in-time classification)  
**Data Frequency:** Daily bars  
**Rebalance Frequency:** Periodic (e.g., every 10 trading days)  
**Holding Period:** Forward window until next rebalance date  

The strategy operates cross-sectionally:

1. Classify all stocks by market capitalization using historical point-in-time data  
2. Filter to nano-cap stocks only  
3. Compute rolling price anchors per stock  
4. Measure cross-sectional deviations  
5. Rank and select a basket  
6. Evaluate forward returns  

---

## Universe Construction (Point-in-Time Correctness)

The universe is explicitly constructed using prior-day market capitalization data.

Each stock is classified into a market-cap segment:

- Mega Cap  
- Large Cap  
- Mid Cap  
- Small Cap  
- Micro Cap  
- **Nano Cap (< $50m)**  

Only stocks classified as **nano cap on the prior trading day** are eligible for selection.

This ensures:

- No forward-looking bias  
- No reclassification leakage  
- True point-in-time universe integrity  

Universe membership can change over time as market caps fluctuate.

---

## Feature Construction

For each eligible nano-cap stock:

- Compute a rolling average price (short-term anchor)  
- Measure percentage distance from the rolling average  
- Rank stocks cross-sectionally by deviation  

Primary ranking signal:

> **Distance from rolling average price (cross-sectional percentile rank)**

Stocks most extended relative to their recent average are ranked highest.

---

## Portfolio Construction

On each rebalance date:

- Filter to nano-cap stocks (point-in-time)  
- Rank by deviation from rolling average  
- Select the top decile  
- Form an equal-weight basket  

Forward returns are measured over the next rebalance window.

Basket returns are aggregated and capital is tracked cumulatively.

---

## Backtest Methodology

- Explicit NYSE trading calendar alignment  
- Prior-day market cap classification  
- Rolling feature calculation per ticker  
- Cross-sectional ranking per rebalance date  
- Out-of-sample forward return evaluation  

All calculations are deterministic and reproducible.

---

## Required Data

This strategy requires:

- Alphanume historical market capitalization data (point-in-time)  
- Exchange-level daily OHLCV data (e.g., Polygon)  

An active API key may be required to reproduce results.

---

## Adjustable Parameters

Key parameters that can be modified:

- Rolling average window length  
- Rebalance frequency  
- Basket size (e.g., top 5, top 10)  
- Holding window length  

These allow adaptation to different liquidity tiers or holding horizons.

---

## Output

The script produces:

- Cross-sectional nano-cap rankings per rebalance date  
- Forward return calculations  
- Basket-level cumulative equity curve  

Results are fully transparent and reproducible.

---

## Research Philosophy

Nano-cap equities are structurally different from larger-cap stocks:

- Higher volatility  
- Lower liquidity  
- Greater cross-sectional dispersion  

This implementation demonstrates how disciplined, point-in-time universe construction can be combined with systematic ranking to explore mean reversion effects in the smallest capitalization segment of the equity market.

It is not investment advice or a signal service.  
It is a reproducible research framework.
