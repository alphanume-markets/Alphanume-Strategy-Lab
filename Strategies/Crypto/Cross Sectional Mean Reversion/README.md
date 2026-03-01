# Cross-Sectional Mean Reversion (Crypto)

This strategy implements a short-horizon cross-sectional mean reversion framework across USDT-denominated crypto pairs.

It ranks assets based on their distance from a rolling VWAP anchor and evaluates forward returns over a fixed holding window.

The objective is to demonstrate how structured OHLCV data can be transformed into a systematic, reproducible cross-sectional signal.

---

## Strategy Overview

**Asset Class:** Crypto  
**Universe:** USDT pairs on a specified exchange (e.g., MEXC)  
**Data Frequency:** 4-hour bars  
**Rebalance Frequency:** Daily  
**Holding Period:** ~1 day forward window  

The strategy operates cross-sectionally:

1. Construct a universe of exchange-traded USDT pairs  
2. Compute rolling features per asset  
3. Rank assets by deviation from a short-term anchor  
4. Form a top-decile basket  
5. Measure forward returns  

---

## Universe Construction

The universe is built using exchange-level metadata and filtered to:

- Quote currency: USDT  
- Exchange-specific listing (e.g., MEXC)  
- Valid OHLCV coverage  

All filtering is explicit and reproducible.

---

## Feature Construction

For each asset:

- Compute rolling log-return variance (short-term realized volatility)  
- Estimate short-term expected volatility  
- Compute rolling VWAP  
- Measure percentage distance from VWAP  

Primary ranking signal:

> **Distance from rolling VWAP (cross-sectional percentile rank)**

Assets furthest from their short-term VWAP anchor are ranked highest.

---

## Portfolio Construction

On each rebalance date:

- Rank all assets by distance from VWAP  
- Select the top decile (most extended assets)  
- Form an equal-weight basket  

Forward returns are measured over a fixed forward window to simulate holding performance.

---

## Backtest Methodology

- Explicit timestamp handling (timezone-aware)  
- Rolling window feature calculation  
- Cross-sectional ranking per rebalance date  
- Out-of-sample forward return measurement  

Capital is modeled using equal-weight basket returns with cumulative PnL tracking.

---

## Required Data

This strategy requires:

- Tiingo crypto OHLCV data (or equivalent exchange-level data source)  
- 4-hour resampled price and volume series  
- Exchange metadata for universe construction  

An active API key may be required to reproduce results.

---

## Adjustable Parameters

Key parameters that can be modified:

- Rolling volatility window size  
- VWAP lookback length  
- Rebalance hour  
- Basket size (e.g., top 5, top 10, top decile)  
- Holding window length  

These parameters allow adaptation to different exchanges or timeframes.

---

## Output

The script produces:

- Cross-sectional rankings per rebalance date  
- Forward return calculations  
- Basket-level cumulative equity curve  

Results are fully reproducible and transparent.

---

## Research Philosophy

This implementation is designed to reflect how systematic crypto strategies are structured in practice:

- Explicit universe construction  
- Deterministic feature engineering  
- Clear rebalance logic  
- Transparent forward evaluation  

It is not a signal service or investment recommendation.  
It is a reproducible research framework.
