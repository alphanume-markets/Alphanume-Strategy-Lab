# Equities

The `equities/` directory contains systematic trading strategies applied to listed equity markets.

These strategies typically rely on:

- Point-in-time universe construction  
- Cross-sectional ranking methodologies  
- Liquidity and market capitalization filters  
- Explicit forward return measurement  
- Reproducible backtest workflows  

All implementations are production-oriented examples of how structured datasets can be integrated into quantitative equity research pipelines.

---

## Scope

This directory focuses on:

- US-listed equities  
- Exchange-traded common shares  
- Market-cap segmented universes  
- Event-driven and cross-sectional strategies  

Universe construction is explicitly defined inside each strategy folder to ensure point-in-time correctness.

---

## Data Requirements

Equity strategies in this directory may use:

- Alphanume historical market capitalization data  
- Alphanume optionable universe history  
- Alphanume event-driven datasets  
- Exchange-level OHLCV data (e.g., Polygon)  

Refer to each strategy’s `README.md` for exact API requirements and setup instructions.

---

## Structure

Each strategy lives in its own folder and is fully self-contained:

```
equities/
  strategy_name/
    README.md
    strategy_script.py
```

This ensures:

- Independent execution  
- Clear research assumptions  
- Transparent modeling logic  
- Clean reproducibility  

---

## Research Philosophy

Equity strategies in Strategy Lab are designed with:

- Explicit point-in-time data integrity  
- Transparent feature engineering  
- Clearly defined rebalance logic  
- Out-of-sample forward return evaluation  

These are not theoretical examples — they reflect how systematic equity research is implemented in practice.
