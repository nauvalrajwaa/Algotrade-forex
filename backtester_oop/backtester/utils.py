# backtester/utils.py
import matplotlib.pyplot as plt
import pandas as pd

def plot_equity(equity_series_map, title="Equity"):
    plt.figure(figsize=(12,6))
    for label, series in equity_series_map.items():
        plt.plot(series.index, series.values, label=label)
    plt.legend()
    plt.title(title)
    plt.show()
