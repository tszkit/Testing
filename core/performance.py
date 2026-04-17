"""Performance tracker: measures progress toward the 10% monthly target."""
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

from config.settings import MONTHLY_TARGET_PCT, RESULTS_DIR

logger = logging.getLogger(__name__)


@dataclass
class MonthlySnapshot:
    year: int
    month: int
    start_equity: float
    end_equity: float
    trades: int
    win_rate: float
    max_drawdown_pct: float

    @property
    def pnl_pct(self) -> float:
        return (self.end_equity - self.start_equity) / self.start_equity * 100

    @property
    def target_met(self) -> bool:
        return self.pnl_pct >= MONTHLY_TARGET_PCT


class PerformanceTracker:
    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self._equity_history: List[dict] = []          # {"date": ..., "equity": ...}
        self._monthly_snapshots: List[MonthlySnapshot] = []
        self._month_start_equity: float = initial_capital
        self._current_month: tuple = (date.today().year, date.today().month)

    def record(self, equity: float, trades_today: int = 0):
        today = date.today()
        self._equity_history.append({"date": str(today), "equity": round(equity, 2)})

        # Month rollover
        current = (today.year, today.month)
        if current != self._current_month:
            self._close_month(equity)
            self._current_month = current
            self._month_start_equity = equity

    def _close_month(self, end_equity: float):
        from core.portfolio import Trade  # avoid circular at module level
        year, month = self._current_month
        snap = MonthlySnapshot(
            year=year,
            month=month,
            start_equity=self._month_start_equity,
            end_equity=end_equity,
            trades=0,
            win_rate=0.0,
            max_drawdown_pct=0.0,
        )
        self._monthly_snapshots.append(snap)
        status = "✓ TARGET MET" if snap.target_met else "✗ below target"
        logger.info(
            "Month %d/%d closed | PnL=%.2f%% | %s",
            year, month, snap.pnl_pct, status,
        )

    def monthly_progress(self, current_equity: float) -> dict:
        start = self._month_start_equity
        pnl_pct = (current_equity - start) / start * 100
        remaining = MONTHLY_TARGET_PCT - pnl_pct
        return {
            "month_start_equity": round(start, 2),
            "current_equity": round(current_equity, 2),
            "month_pnl_pct": round(pnl_pct, 2),
            "target_pct": MONTHLY_TARGET_PCT,
            "remaining_to_target_pct": round(remaining, 2),
            "on_track": pnl_pct >= 0,
        }

    def overall_summary(self, current_equity: float) -> dict:
        total_pnl_pct = (current_equity - self.initial_capital) / self.initial_capital * 100
        months_completed = len(self._monthly_snapshots)
        months_on_target = sum(1 for s in self._monthly_snapshots if s.target_met)
        return {
            "initial_capital": self.initial_capital,
            "current_equity": round(current_equity, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "months_completed": months_completed,
            "months_on_target": months_on_target,
            "target_hit_rate": round(months_on_target / months_completed * 100, 1) if months_completed else 0,
        }

    def save(self, path: Optional[Path] = None):
        path = path or (RESULTS_DIR / f"performance_{date.today()}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "equity_history": self._equity_history,
            "monthly_snapshots": [asdict(s) for s in self._monthly_snapshots],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("Performance saved to %s", path)
