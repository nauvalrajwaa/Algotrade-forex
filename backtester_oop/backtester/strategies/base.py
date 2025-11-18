# backtester/strategies/base.py
from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any

class Strategy(ABC):
    """
    Base strategy. Implement generate_signals to return a DataFrame column 'signal':
      1 for long, -1 for short, 0 for flat/no action.
    """
    def __init__(self, params: Dict[str, Any] = None):
        self.params = params or {}

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return dataframe with at least a 'signal' column aligned to df index."""
        raise NotImplementedError
