# Options

The `options/` directory contains systematic trading strategies applied to listed options markets.

These strategies typically rely on:

- Implied volatility surface information  
- Explicit strike selection methodologies  
- Defined entry and exit logic  
- Intraday or daily event-driven triggers  
- Reproducible backtest workflows  

All implementations are production-oriented examples of how structured options datasets can be integrated into quantitative derivatives research pipelines.

---

## Scope

This directory focuses on:

- Index and equity options markets  
- Short-dated and event-driven strategies  
- Systematic volatility trading  
- Strike selection and probability-based modeling  
- Intraday and daily options strategies  

Strategies in this directory emphasize how options prices encode forward-looking information about the market, and how that information can be systematically extracted and incorporated into trading models.

---

## Data Requirements

Options strategies in this directory may use:

- Alphanume options-derived datasets  
- Alphanume SPX strike band datasets  
- Alphanume market regime datasets  
- Exchange-level options quotes and trades (e.g., Polygon/Massive)  
- Underlying asset market data (OHLCV)

Refer to each strategy’s `README.md` for exact API requirements and setup instructions.

---

## Structure

Each strategy lives in its own folder and is fully self-contained:

```
options/
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

Options strategies in Strategy Lab are designed with:

- Explicit modeling of implied volatility and option pricing dynamics  
- Transparent strike selection frameworks  
- Clearly defined payoff structures and risk profiles  
- Realistic execution assumptions using market quote data  

These are not theoretical examples — they reflect how systematic options research is implemented in practice.
