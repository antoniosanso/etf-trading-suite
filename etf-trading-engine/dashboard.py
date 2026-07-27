"""Simple Streamlit control panel for daily ETF decisions."""

from pathlib import Path
import json
import sys

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from src.engine.operations import build_orders
from src.engine.trading_costs import FinecoCosts


st.set_page_config(page_title="ETF Trading Suite", page_icon="📈", layout="wide")
st.title("📈 ETF Trading Suite")
st.caption("Segnali, portafoglio e risultati in un unico pannello operativo")

with st.sidebar:
    st.header("Parametri")
    output_dir = Path(st.text_input("Cartella risultati", "outputs"))
    capital = st.number_input("Capitale (€)", min_value=0.0, value=10_000.0, step=1_000.0)
    commission = st.number_input("Commissione Fineco per ordine (€)", 0.0, value=19.0)
    spread = st.number_input("Spread (basis point)", 0.0, value=10.0)
    tax = st.number_input("Fiscalità plusvalenze (%)", 0.0, 100.0, 26.0)
    risk = st.number_input("Rischio per operazione (%)", 0.1, 100.0, 1.5)
    st.info("Costi e fiscalità sono simulazioni configurabili: verificare il proprio profilo Fineco e la situazione fiscale.")


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


signals = read_csv(output_dir / "signals" / "entries_today.csv")
positions = read_csv(output_dir / "positions.csv")
curve = read_csv(output_dir / "equity_curve.csv")
kpis_path = output_dir / "kpis.json"
kpis = json.loads(kpis_path.read_text()) if kpis_path.exists() else {}

tab_signal, tab_positions, tab_performance, tab_report = st.tabs(
    ["Segnali", "Posizioni", "Performance", "Report operativo"]
)
with tab_signal:
    st.subheader("Segnali odierni")
    st.dataframe(signals, use_container_width=True, hide_index=True) if not signals.empty else st.info("Nessun segnale disponibile.")
with tab_positions:
    st.subheader("Posizioni aperte")
    st.dataframe(positions, use_container_width=True, hide_index=True) if not positions.empty else st.info("Nessuna posizione registrata in outputs/positions.csv.")
with tab_performance:
    cols = st.columns(4)
    for col, (name, value) in zip(cols, kpis.items()):
        col.metric(name, f"{value:.2%}" if name in {"MaxDD", "CAGR_sim"} else f"{value:.2f}")
    if not curve.empty:
        chart_cols = [c for c in ["Strategy", "Benchmark", "BuyHold"] if c in curve]
        date_col = "Date" if "Date" in curve else None
        st.line_chart(curve.set_index(date_col)[chart_cols] if date_col else curve[chart_cols])
        if chart_cols:
            st.dataframe(pd.DataFrame({"Rendimento totale": curve[chart_cols].iloc[-1] / curve[chart_cols].iloc[0] - 1}).style.format("{:.2%}"))
    else:
        st.info("Eseguire il backtest per confrontare strategia, benchmark e buy-and-hold.")
with tab_report:
    costs = FinecoCosts(commission, spread, tax / 100)
    orders = build_orders(signals, capital, risk_pct=risk, costs=costs)
    st.subheader("Piano per la prossima seduta")
    st.dataframe(orders, use_container_width=True, hide_index=True)
    st.download_button("Scarica report CSV", orders.to_csv(index=False).encode(), "report_operativo.csv", "text/csv")
