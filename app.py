"""Streamlit interface for the NYC taxi analyst."""

import pandas as pd
import plotly.express as px
import streamlit as st

from data_analyst.agent import ask
from data_analyst.data import DATA_MONTH, TRIP_URL
from data_analyst.sql import describe_dataset

st.set_page_config(page_title="NYC Taxi Analyst", page_icon="🚕", layout="wide")
st.title("NYC Taxi Analyst")
st.caption(
    "Ask a focused question about the real NYC TLC Yellow Taxi sample loaded on this machine."
)

try:
    coverage = describe_dataset()
    st.info(
        f"Loaded sample: {coverage['row_count']:,} rows | "
        f"{coverage['start']} to {coverage['end']} | source month {DATA_MONTH}"
    )
except Exception:
    st.error("No local dataset found. Run `python scripts/download_data.py` first.")
    st.stop()

examples = [
    "How many trips occurred per day?",
    "What were the busiest pickup hours?",
    "What was the average fare by pickup borough?",
    "Compare weekday and weekend demand.",
]
selected = st.pills("Examples", examples, selection_mode="single")
question = st.text_input(
    "Question", value=selected or "", placeholder="How did demand change by day?"
)

if st.button("Analyze", type="primary", disabled=not question.strip()):
    with st.spinner("Analyzing the loaded sample..."):
        result = ask(question)
    if result.get("error"):
        st.error(result["error"])
    else:
        st.subheader("Answer")
        st.write(result["answer"])
        frame = pd.DataFrame(result["rows"])
        if 2 <= len(frame.columns) <= 3 and len(frame) > 1:
            first, second = frame.columns[:2]
            if pd.api.types.is_numeric_dtype(frame[second]):
                chart = (
                    px.bar(frame, x=first, y=second)
                    if len(frame) < 25
                    else px.line(frame, x=first, y=second)
                )
                st.plotly_chart(chart, use_container_width=True)
        st.dataframe(frame, use_container_width=True)
        with st.expander("SQL and diagnostics", expanded=True):
            st.code(result["sql"], language="sql")
            st.json(
                {
                    "query_latency_ms": round(result.get("latency_ms", 0), 2),
                    "status": "success",
                    "tokens": result.get("tokens", {}),
                }
            )

st.caption(f"Official source: {TRIP_URL}")
