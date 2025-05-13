# dashboard_view.py

import streamlit as st
import pandas as pd
from datetime import datetime

def render_dashboard(df):
    st.markdown("## 📊 Shipment Dashboard")
    st.markdown("Get insights into submitted shipments, truck performance, and site activity.")

    # --- Filters Section ---
    df_filtered = df.copy()
    with st.sidebar:
        st.header("🔍 Filter Shipments")
        st.markdown("---")

        # Date Filter
        if "Date Submitted" in df_filtered.columns and not df_filtered["Date Submitted"].empty:
            min_date = df_filtered["Date Submitted"].min().date()
            max_date = df_filtered["Date Submitted"].max().date()
            default_range = [min_date, max_date]
            date_range = st.date_input(
                "📅 Submission Date Range",
                value=default_range,
                min_value=min_date,
                max_value=max_date,
                key="filter_date_range"
            )
            if isinstance(date_range, list) and len(date_range) == 2:
                start, end = date_range
                start_dt = datetime.combine(start, datetime.min.time())
                end_dt = datetime.combine(end, datetime.max.time())
                df_filtered = df_filtered[
                    (df_filtered["Date Submitted"] >= start_dt) &
                    (df_filtered["Date Submitted"] <= end_dt)
                ]
        else:
            st.info("No submission dates available.")

        st.markdown("---")

        # Client Filter
        if "Client" in df_filtered.columns and not df_filtered["Client"].dropna().empty:
            client_options = sorted(df_filtered["Client"].dropna().unique().tolist())
            selected_clients = st.multiselect("🏢 Filter by Client", options=client_options, key="filter_clients")
            if selected_clients:
                df_filtered = df_filtered[df_filtered["Client"].isin(selected_clients)]
        else:
            st.info("No client data available.")

    # --- Show Metrics ---
    if df_filtered.empty:
        st.warning("⚠️ No data matches the selected filters.")
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("📦 Shipments", 0)
        with col2: st.metric("🚛 Trucks", 0)
        with col3: st.metric("💸 Standing Charges", "R 0.00")
        with col4: st.metric("⏳ Avg Days on Site", "0.0")
        st.stop()

    total_shipments = df_filtered["Unique ID"].nunique() if "Unique ID" in df_filtered.columns else 0
    total_trucks = 0
    total_standing_charges = 0
    total_days_on_site = 0
    truck_count = 0

    # Calculate totals
    for _, row in df_filtered.iterrows():
        if "Trucks" in row and isinstance(row["Trucks"], list):
            total_trucks += len(row["Trucks"])
            for truck in row["Trucks"]:
                if isinstance(truck, dict):
                    if "Standing time charges" in truck and pd.notna(truck["Standing time charges"]):
                        total_standing_charges += truck["Standing time charges"]
                    if "Days on site" in truck and pd.notna(truck["Days on site"]):
                        total_days_on_site += truck["Days on site"]
                        truck_count += 1

    avg_days = total_days_on_site / truck_count if truck_count else 0

    # --- Display Key Metrics ---
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("📦 Total Shipments", total_shipments)
    with col2: st.metric("🚛 Total Trucks", total_trucks)
    with col3: st.metric("💰 Standing Charges", f"R {total_standing_charges:,.2f}")
    with col4: st.metric("⏱ Avg Days on Site", f"{avg_days:.1f}" if truck_count else "N/A")

    # --- Shipment Overview ---
    st.subheader("📋 Shipment Overview")
    grouped_df = df_filtered.sort_values("Date Submitted", ascending=False)

    for _, row in grouped_df.iterrows():
        uid = row["Unique ID"]
        client = row.get("Client", "Unknown")
        transporter = row.get("Transporter", "Unknown")
        trucks = row.get("Trucks", [])
        date_submitted = row.get("Date Submitted")
        truck_count = len(trucks)

        # Determine Status
        all_offloaded = all(truck.get("Date offloaded") for truck in trucks) if trucks else False
        all_dispatched = all(any("dispatch from" in k.lower() and pd.notna(truck.get(k)) for k in truck) for truck in trucks) if trucks else False
        partial_dispatch = any(any("dispatch from" in k.lower() and pd.notna(truck.get(k)) for k in truck) for truck in trucks) and not all_dispatched and not all_offloaded

        if not trucks:
            status_icon, label = "🔴", "No Truck Data"
        elif all_offloaded:
            status_icon, label = "🟢", "All Offloaded"
        elif all_dispatched:
            status_icon, label = "🟡", "Dispatched, Pending Offload"
        elif partial_dispatch:
            status_icon, label = "🟠", "Partially Dispatched"
        else:
            status_icon, label = "🔴", "Pending Dispatch"

        submitted_str = date_submitted.strftime("%Y-%m-%d %H:%M") if pd.notna(date_submitted) else "N/A"
        header = f"{status_icon} **{uid}** | 🏢 {client} | 🚚 {transporter} | 🛻 Trucks: {truck_count} | 🕒 {submitted_str} — *{label}*"

        with st.expander(header):
            if not trucks:
                st.info("No truck data found.")
            else:
                for truck in trucks:
                    truck.setdefault("Cancel", False)

                active_trucks = [t.copy() for t in trucks if not t.get("Cancel")]
                cancelled_trucks = [t.copy() for t in trucks if t.get("Cancel")]
                desired_columns = [
                    "Truck Number", "Horse Number", "Trailer Number", "Driver Name", "Passport NO.", "Contact NO.",
                    "Tonnage", "ETA", "Status", "Current Location", "Load Location", "Destination",
                    "Arrived at Loading point", "Loaded Date", "Dispatch date",
                    "Date Arrived", "Date offloaded", "Cancel", "Flag", "Comment"
                ]


                # --- ACTIVE TRUCKS ---
                if active_trucks:
                    st.markdown("### ✅ Active Trucks")

                    # Ensure all desired columns exist, set missing to default ("" or False for boolean fields)
                    cleaned_data = []
                    for truck in active_trucks:
                        row = {}
                        for col in desired_columns:
                            if col in ["Cancel", "Flag"]:
                                row[col] = bool(truck.get(col, False))
                            else:
                                row[col] = truck.get(col, "")
                        cleaned_data.append(row)

                    active_df = pd.DataFrame(cleaned_data)

                    # Format date/time columns
                    date_cols = [col for col in active_df.columns if any(s in col.lower() for s in ["date", "arrival", "dispatch", "eta"])]
                    for col in date_cols:
                        if pd.api.types.is_datetime64_any_dtype(active_df[col]):
                            active_df[col] = active_df[col].dt.strftime("%Y-%m-%d %H:%M").fillna("")
                        else:
                            active_df[col] = pd.to_datetime(active_df[col], errors="coerce").dt.strftime("%Y-%m-%d %H:%M").fillna("")

                    # Format numeric columns
                    num_cols = [col for col in active_df.columns if any(x in col.lower() for x in ["ton", "days", "charges", "weight"])]
                    for col in num_cols:
                        if pd.api.types.is_numeric_dtype(active_df[col]):
                            active_df[col] = active_df[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "")
                        else:
                            active_df[col] = pd.to_numeric(active_df[col], errors="coerce").apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "")

                    # Define column configurations for checkboxes (read-only)
                    column_config = {
                        "Cancel": st.column_config.CheckboxColumn("Cancel", disabled=True),
                        "Flag": st.column_config.CheckboxColumn("Flag", disabled=True),
                    }

                    # Show editable table
                    st.data_editor(
                        active_df,
                        use_container_width=True,
                        key=f"active_editor_{uid}",
                        hide_index=True,
                        column_config=column_config
                    )
                else:
                    st.info("No active trucks.")

                # --- CANCELLED TRUCKS ---
                if cancelled_trucks:
                    st.markdown("### ❌ Cancelled Trucks")

                    # Build DataFrame ensuring all desired columns exist
                    cleaned_data = []
                    for truck in cancelled_trucks:
                        row = {col: truck.get(col, "") for col in desired_columns}
                        cleaned_data.append(row)

                    cancelled_df = pd.DataFrame(cleaned_data)

                    # Format date/time columns
                    date_cols = [col for col in cancelled_df.columns if any(s in col.lower() for s in ["date", "arrival", "dispatch", "eta"])]
                    for col in date_cols:
                        if pd.api.types.is_datetime64_any_dtype(cancelled_df[col]):
                            cancelled_df[col] = cancelled_df[col].dt.strftime("%Y-%m-%d %H:%M").fillna("")
                        else:
                            cancelled_df[col] = pd.to_datetime(cancelled_df[col], errors="coerce").dt.strftime("%Y-%m-%d %H:%M").fillna("")

                    # Format numeric columns
                    num_cols = [col for col in cancelled_df.columns if any(x in col.lower() for x in ["ton", "days", "charges", "weight"])]
                    for col in num_cols:
                        if pd.api.types.is_numeric_dtype(cancelled_df[col]):
                            cancelled_df[col] = cancelled_df[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "")
                        else:
                            # Attempt to convert and format
                            cancelled_df[col] = pd.to_numeric(cancelled_df[col], errors="coerce").apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "")

                    # Styling
                    styled_df = cancelled_df.style.set_properties(**{
                        'background-color': '#ffe6e6',
                        'color': '#8a0000'
                    })

                    st.dataframe(styled_df, use_container_width=True)
                else:
                    st.info("No cancelled trucks.")

                # --- Truck Status Summary ---
                def render_truck_status_summary(df, title="📊 Truck Status Summary"):
                    # Try to find the correct status column
                    possible_status_cols = ["truck status", "status"]
                    status_col = next((col for col in df.columns if col.strip().lower() in possible_status_cols), None)

                    if status_col and not df.empty:
                        status_summary = df[status_col].value_counts()
                        if not status_summary.empty:
                            st.markdown(f"### {title}:")
                            for label, count in status_summary.items():
                                st.markdown(f"- **{count} truck(s)** — {label}")
                        else:
                            st.info("No truck statuses to summarize.")
                    else:
                        st.info("No status column found to summarize.")

                # Usage example after your dataframe is built
                render_truck_status_summary(active_df)
                # --- Download Button ---
                full_df = pd.DataFrame(trucks)
                csv_data = full_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📄 Download Truck Data (CSV)",
                    data=csv_data,
                    file_name=f"{uid}_trucks.csv",
                    mime="text/csv",
                    key=f"dl_{uid}"
                )