"""Fail-closed gates for real-money trading proposals."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

import pandas as pd


def load_economic_validation(path: str | Path, max_age_days: int = 7,
                             now: datetime | None = None) -> dict:
    """Return a validation report or a BLOCKED result for any uncertainty."""
    now = now or datetime.now(timezone.utc)
    path = Path(path)
    if not path.exists():
        return {"status": "BLOCKED", "reason": "economic validation report missing"}
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        generated = pd.Timestamp(report["generated_at"])
        if generated.tzinfo is None:
            generated = generated.tz_localize("UTC")
        age = now - generated.to_pydatetime()
        if age.total_seconds() < 0 or age.days > max_age_days:
            return {"status": "BLOCKED", "reason": "economic validation expired"}
        if report.get("status") != "PASS" or not report.get("approved_strategies"):
            return {"status": "BLOCKED", "reason": report.get("reason", "no approved strategy")}
        return report
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return {"status": "BLOCKED", "reason": f"invalid economic validation: {exc}"}


def data_is_fresh(eod: pd.DataFrame, max_age_days: int = 5,
                  now: datetime | None = None) -> tuple[bool, str]:
    now = now or datetime.now(timezone.utc)
    if eod.empty or "Date" not in eod:
        return False, "market data missing"
    dates = pd.to_datetime(eod["Date"], errors="coerce", utc=True).dropna()
    if dates.empty:
        return False, "market dates invalid"
    age = now - dates.max().to_pydatetime()
    if age.total_seconds() < 0 or age.days > max_age_days:
        return False, f"market data stale ({age.days} days)"
    return True, "ok"
