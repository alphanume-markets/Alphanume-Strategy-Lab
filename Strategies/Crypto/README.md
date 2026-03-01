# Crypto

The `crypto/` directory contains systematic trading strategies applied to digital asset markets.

These strategies typically rely on:

- Explicit exchange-level universe construction  
- Cross-sectional ranking methodologies  
- Liquidity-aware filtering  
- Rolling volatility and volume-based features  
- Clearly defined forward return windows  

All implementations are production-oriented examples of how structured crypto datasets can be integrated into quantitative research workflows.

---

## Scope

This directory focuses on:

- Exchange-specific universes (e.g., MEXC)  
- Perpetual futures and spot pairs  
- Quote-currency segmented products (e.g., USDT pairs)  
- Cross-sectional and short-horizon strategies  

Universe construction is explicitly defined inside each strategy folder to ensure consistency across exchanges and instruments.

---

## Data Requirements

Crypto strategies in this directory may use:

- Exchange-level OHLCV data (e.g., Tiingo, Polygon)  
- Resampled intraday datasets (e.g., 4-hour bars)  
- Liquidity and notional volume filters  
- Custom feature engineering derived from price/volume data  

Refer to each strategy’s `README.md` for exact API requirements and setup instructions.

---

## Structure

Each strategy lives in its own folder and is fully self-contained:

```
crypto/
  strategy_name/
    README.md
    strategy_script.py
```

This ensures:

- Independent execution  
- Explicit exchange assumptions  
- Transparent modeling logic  
- Clean reproducibility  

---

## Research Philosophy

Crypto strategies in Strategy Lab are designed with:

- Exchange-aware universe selection  
- Clear feature construction from raw OHLCV data  
- Explicit holding period definitions  
- Forward return evaluation using defined timestamps  

These are not theoretical demonstrations — they reflect how systematic crypto research can be implemented in practice.
