#!/usr/bin/env python3
"""Convert walk-forward evidence into an explicit, auditable trading gate."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path


def evaluate(report: dict, min_windows: int, min_sharpe: float,
             min_profit_factor: float, max_drawdown: float) -> dict:
    approved, details = [], {}
    for strategy, values in report.get("aggregates", {}).items():
        windows = [
            row for row in report.get("windows", [])
            if row.get("strategy") == strategy
        ]
        positive = sum(float(row.get("CAGR", 0) or 0) > 0 for row in windows)
        checks = {
            "enough_windows": len(windows) >= min_windows,
            "majority_positive": positive > len(windows) / 2,
            "sharpe": float(values.get("sharpe_mean", -999)) >= min_sharpe,
            "profit_factor": float(values.get("profit_factor_mean", 0)) >= min_profit_factor,
            "drawdown": abs(float(values.get("maxdd_mean", -999))) <= max_drawdown,
            "has_trades": int(values.get("trades_total", 0)) > 0,
        }
        details[strategy] = {**values, "positive_windows": positive, "checks": checks}
        if all(checks.values()):
            approved.append(strategy)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if approved else "BLOCKED",
        "approved_strategies": approved,
        "reason": "validated strategies available" if approved else "no strategy passed out-of-sample gates",
        "criteria": {
            "min_windows": min_windows, "min_sharpe": min_sharpe,
            "min_profit_factor": min_profit_factor,
            "max_abs_drawdown": max_drawdown,
            "majority_positive_windows": True,
        },
        "strategies": details,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--walk-forward", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--min-windows", type=int, default=5)
    parser.add_argument("--min-sharpe", type=float, default=0.30)
    parser.add_argument("--min-profit-factor", type=float, default=1.10)
    parser.add_argument("--max-drawdown", type=float, default=0.30)
    args = parser.parse_args()
    source = json.loads(Path(args.walk_forward).read_text(encoding="utf-8"))
    result = evaluate(source, args.min_windows, args.min_sharpe,
                      args.min_profit_factor, args.max_drawdown)
    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Economic gate: {result['status']} ({len(result['approved_strategies'])} approved)")


if __name__ == "__main__":
    main()
