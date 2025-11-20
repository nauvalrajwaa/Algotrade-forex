# **Algorithmic Trading Backtesting & Genetic Optimization Framework**

Framework ini adalah sistem **algo-trading modular** berbasis Python dengan fitur:

* Multi-strategy (MA-ATR, RSI-MA-Reversal, ICT Hybrid, dan lainnya)
* Genetic Algorithm (GA) Optimizer untuk mencari parameter terbaik
* Monte Carlo analysis
* Backtesting dengan detail lengkap (PNL, drawdown, expectancy, Sharpe, dll.)
* Trade analytics lengkap (avg duration, avg win/loss, winning/losing count)
* Output ASCII table dan logging rapi
* Struktur code profesional dan scalable

Framework ini cocok untuk Forex, Crypto, dan indeks berbasis OHLCV.

---

# **📂 Project Structure**

```
project/
│
├── data/                      # Dataset OHLCV (CSV)
│
├── strategies/               # All trading strategies
│   ├── base.py
│   ├── ma_atr.py
│   ├── rsi_ma_reversal.py
│   └── ict_hybrid.py
│
├── optimizer/
│   ├── ga.py                 # Genetic Algorithm
│   ├── metrics.py            # Metrics & analytics
│   ├── monte_carlo.py        # Monte-Carlo simulation
│   └── config_ga.py          # GA parameter ranges per strategy
│
├── backtester/
│   ├── engine.py             # Core backtest engine
│   └── executor.py           # Trade execution logic (SL/TP, etc.)
│
├── run_backtest.py           # Run single backtest
├── run_ga_optimize.py        # Run GA optimization
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
```

---

# **📘 How Strategies Work**

Semua strategi extend class **Strategy** dari strategies/base.py dan **menghasilkan kolom `signal`** berisi:

* `1` → Buy
* `-1` → Sell
* `0` → No trade

SL/TP dan lot ditangani oleh **engine backtest**, bukan strategi.

### Example: MA + ATR

```python
signal = 1  # MA cross up + ATR filter pass
```

### Example: RSI + MA Reversal

```python
signal = -1  # MA downturn + RSI rebound
```

---

# **🧬 GA Optimization (Genetic Algorithm)**

GA memakai file parameter di:

```
optimizer/config_ga.py
```

Contoh untuk MA-ATR:

```python
"ma_atr": {
    "ma_fast": (5, 30),          # Fast MA period
    "ma_slow": (20, 200),        # Slow MA period
    "atr_period": (5, 30),       # ATR length
    "atr_mult": (0.5, 3.0),      # ATR factor
    "cooldown": (1, 15)          # Anti-whipsaw
},
```

Menjalankan GA optimizer:

```
python run_ga_optimize.py --strategy ma_atr
```

---

# **📈 Backtesting**

Jalankan backtest manual:

```
python run_backtest.py --strategy rsi_ma_reversal --symbol EURUSD --data data/EURUSD.csv
```

Output mencakup:

* PnL total (USD)
* Win rate (%)
* Avg win/loss (USD)
* Max drawdown (%)
* Sharpe, Sortino, Omega, MAR, Calmar
* Consecutive wins/losses
* Avg duration (hours)
* Winners & losers count
* ASCII box metrics table

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

# **💡 Adding New Strategy**

1. Buat file baru di `/strategies/xyz.py`
2. Extend base class **Strategy**
3. Implementasikan `generate_signals(df)` dan return DF dengan kolom `signal`
4. Tambahkan parameter GA di `optimizer/config_ga.py`

Framework langsung bisa:

* Backtest
* Optimize GA
* Monte Carlo

---

# **🧪 Monte Carlo Simulation**

Simulasi reshuffling PnL untuk validasi robustness:

```
python run_montecarlo.py --strategy ma_atr
```

Output:

* Worst-case equity curve
* Best-case equity curve
* Probability of ruin
* Drawdown distribution

---

# **🧵 Logging**

Semua hasil GA, backtest, dan MC dapat disimpan ke folder:

```
logs/ga/
logs/backtest/
logs/mc/
```

---

# **📜 License**

MIT License.

---

# **👤 Author**

Developed by **Nauval Rajwaa Raysendria**.

Jika perlu dokumentasi PDF atau video tutorial, beritahu saya!
