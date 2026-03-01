# Strategies

The `strategies/` directory contains fully reproducible quantitative trading workflows organized by asset class.

Each strategy folder is self-contained and includes:

- Research context and assumptions  
- Python implementation scripts  
- Required dependencies  
- Modeling and/or backtest logic  
- Clear output definitions  

Strategies are organized by asset class to reflect how research is structured in production environments.

---

## Directory Structure

```
strategies/
  equities/
    cross_sectional_mean_reversion/
      README.md
      strategy_script.py
  crypto/
    mexc_cross_sectional_mean_reversion/
      README.md
      strategy_script.py
```

Each asset class directory contains one or more strategy implementations.

---

## Design Principles

All strategies in this repository follow the same design philosophy:

- **Point-in-time correctness**  
- **Explicit universe construction**  
- **Transparent feature engineering**  
- **Clear forward return logic**  
- **Reproducible outputs**

These are not theoretical examples.  
They reflect how quantitative workflows are structured in practice.

---

## Data Dependencies

Most strategies rely on one or more of the following:

- Alphanume market data APIs  
- Exchange-level OHLCV data (e.g., Polygon, Tiingo)  

To fully reproduce results, an active API key may be required.

Refer to each individual strategy’s README for specific requirements.
