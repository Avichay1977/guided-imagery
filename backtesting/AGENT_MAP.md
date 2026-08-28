# Alpha Research — Agent Map v1

ארכיטקטורת מערכת המחקר הכמותי.  
כל Agent הוא מודול עצמאי עם קלט ופלט מוגדרים.  
**העיקרון המרכזי: כל Agent אומר "לא" לרוב המקרים.**

---

## מפת הזרימה

```
Idea Generator
      ↓
Feature Engineer
      ↓
Strategy Builder
      ↓
Backtest Engine
      ↓
Skeptic / Falsifier   ← הסוכן החשוב ביותר
      ↓
Risk Manager
      ↓
Benchmark Judge
      ↓
Paper Trading Monitor
      ↓
  כסף אמיתי קטן
```

---

## Agent 1 — Idea Generator

**מטרה:** לייצר השערות בלבד. לא לאשר.

| שדה | תוכן |
|-----|------|
| **Input** | רשימת מניות, אופק זמן, תיאור רג'ים שוק |
| **Output** | רשימה של 3–10 השערות עם שם ורציונל (לא קוד) |
| **Forbidden** | בדיקת רווחיות, אופטימיזציה, הבטחת תשואה |
| **Pass** | ≥3 השערות עם תנאי כניסה/יציאה ברורים ומנוסחים |
| **Fail** | פחות מ-3 השערות, או השערה לא ניתנת לקידוד |

**דוגמאות לפלט:**
```
1. Breakout + Volume — פריצת שיא 20 יום עם נפח ×1.5
2. Trend + Low Volatility — EMA50 > EMA200 ו-ATR < 90th percentile
3. Gap Continuation — פתיחה מעל שיא אתמול, לא גפ קיצוני
```

**קוד קיים:** לא קיים. יבנה בעתיד.

---

## Agent 2 — Feature Engineer

**מטרה:** להפוך OHLCV גלם לעמודות feature.

| שדה | תוכן |
|-----|------|
| **Input** | `pd.DataFrame` עם עמודות OHLCV נקיות |
| **Output** | `pd.DataFrame` עם עמודות feature — כולן shifted |
| **Forbidden** | כל feature ללא `shift(1)`, forward-fill על OHLC, שימוש בבר הנוכחי |
| **Pass** | כל עמודה עוברת בדיקת anti-lookahead אוטומטית |
| **Fail** | אם אפשר לשפר ביצועים על ידי הסרת ה-shift — הכלי שגוי |

**עמודות קיימות (`FeatureEngine`):**

| עמודה | מצב |
|-------|-----|
| `ema_200` | ✓ קיים |
| `ema_50` | ✓ קיים |
| `local_high_20` | ✓ קיים |
| `volume_avg_20` | ✓ קיים |
| `atr_14` | ✓ קיים |
| `atr_pct` | ✓ קיים |
| `market_trend` | ✓ קיים |
| `volatility_regime` | ✓ קיים |
| `signal` | ✓ קיים |
| `relative_strength` | ✗ דורש benchmark |
| `momentum_63` | ✗ עתיד |
| `volume_zscore` | ✗ עתיד |
| `gap_pct` | ✗ עתיד |

**קוד קיים:** `backtesting/features.py` — `FeatureEngine`

---

## Agent 3 — Strategy Builder

**מטרה:** להפוך features לחוקים מסחר.

| שדה | תוכן |
|-----|------|
| **Input** | רשימת עמודות feature זמינות, השערה מ-Agent 1 |
| **Output** | `BacktestConfig` + תנאי כניסה ב-Python (`signal` column logic) |
| **Forbidden** | שינוי `min_confluence_score` כדי "לקבל עסקאות", אופטימיזציה |
| **Pass** | החוקים דטרמיניסטיים, ניתנים לקוד, תואמים להשערה |
| **Fail** | כניסה לא ניתנת לניסוח בלי lookahead |

**קוד קיים:** `backtesting/backtester.py` — `BacktestConfig`, `calculate_confluence_score`

---

## Agent 4 — Backtest Engine

**מטרה:** לסמלץ עסקאות על עבר. לא לפסוק.

| שדה | תוכן |
|-----|------|
| **Input** | `pd.DataFrame` עם features, `BacktestConfig`, הון התחלתי |
| **Output** | `equity_curve`, `trades`, `kill_switch_triggered`, `ambiguous_exits` |
| **Forbidden** | שינוי stop/TP לאחר כניסה, הסתכלות על בר עתידי ביציאה |
| **Pass** | ≥30 עסקאות (סטטיסטיקה), ללא הפרות lookahead |
| **Fail** | פחות מ-30 עסקאות → לא ניתן להסיק מסקנות |

**קוד קיים:** `backtesting/backtester.py` — `Backtester.run()`

---

## Agent 5 — Skeptic / Falsifier

**מטרה:** להרוס רעיונות בזול — לפני שכסף אמיתי הורס אותם.

| שדה | תוכן |
|-----|------|
| **Input** | תוצאות Backtest, חוקי האסטרטגיה |
| **Output** | רשימת כשלונות שנמצאו + פסיקה: `PASS` / `FAIL` |
| **Forbidden** | קבלת אסטרטגיה שנכשלת בבדיקה, אופטימיזציה כ"תיקון" |
| **Pass** | האסטרטגיה שורדת את **כל** בדיקות הפסילה |
| **Fail** | כשל **אחד** מספיק לפסילה |

**בדיקות פסילה:**

| בדיקה | תנאי כשלון |
|--------|-----------|
| מספר עסקאות | < 30 |
| Max Drawdown | > 30% |
| Profit Factor | < 1.2 |
| Calmar | < benchmark |
| Out-of-sample (2022 בלבד) | כשל מוחלט |
| רגישות לפרמטר | שינוי ±20% בפרמטר → תוצאה שונה לגמרי |
| כל התשואה מ-3 עסקאות | כן → overfit |

**קוד קיים:** `backtesting/metrics.py` — חלקי. `Falsifier` — עתיד.

---

## Agent 6 — Risk Manager

**מטרה:** למנוע התאבדות פיננסית גם כשהאסטרטגיה "יפה".

| שדה | תוכן |
|-----|------|
| **Input** | פרמטרי אסטרטגיה, מצב תיק נוכחי, עסקה מוצעת |
| **Output** | `APPROVED` / `REJECTED` + גודל פוזיציה מאושר |
| **Forbidden** | חריגה ממגבלות סיכון, אישור בזמן kill switch |
| **Pass** | כל מגבלות הסיכון מתקיימות |
| **Fail** | חריגה **אחת** → NO TRADE |

**פרמטרי סיכון נוכחיים (`BacktestConfig`):**

| פרמטר | ערך ברירת מחדל |
|--------|---------------|
| `max_risk_pct` | 1% לעסקה |
| `max_drawdown_kill_pct` | 15% kill switch |
| `max_entry_gap_pct` | +5% |
| `min_entry_gap_pct` | -3% |

**קוד קיים:** `backtesting/portfolio.py`, `backtesting/execution.py` — חלקי.

---

## Agent 7 — Benchmark Judge

**מטרה:** לבדוק אם בכלל שווה לסחור אקטיבית.

| שדה | תוכן |
|-----|------|
| **Input** | מדדי אסטרטגיה, מדדי Buy & Hold |
| **Output** | `BETTER_THAN_PASSIVE` / `WORSE_THAN_PASSIVE` + טבלת דלתא |
| **Forbidden** | קבלת אסטרטגיה שגרועה מ-Buy & Hold על Calmar ו-Sharpe גם יחד |
| **Pass** | Calmar ≥ benchmark **וגם** Sharpe ≥ benchmark |
| **Fail** | גרוע משניהם → אין סיבה לסחור |

**קוד קיים:** `backtesting/main.py` — `STRATEGY VS BENCHMARK`, `VERDICT`

---

## Agent 8 — Paper Trading Monitor

**מטרה:** לוודא שה-Backtest מייצג מציאות לפני כסף אמיתי.

| שדה | תוכן |
|-----|------|
| **Input** | אותות live, מצב תיק נייר |
| **Output** | לוג אותות, P&L נייר, drift מ-Backtest |
| **Forbidden** | שינוי חוקים באמצע התקופה, cherry-picking |
| **Pass** | תקופת תצפית 30–90 יום הושלמה, תוצאות עקביות עם Backtest |
| **Fail** | סטייה > 30% מתוצאות Backtest → החזר ל-Skeptic |

**קוד קיים:** לא קיים. יבנה לאחר שהאסטרטגיה עוברת את Agent 7.

---

## מצב נוכחי

| Agent | מצב | קובץ |
|-------|-----|------|
| Idea Generator | ✗ עתיד | — |
| Feature Engineer | ✓ קיים | `features.py` |
| Strategy Builder | ✓ חלקי | `backtester.py` |
| Backtest Engine | ✓ קיים | `backtester.py` |
| Skeptic / Falsifier | ✗ עתיד | — |
| Risk Manager | ✓ חלקי | `portfolio.py`, `execution.py` |
| Benchmark Judge | ✓ חלקי | `main.py`, `metrics.py` |
| Paper Trading | ✗ עתיד | — |

**62/62 בדיקות ירוקות. DataLoader + FeatureEngine + Backtester + Metrics מוכנים.**

---

## הצעד הבא לפי הסדר

1. **להריץ Backtest על QQQ** עם FeatureEngine v2 ולראות עסקאות
2. **לבנות Falsifier** — הכלי שמנסה להרוס את האסטרטגיה
3. **Multi-Ticker** — לאחר שהאסטרטגיה שורדת Falsifier על נייר
