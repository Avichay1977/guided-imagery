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
| `tests/test_synthetic_stress.py` | 7 deterministic pytest stress tests (all green) |

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

### 6. Gap filter (dual-sided)
Entry is cancelled if next bar's open is outside this range relative to signal close:
- Too far up: `gap > +5%` → rejected (chasing)
- Too far down: `gap < -3%` → rejected (bad fill risk)

### 7. Exit logic — gap scenarios handled first
If bar opens through a level, fill is at actual open (not pre-calculated level):
```python
if row.open <= stop:       # gap down through stop
    return row.open, "stop_loss"
if row.open >= tp:         # gap up through TP
    return row.open, "take_profit"
# then intrabar checks...
```

### 8. Ambiguous exits (conservative)
When same bar hits both stop and TP intrabar (open is between them):
- Trade record: `exit_reason = "stop_loss"` (conservative — assume stop hit first)
- Separate counter: `results["ambiguous_exits"]` incremented for telemetry
- Exit price: stop_price (not TP)

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

## Confluence Score Logic (max 6 points, min required 5)

```python
# Technical structure (3 points max)
if close > ema_200:               score += 1
if close > local_high_20:         score += 1
if volume > volume_avg_20 * 1.5:  score += 1

# Market context — NaN-safe (3 points max)
if relative_strength > 1.05:      score += 1
if market_trend == "bullish":     score += 1
if volatility_regime != "extreme": score += 1
```

All 6 checks use `_has_valid_value()` — NaN fields score 0, not 1.

---

## Required DataFrame columns

```
open, high, low, close, volume   ← required OHLCV (from DataLoader)
signal                            ← 0 or 1 (from FeatureEngine, not yet built)
atr                               ← ATR value on signal bar
ema_200                           ← pre-computed 200-day EMA
local_high_20                     ← highest close of last 20 bars
volume_avg_20                     ← average volume of last 20 bars
relative_strength                 ← optional, float
market_trend                      ← optional, "bullish"/"bearish"/"neutral"
volatility_regime                 ← optional, "normal"/"high"/"extreme"
```

---

## Execution Flow (per bar)

```
bar N close → signal == 1?
           → confluence score >= 5?
           → gap filter: next_open within [-3%, +5%] of close?
           → ATR valid?
           → entry_price = next_open * (1 + slippage)
           → stop = entry - 2*ATR
           → shares = (cash * 1%) / risk_per_share
           → TP = entry + 3R

bar N+1+  → check exit (gap first, then intrabar)
           → if stop/TP hit: close position, apply slippage + fee
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
2. `calmar_ratio >= benchmark calmar` — risk-adjusted return beats passive
3. `profit_factor >= 1.2`

---

## Run Commands

```bash
pip install pandas numpy yfinance pytest

# Step 1: fetch data
python fetch_yfinance_data.py --ticker QQQ --start 2020-01-01 --end 2024-12-31 --output qqq_2020_2024.csv

# Step 2: run stress tests (must be green before using real data)
python -m pytest tests/test_synthetic_stress.py -v

# Step 3: run backtest
python main.py --input qqq_2020_2024.csv --adjust
```

---

## Synthetic Stress Tests (7/7 passing)

| Test | What it proves |
|---|---|
| `test_trending_market_hits_take_profit` | TP hit, R>0, entry on bar N+1 (no lookahead) |
| `test_entry_gap_up_is_cancelled` | +6% gap → 0 trades |
| `test_entry_gap_down_is_cancelled` | -4% gap → 0 trades |
| `test_stop_gap_down_exits_at_open_not_stop` | crash fill at actual open, R < -1 |
| `test_ambiguous_bar_counts_and_uses_stop_first` | counter+1, conservative stop fill |
| `test_nan_optional_fields_do_not_add_score` | NaN score = 0, guards old NaN bug |
| `test_crash_scenario_triggers_kill_switch` | 5% loss > 3% threshold → kill |

---

## Red Flags in Output (stop and investigate)

| Signal | Threshold | Action |
|---|---|---|
| `invalid_geometry_rows_corrected` | > 1% of rows | Inspect data source |
| `negative_or_zero_price_rows_removed` | > 0 | Check ticker / date range |
| `ambiguous_exits_pct` | > 5% | Daily OHLC too coarse |
| `expectancy_per_trade_r` | <= 0 | No edge — do not proceed |
| `adjusted_ohlc_applied` | False when expected True | Wrong CLI flag |

---

## Next Step: QQQ E2E Run

Run the three commands above and paste the full output:
- `=== DATA QUALITY REPORT ===`
- `=== BACKTEST ===`
- `=== METRICS ===`
- `=== BENCHMARK (buy & hold) ===`
- `=== STRATEGY VS BENCHMARK ===`
- `--- VERDICT ---`

**Decision criteria (in order):**
1. `adjusted_ohlc_applied: True` — mandatory
2. `expectancy_per_trade_r > 0` — edge must exist
3. `calmar_ratio >= benchmark calmar` — most important metric
4. `profit_factor >= 1.2`
5. Low CAGR vs buy-and-hold is acceptable if max_drawdown is much lower (tactical system)

**Do NOT proceed to multi_ticker_runner.py before QQQ output is reviewed.**

---

## What Has NOT Been Built Yet

- FeatureEngine (technical indicators → signal column, ema_200, local_high_20, etc.)
- Position sizing variants (fixed fractional, Kelly)
- `multi_ticker_runner.py` — portfolio-level multi-symbol backtesting
- Walk-forward validation
- Transaction cost sensitivity analysis
