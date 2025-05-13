# dashboard_view.py

import streamlit as st
import pandas as pd
from datetime import datetime

def render_shipments(df):
    st.markdown("## 📁 All Past Shipment IDs (Metadata View)")
    if df.empty:
        st.info("No shipment data available in the database.")
    else:
        if "Date Submitted" in df.columns:
            df["Date Submitted"] = pd.to_datetime(df["Date Submitted"], errors="coerce")
            df_valid_dates = df.dropna(subset=["Date Submitted"])
        else:
            df_valid_dates = df
            
        if "Unique ID" in df_valid_dates.columns:
            metadata_table = (
                df_valid_dates.sort_values("Date Submitted", ascending=False).groupby("Unique ID").first().reset_index()
            )
            
            display_cols = ["Unique ID", "Date Submitted", "Transporter", "Client", "Cargo Type", "Loading Point", "File Number", "Truck Count"]
            display_cols_present = [col for col in display_cols if col in metadata_table.columns]

            metadata_table = metadata_table[display_cols_present]

            if "Date Submitted" in metadata_table.columns:
                metadata_table = metadata_table.sort_values("Date Submitted", ascending=False).reset_index(drop=True)
                metadata_table["Date Submitted"] = metadata_table["Date Submitted"].dt.strftime("%Y-%m-%d %H:%M").fillna("") # Format datetime, use empty string for NaT

            metadata_table.index += 1

            st.dataframe(metadata_table, use_container_width=True)
        else:
            st.warning("Data is missing the 'Unique ID' column required for this view.")