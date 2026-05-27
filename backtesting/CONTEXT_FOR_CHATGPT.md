# Backtesting System — Context for Continuation

## Project Goal
Building a rigorous event-driven backtesting framework in Python for daily OHLCV data.
Designed around strict anti-lookahead principles.

---

## Directory: `backtesting/`

| File | Role |
|---|---|
| `fetch_yfinance_data.py` | CLI fetcher — downloads raw OHLCV from yfinance |
| `data_loader.py` | Cleans and validates CSV → DataFrame |
| `backtester.py` | Signal loop, position management, kill switch |
| `portfolio.py` | Cash + mark-to-market equity tracking |
| `execution.py` | Slippage, fees, open/close position accounting |
| `metrics.py` | CAGR, Sharpe, Calmar, expectancy_R, profit factor |
| `main.py` | End-to-end wiring + benchmark comparison + verdict |

---

## Key Design Decisions (non-negotiable)

### 1. No Lookahead
- Signal generated on **close of bar N**
- Entry executed on **open of bar N+1**
- All features shifted with `shift(1)` before signal logic

### 2. adjusted_close — explicit only
`use_adjusted_close` defaults to `False`.  
Must be set explicitly. If the source file is already adjusted, setting it again = double adjustment = corruption.  
CLI flag: `python main.py --input data.csv --adjust`

### 3. NaN != "extreme" bug (fixed)
Old code: `row.volatility_regime != "extreme"` → True for NaN → phantom score point  
Fix: `_has_valid_value(row, field_name)` checks `not pd.isna(value)` before comparison

```python
def _has_valid_value(self, row, field_name: str) -> bool:
    value = getattr(row, field_name, None)
    return value is not None and not pd.isna(value)
```

### 4. fetch_yfinance must use `auto_adjust=False`
We want raw Close + Adj Close columns. DataLoader handles adjustment, not yfinance.

### 5. OHLC sanitization rules (DataLoader)
- Missing OHLC row → **dropped** (no ffill/bfill)
- Missing Volume → filled with 0.0 (weakens volume signals, doesn't corrupt price)
- Non-positive prices → dropped
- Invalid geometry (high < low, etc.) → corrected by recalculating high/low from OHLC max/min
- Duplicate timestamps → keep last
- All coerced to numeric with `errors="coerce"` before validation

---

## BacktestConfig (current values)

```python
initial_cash = 100_000
max_risk_pct = 0.01          # 1% account risk per trade
max_drawdown_kill_pct = 0.15 # kill switch at 15% drawdown
min_confluence_score = 5     # minimum score to enter
atr_stop_multiplier = 2.0    # stop = entry - 2*ATR
take_profit_r = 3.0          # TP = entry + 3R
max_entry_gap_pct = 0.05     # reject if next open >5% above signal close
min_entry_gap_pct = -0.03    # reject if next open >3% below signal close
```

---

## Confluence Score Logic (in Backtester)

Optional fields — scored only if valid (not None, not NaN):

```python
if _has_valid_value(row, "relative_strength") and row.relative_strength > 1.05:
    score += 1

if _has_valid_value(row, "market_trend") and row.market_trend == "bullish":
    score += 1

if _has_valid_value(row, "volatility_regime") and row.volatility_regime != "extreme":
    score += 1
```

Min required: 5. (Most signals need other score sources — ATR signal, volume confirmation, etc. — that haven't been shown in full here but feed into `row.signal`.)

---

## Execution Flow (per bar)

```
row N close → check signal == 1
           → calculate confluence score
           → check gap filter vs row N+1 open
           → check ATR validity
           → compute shares from 1% risk
           → ExecutionSimulator.open_position() with slippage
row N+1+   → check exit: stop / take_profit / ambiguous (both hit same bar)
```

---

## Metrics Output

**Strategy metrics:**
- `total_return_pct`, `cagr_pct`, `sharpe_ratio`, `max_drawdown_pct`, `calmar_ratio`
- `total_trades`, `win_rate_pct`, `avg_win`, `avg_loss`, `profit_factor`
- `expectancy_per_trade_r` — mean R-multiple across all trades

**Benchmark (buy & hold):**
- Same equity metrics, no trade metrics
- Equity = `initial_cash * close / close[0]`

**VERDICT block checks:**
1. `expectancy_per_trade_r > 0` — edge must exist
2. `calmar_ratio ≥ benchmark calmar` — risk-adjusted return beats passive
3. `profit_factor ≥ 1.2`

---

## Run Commands

```bash
pip install pandas numpy yfinance

python fetch_yfinance_data.py --ticker QQQ --start 2020-01-01 --end 2024-12-31 --output qqq_2020_2024.csv

python main.py --input qqq_2020_2024.csv --adjust
```

---

## Red Flags in Output (stop and investigate)

| Signal | Threshold | Action |
|---|---|---|
| `invalid_geometry_rows_corrected` | > 1% of rows | Inspect data source |
| `negative_or_zero_price_rows_removed` | > 0 | Check ticker / date range |
| `ambiguous_exits_pct` | > 5% | Daily OHLC too coarse, consider intraday |
| `expectancy_per_trade_r` | ≤ 0 | No edge — do not proceed |
| `adjusted_ohlc_applied` | False (when expected True) | Wrong CLI flag |

---

## Next Step: Synthetic Stress Test

Before using real data results, run on **synthetic scenarios with known ground truth**:

1. **Trending market** — price rises 0.1%/day, signals every 10 bars → all TPs should hit
2. **Sideways chop** — random walk, no trend → most stops should hit, expectancy_R near 0
3. **Crash scenario** — single -20% gap down → kill switch must trigger
4. **NaN-heavy data** — 50% of optional fields are NaN → score must not exceed what's available
5. **Ambiguous exit scenario** — construct bars where high ≥ TP and low ≤ stop same bar → ambiguous_exits must count correctly

Purpose: confirm the system behaves *exactly* as designed before trusting any real-data output.

---

## What Has NOT Been Built Yet

- FeatureEngine (technical indicators → signal column)
- Position sizing variants (fixed fractional, Kelly)
- Multi-symbol portfolio support
- Walk-forward validation
- Transaction cost sensitivity analysis
