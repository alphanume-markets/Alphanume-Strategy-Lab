# SPX 0-DTE Iron Condor

This strategy implements a systematic **0-DTE iron condor framework on the S&P 500 index**, with strike selection anchored to probability information derived from the options market.

Rather than placing strikes using fixed heuristics (e.g., selling 30-delta options or placing strikes a fixed percentage away from spot), the strategy uses **Alphanume's SPX 0-DTE strike band dataset** to identify probabilistic containment ranges for the trading session.

The objective is to demonstrate how **forward-looking information embedded in options prices** can be used to construct more consistent volatility-selling strategies.

---

## Strategy Overview

**Asset Class:** Index Options  
**Underlying:** S&P 500 Index (SPX)  
**Instrument Type:** SPXW 0-DTE options  
**Strategy Type:** Short volatility (iron condor)  
**Trade Frequency:** Daily  
**Entry Time:** Intraday (e.g., 10:30 ET)  
**Holding Period:** Same-day expiration  

For each trading day the strategy:

1. Retrieves a probabilistic strike band for SPX using the Alphanume API  
2. Selects out-of-the-money puts below the lower strike bound  
3. Selects out-of-the-money calls above the upper strike bound  
4. Constructs an iron condor using the nearest available strikes  
5. Estimates entry prices using midpoint quotes  
6. Holds the position until expiration  
7. Calculates PnL using the SPX closing value

---

## Strike Selection Framework

Traditional 0-DTE strategies often rely on simplified strike rules:

- Fixed delta levels (e.g., 30-delta)
- Fixed distance from spot
- Static expected move assumptions

These approaches can become misaligned with the **actual probability distribution implied by the options market**.

This strategy instead uses the **Alphanume SPX 0-DTE Strike Band dataset**, which estimates probabilistic containment ranges using:

- At-the-money straddle implied moves  
- Volatility skew across strikes  
- Intraday volatility behavior  
- Market regime context  

The resulting strike band represents the **range where the index is most likely to remain through the close**.

Iron condor strikes are then constructed **outside this probabilistic containment range**.

---

## Trade Construction

For each trading session:

- **Short Put:** nearest strike below the lower strike band  
- **Long Put:** next strike lower (defined by spread width)  

- **Short Call:** nearest strike above the upper strike band  
- **Long Call:** next strike higher  

This produces a symmetric iron condor positioned outside the modeled containment region.

Entry pricing is estimated using **quote midpoints** around the chosen trade timestamp.

---

## Backtest Methodology

The backtest script performs the following:

- Aligns trading dates with the NYSE trading calendar  
- Pulls strike bands and regime data from the Alphanume API  
- Retrieves available SPXW contracts from Polygon  
- Estimates entry prices using midpoint quote data  
- Holds positions until expiration (same-day settlement)  
- Calculates final PnL using the SPX closing value  

The backtest explicitly models:

- Option bid/ask midpoint execution  
- Strike availability from the options chain  
- Realistic contract selection logic  

All calculations are deterministic and reproducible.

---

## Required Data

This strategy requires:

- Alphanume SPX 0-DTE Strike Band dataset  
- Alphanume S&P 500 Risk Regime dataset  
- SPX options contract data (Polygon/Massive)  
- SPX index price data (Polygon / Massive)

An active API key may be required to reproduce results.

---

## Repository Structure

This strategy directory contains both a research backtest and a production-style script.

```
options/
  SPX 0-DTE Iron Condor/
    README.md
    alphanume-iron-condor-backtest.py
    alphanume-iron-condor-production.py
```

- **Backtest script** demonstrates the full research workflow and historical evaluation.
- **Production script** shows how the strategy could be deployed to generate daily trade signals.

Both scripts rely on the same underlying data sources and strike selection methodology.

---

## Adjustable Parameters

Key parameters that can be modified:

- Trade entry time  
- Spread width  
- Position sizing (contracts traded)  
- Portfolio capital assumptions  

These parameters allow experimentation with different risk profiles and execution windows.

---

## Output

The backtest produces:

- Daily trade records  
- Strategy PnL per session  
- Cumulative capital curve  

The equity curve can also be compared against **market regime conditions** using the included risk regime dataset.

---

## Educational Video

A full walkthrough of this strategy and its underlying concepts is available on the Alphanume YouTube channel.

YouTube channel:

[Alphanume Research](https://www.youtube.com/@Alphanume-Research)

The video covers:

- Why many 0-DTE strategies fail  
- How probability distributions can be extracted from options prices  
- Why strike selection is critical for volatility-selling strategies  
- How this framework improves strategy consistency

---

## Research Philosophy

Most options strategies fail not because of their structure, but because of **how strikes are chosen**.

Iron condors, credit spreads, and butterflies are simply payoff structures.

The real edge comes from **aligning those structures with the market’s forward-looking probability distribution**.

This implementation demonstrates how structured datasets and systematic strike selection can be combined to construct reproducible options strategies.

It is not investment advice or a signal service.  
It is a reproducible research framework.
