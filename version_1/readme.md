```markdown
# **Algorithmic Trading Backtesting & Genetic Optimization Framework**

This framework is a modular **algorithmic trading system** built in Python, featuring:

* Multi-strategy support (MA-ATR, RSI-MA-Reversal, ICT Hybrid, and more)
* Genetic Algorithm (GA) Optimizer for parameter tuning
* Monte Carlo analysis
* Comprehensive backtesting (PNL, drawdown, expectancy, Sharpe, etc.)
* Complete trade analytics (avg duration, avg win/loss, win/loss count)
* Clean ASCII table output and organized logging
* Professional and scalable code structure

This framework works for Forex, Crypto, and index markets using OHLCV data.

---

# **📂 Project Structure**

```

version_1/
│
├── main/
│   │
│   ├── data/                      # OHLCV datasets (CSV)
│   │   ├── datasets/
│   │   ├── fetcher.py
│   │   └── clean_datasets.ipynb
│   │
│   ├── strategies/                # All trading strategies
│   │   ├── base.py
│   │   ├── ma_atr.py
│   │   ├── rsi_ma_reversal.py
│   │   └── ict_hybrid.py
│   │
│   ├── optimizer/
│   │   ├── ga.py                  # Genetic Algorithm
│   │   ├── metrics.py             # Metrics & analytics
│   │   ├── monte_carlo.py         # Monte-Carlo simulation
│   │   └── config_ga.py           # GA parameter ranges/config
│   │
│   ├── engine/
│   │   ├── backtest_engine.py
│   │   ├── live_engine.py
│   │   └── live_engine_screening.py
│   │
│   ├── config.py
│   ├── run_backtest.py
│   └── run_live.py
│
├── logs/
│   ├── backtest/
│   └── live/
│
├── config.py
├── run_backtest.py.               # for backtest
├── run_live.py                    # run live trade with single pair
├── run_live_screening.py          # run live trade with multiple pair
├── requirements.txt
└── README.md

```

---

# **⚙️ Installation**

```

pip install -r requirements.txt

```

Minimal dependencies:

```

pandas
numpy
scipy
tqdm

````

---

# **📘 How Strategies Work**

All strategies extend the **Strategy** class from `strategies/base.py` and must output a column named **`signal`**:

* `1` → Buy  
* `-1` → Sell  
* `0` → No trade  

Stop-loss, take-profit, and lot sizing are handled by the **backtest engine**, not the strategies.

### MA + ATR Example

```python
signal = 1  # MA cross up + ATR filter pass
````

### RSI + MA Reversal Example

```python
signal = -1  # MA downturn + RSI reversal signal
```

---

# **🧬 GA Optimization (Genetic Algorithm)**

GA parameter configurations are stored in:

```
optimizer/config_ga.py
```

Example for MA-ATR:

```python
"ma_atr": {
    "ma_fast": (5, 30),
    "ma_slow": (20, 200),
    "atr_period": (5, 30),
    "atr_mult": (0.5, 3.0),
    "cooldown": (1, 15)
},
```

Run GA optimization:

```
python run_ga_optimize.py --strategy ma_atr
```

---

# **📈 Backtesting**

Run a manual backtest:

```
python run_backtest.py --strategy rsi_ma_reversal --symbol EURUSD --data data/EURUSD.csv
```

The output includes:

* Total PnL (USD)
* Win rate (%)
* Avg win / Avg loss
* Max drawdown (%)
* Sharpe, Sortino, Omega, MAR, Calmar ratios
* Consecutive wins/losses
* Average trade duration (hours)
* Winners & losers count
* ASCII metrics table

---

# **📊 Metrics Example Output**

```
+------------------------------------------------------+
|                       METRICS                        |
+------------------------------------------------------+
| trades                  | 572                        |
| total_pnl               | 209909.361192              |
| win_rate                | 0.590909                   |
| profit_factor           | 2.147966                   |
| expectancy              | 366.974408                 |
| max_drawdown            | -0.155474                  |
| sharpe                  | 2.192843                   |
| sortino                 | 3.551920                   |
| omega                   | 1.520553                   |
| cagr                    | 0.422331                   |
| calmar_ratio            | 2.693810                   |
| winners_count           | 338                        |
| losers_count            | 234                        |
| avg_win                 | 580.33                     |
| avg_loss                | -244.11                    |
| avg_duration_hours      | 23.2                       |
| max_consecutive_wins    | 7                          |
| max_consecutive_losses  | 4                          |
+------------------------------------------------------+
```

---

# **💡 Adding a New Strategy**

To add a new strategy:

1. Create a new file in `/strategies/xyz.py`
2. Extend the **Strategy** base class
3. Implement `generate_signals(df)` and return a DF with `signal`
4. Add GA parameter ranges in `optimizer/config_ga.py`

The framework will automatically support:

* Backtesting
* GA optimization
* Monte Carlo testing

---

# **🧪 Monte Carlo Simulation**

Run Monte Carlo robustness testing:

```
python run_montecarlo.py --strategy ma_atr
```

Outputs include:

* Best & worst equity curves
* Drawdown distribution
* Probability of ruin

---

# **🧵 Logging**

All results are stored in:

```
logs/live/
logs/screening/
```

---

# **📜 License**

MIT License.

---

# **👤 Author**

Developed by **Nauval Rajwaa Raysendria**.

If you need a PDF manual or video tutorials, feel free to ask!

```
```
