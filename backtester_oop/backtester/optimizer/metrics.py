import numpy as np
import pandas as pd


# ==============================================================
#   Sharpe, Sortino, Omega, MAR, Calmar (stabil)
# ==============================================================

def compute_risk_adjusted_metrics(equity_series: pd.Series,
                                  risk_free_rate: float = 0.0,
                                  mar_return: float = 0.10):
    """
    Compute Sharpe, Sortino, Omega, MAR ratio, Calmar ratio.
    252 periods per year assumed.
    """
    if equity_series is None or len(equity_series) < 3:
        return {k: np.nan for k in [
            "sharpe", "sortino", "omega", "mar_ratio", "calmar_ratio", "cagr"
        ]}

    returns = equity_series.pct_change().dropna()

    if len(returns) < 2:
        return {k: np.nan for k in [
            "sharpe", "sortino", "omega", "mar_ratio", "calmar_ratio", "cagr"
        ]}

    rf_adj = risk_free_rate / 252
    mean_r = returns.mean() - rf_adj

    std_r = returns.std()
    downside = returns[returns < 0].std()

    # Sharpe
    sharpe = (mean_r / std_r * np.sqrt(252)) if std_r > 0 else np.nan

    # Sortino
    sortino = (mean_r / downside * np.sqrt(252)) if downside > 0 else np.nan

    # Omega ratio
    threshold = 0.0
    gains = (returns - threshold)[returns > threshold].sum()
    losses = abs((returns - threshold)[returns < threshold].sum())
    omega = (gains / losses) if losses > 0 else np.inf

    # CAGR
    start_val = equity_series.iloc[0]
    end_val = equity_series.iloc[-1]
    num_years = len(equity_series) / 252

    cagr = (end_val / start_val) ** (1 / num_years) - 1 if start_val > 0 else np.nan

    # MAR ratio
    mar_ratio = cagr / mar_return if mar_return > 0 else np.nan

    # Max drawdown
    rolling_max = np.maximum.accumulate(equity_series)
    drawdown = equity_series / rolling_max - 1
    max_dd = float(drawdown.min())

    # Calmar
    calmar_ratio = abs(cagr / max_dd) if max_dd < 0 else np.inf

    return {
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "omega": float(omega),
        "cagr": float(cagr),
        "mar_ratio": float(mar_ratio),
        "calmar_ratio": float(calmar_ratio)
    }


# ==============================================================
#   Trade analytics (duration, avg win/loss, WR)
# ==============================================================

def trade_analytics(trades):
    if not trades:
        return {}

    durations = [
        (t["exit_time"] - t["entry_time"]).total_seconds() / 3600
        for t in trades
    ]

    pnl_list = [t.get("pnl", 0.0) for t in trades]
    winners = [p for p in pnl_list if p > 0]
    losers = [p for p in pnl_list if p <= 0]

    return {
        "avg_duration_hours": float(np.mean(durations)),
        "median_duration_hours": float(np.median(durations)),
        "winners_count": len(winners),
        "losers_count": len(losers),
        "avg_win": float(np.mean(winners)) if winners else 0.0,
        "avg_loss": float(np.mean(losers)) if losers else 0.0,
        "win_rate": len(winners) / len(pnl_list) if pnl_list else 0.0
    }


# ==============================================================
#   QuantConnect style metrics
# ==============================================================

def quantconnect_style_metrics(trades, equity_series: pd.Series):
    if not trades:
        return {}

    pl = [t.get("pnl", 0.0) for t in trades]
    pnl_series = pd.Series(pl)

    pnl_volatility = pnl_series.std()
    avg_return_per_trade = pnl_series.mean()

    cons_win = cons_loss = 0
    max_consecutive_wins = max_consecutive_losses = 0

    for p in pnl_series:
        if p > 0:
            cons_win += 1
            cons_loss = 0
        else:
            cons_loss += 1
            cons_win = 0
        max_consecutive_wins = max(max_consecutive_wins, cons_win)
        max_consecutive_losses = max(max_consecutive_losses, cons_loss)

    skew = pnl_series.skew()
    kurt = pnl_series.kurt()

    return {
        "pnl_volatility": float(pnl_volatility),
        "avg_return_per_trade": float(avg_return_per_trade),
        "max_consecutive_wins": int(max_consecutive_wins),
        "max_consecutive_losses": int(max_consecutive_losses),
        "pnl_skewness": float(skew),
        "pnl_kurtosis": float(kurt)
    }


# ==============================================================
#   Main metrics aggregator
# ==============================================================

def metrics_from_trades(trades,
                        equity_series: pd.Series = None,
                        initial_balance: float = 10000.0):

    if not trades:
        return {}

    pl = [t.get("pnl", 0.0) for t in trades]
    total_pnl = sum(pl)

    wins = [p for p in pl if p > 0]
    losses = [p for p in pl if p <= 0]
    win_rate = len(wins) / len(pl)

    profit_factor = (sum(wins) / abs(sum(losses))) if losses else np.inf
    avg_win = np.mean(wins) if wins else 0.0
    avg_loss = np.mean(losses) if losses else 0.0

    expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

    if equity_series is not None and len(equity_series) > 3:
        rolling_max = np.maximum.accumulate(equity_series)
        drawdown = equity_series / rolling_max - 1
        max_drawdown = float(drawdown.min())
    else:
        cum = np.cumsum(pl) + initial_balance
        max_drawdown = float((cum / np.maximum.accumulate(cum) - 1).min())

    metrics = {
        "trades": len(pl),
        "total_pnl": float(total_pnl),
        "win_rate": float(win_rate),
        "profit_factor": float(profit_factor),
        "expectancy": float(expectancy),
        "max_drawdown": max_drawdown,
        "avg_win": float(avg_win),
        "avg_loss": float(avg_loss)
    }

    if equity_series is not None:
        metrics.update(compute_risk_adjusted_metrics(equity_series))
        metrics.update(quantconnect_style_metrics(trades, equity_series))

    metrics.update(trade_analytics(trades))

    return metrics


# ==============================================================
#   ASCII BOX TABLE FORMATTER
# ==============================================================

def ascii_box_table(metrics: dict, title: str = "METRICS"):
    """
    Print metrics in a clean ASCII box table.
    """

    if not metrics:
        return "No metrics.\n"

    longest_key = max(len(k) for k in metrics.keys())
    longest_val = max(len(f"{v:.6f}") if isinstance(v, float) else len(str(v))
                      for v in metrics.values())

    width = longest_key + longest_val + 7

    lines = []
    lines.append("+" + "-" * width + "+")
    lines.append(f"| {title.center(width)} |")
    lines.append("+" + "-" * width + "+")

    for k, v in metrics.items():
        if isinstance(v, float):
            v = f"{v:.6f}"
        lines.append(f"| {k.ljust(longest_key)} | {str(v).rjust(longest_val)} |")

    lines.append("+" + "-" * width + "+")
    return "\n".join(lines)
