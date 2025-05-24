import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

def render_dashboard(df):
    st.markdown("## 📊 Shipment Dashboard")
    st.markdown("Get insights into submitted shipments, truck performance, and site activity.")

    # --- Filters Section ---
    df_filtered = df.copy()
    with st.sidebar:
        st.header("🔍 Filter Shipments")
        st.markdown("---")

        # Ensure "Date Submitted" is datetime for proper min/max BEFORE filtering
        if "Date Submitted" in df_filtered.columns:
            df_filtered["Date Submitted"] = pd.to_datetime(df_filtered["Date Submitted"], errors='coerce')
            # Drop rows where Date Submitted could not be parsed
            df_filtered = df_filtered.dropna(subset=["Date Submitted"])

        if "Date Submitted" in df_filtered.columns and not df_filtered["Date Submitted"].empty:
            min_date_available = df_filtered["Date Submitted"].min().date()
            max_date_available = df_filtered["Date Submitted"].max().date()

            if pd.isna(min_date_available):
                min_date_available = datetime.now().date()
            if pd.isna(max_date_available):
                max_date_available = datetime.now().date()

            default_range = [min_date_available, max_date_available]

            date_range = st.date_input(
                "📅 Submission Date Range",
                value=default_range,
                min_value=min_date_available,
                max_value=max_date_available,
                key="filter_date_range"
            )
            if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
                start, end = date_range
                start_dt = datetime.combine(start, datetime.min.time())
                end_dt = datetime.combine(end, datetime.max.time())
                df_filtered = df_filtered[
                    (df_filtered["Date Submitted"] >= start_dt) &
                    (df_filtered["Date Submitted"] <= end_dt)
                ]
        else:
            st.info("No submission dates available after parsing.")

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
        with col3: st.metric("💸 Total Demurrage Costs", "R 0.00")
        with col4: st.metric("⏳ Avg Days on Site", "0.0")
        st.stop()

    total_shipments = df_filtered["Unique ID"].nunique() if "Unique ID" in df_filtered.columns else 0
    total_trucks = 0
    total_demurrage_costs_sum = 0
    total_days_on_site = 0
    truck_count_for_avg_days = 0


    # --- Process each truck for calculations before displaying metrics and tables ---
    processed_shipments_with_demurrage = []
    
    for idx, row in df_filtered.iterrows():
        shipment_copy = row.to_dict()
        trucks_with_demurrage = []
        
        shipment_demurrage_rate = float(shipment_copy.get("Demurrage Rate", 0.0) or 0.0)

        if "Trucks" in shipment_copy and isinstance(shipment_copy["Trucks"], list):
            for truck in shipment_copy["Trucks"]:
                truck_copy = truck.copy()
                
                demurrage_rate_truck = float(truck_copy.get("Demurrage Rate", shipment_demurrage_rate) or 0.0)
                truck_number = truck_copy.get('Truck Number', 'N/A')

                # --- Calculate Billable days at Loading Point & Demurrage cost at Loading Point ---
                loaded_date_str = truck_copy.get("Loaded Date")
                dispatch_date_lp_str = truck_copy.get("Dispatch date")
                free_days_lp = int(truck_copy.get("Free Days at Loading Point", 0) or 0) # Get free days, default to 0

                loaded_dt_lp = pd.to_datetime(loaded_date_str, errors='coerce')
                dispatch_dt_lp = pd.to_datetime(dispatch_date_lp_str, errors='coerce')

                billable_days_lp = 0
                demurrage_cost_lp = 0.0

                if pd.notna(loaded_dt_lp):
                    end_date_lp_calc = dispatch_dt_lp if pd.notna(dispatch_dt_lp) else pd.Timestamp(datetime.now())
                    days_at_loading = (end_date_lp_calc.floor('D') - loaded_dt_lp.floor('D')).days
                    
                    billable_days_lp = max(0, days_at_loading - free_days_lp) # Subtract free days
                    demurrage_cost_lp = billable_days_lp * demurrage_rate_truck

                truck_copy["Billable days at Loading Point"] = billable_days_lp
                truck_copy["Demurrage cost at Loading Point"] = demurrage_cost_lp


                # --- Calculate Billable days at Border & Demurrage cost at Border ---
                billable_days_border = 0
                demurrage_cost_border = 0.0
                free_days_border = int(truck_copy.get("Free Days at Border", 0) or 0) # Get free days for border

                total_days_at_all_borders_raw = 0 # This will accumulate the gross days spent at all borders

                if "Borders" in truck_copy and isinstance(truck_copy["Borders"], dict):
                    border_data = truck_copy["Borders"]
                    
                    # Identify unique border names (e.g., "Testing 1", "Testing 2")
                    border_names = set()
                    for key in border_data.keys():
                        if "actual arrival at" in key.lower():
                            # Extract name after "Actual arrival at "
                            name_part = key.replace("Actual arrival at ", "").strip()
                            border_names.add(name_part)
                    
                    sorted_border_names = sorted(list(border_names))

                    for border_name in sorted_border_names:
                        arrival_key = f"Actual arrival at {border_name}"
                        dispatch_key = f"Actual dispatch from {border_name}"

                        border_arrival_dt = pd.to_datetime(border_data.get(arrival_key), errors='coerce')
                        border_dispatch_dt = pd.to_datetime(border_data.get(dispatch_key), errors='coerce')
                        
                        if pd.notna(border_arrival_dt):
                            end_date_border_calc = border_dispatch_dt if pd.notna(border_dispatch_dt) else pd.Timestamp(datetime.now())
                            
                            # Calculate days for THIS specific border segment (raw duration)
                            days_at_this_border = (end_date_border_calc.floor('D') - border_arrival_dt.floor('D')).days
                            
                            # Accumulate raw days at each border segment
                            total_days_at_all_borders_raw += max(0, days_at_this_border)

                # --- This is where Free Days at Border are subtracted and Billable days are set ---
                # billable_days_border is the final number of days for which demurrage applies
                billable_days_border = max(0, total_days_at_all_borders_raw - free_days_border)
                
                # --- This is where Demurrage cost is calculated using the Billable days ---
                demurrage_cost_border = billable_days_border * demurrage_rate_truck
                
                truck_copy["Total Days at All Borders (Before Free Days)"] = total_days_at_all_borders_raw 
                truck_copy["Free Days at Border Used"] = free_days_border # Display the free days value
                truck_copy["Billable days at Border"] = billable_days_border
                truck_copy["Demurrage cost at Border"] = demurrage_cost_border

                trucks_with_demurrage.append(truck_copy)
                total_demurrage_costs_sum += demurrage_cost_lp + demurrage_cost_border

                if "Days on site" in truck_copy and pd.notna(truck_copy["Days on site"]):
                    total_days_on_site += truck_copy["Days on site"]
                    truck_count_for_avg_days += 1

        total_trucks += len(trucks_with_demurrage)
        shipment_copy["Trucks"] = trucks_with_demurrage
        processed_shipments_with_demurrage.append(shipment_copy)

    avg_days = total_days_on_site / truck_count_for_avg_days if truck_count_for_avg_days else 0

    # --- Display Key Metrics (updated with calculated demurrage sum) ---
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("📦 Total Shipments", total_shipments)
    with col2: st.metric("🚛 Total Trucks", total_trucks)
    with col3: st.metric("💰 Total Demurrage Costs", f"R {total_demurrage_costs_sum:,.2f}")
    with col4: st.metric("⏱ Avg Days on Site", f"{avg_days:.1f}" if truck_count_for_avg_days else "N/A")


    # --- Shipment Overview ---
    st.subheader("📋 Shipment Overview")
    grouped_df = pd.DataFrame(processed_shipments_with_demurrage)
    if "Date Submitted" in grouped_df.columns:
        grouped_df["Date Submitted"] = pd.to_datetime(grouped_df["Date Submitted"], errors='coerce')
        grouped_df = grouped_df.sort_values("Date Submitted", ascending=False)
    else:
        st.warning("'Date Submitted' column missing or invalid for sorting in grouped_df.")


    for _, row in grouped_df.iterrows():
        uid = row["Unique ID"]
        client = row.get("Client", "Unknown")
        transporter = row.get("Transporter", "Unknown")
        trucks = row.get("Trucks", [])
        date_submitted = row.get("Date Submitted")
        truck_count = len(trucks)

        all_offloaded = all(truck.get("Date offloaded") for truck in trucks) if trucks else False
        all_dispatched = all(any("dispatch from" in k.lower() and pd.notna(truck.get("Borders", {}).get(k)) for k in truck.get("Borders", {})) for truck in trucks) if trucks else False
        partial_dispatch = any(any("dispatch from" in k.lower() and pd.notna(truck.get("Borders", {}).get(k)) for k in truck.get("Borders", {})) for truck in trucks) and not all_dispatched and not all_offloaded

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
                active_trucks = [t.copy() for t in trucks if not t.get("Cancel")]
                cancelled_trucks = [t.copy() for t in trucks if t.get("Cancel")]
                
                def extract_ordered_keys(data_list, field):
                    for item in data_list:
                        if isinstance(item.get(field), dict):
                            border_dict_keys = list(item[field].keys())
                            return sorted(border_dict_keys) 
                    return []

                border_keys = extract_ordered_keys(active_trucks, "Borders")
                trailer_keys = extract_ordered_keys(active_trucks, "Trailers")

                desired_columns = [
                    "Truck Number", "Horse Number"
                ]
                desired_columns.extend(trailer_keys)
                desired_columns.extend([
                    "Driver Name", "Passport NO.", "Contact NO.",
                    "Tonnage", "ETA", "Status", "Cargo Description",
                    "Current Location", "Load Location", "Destination",
                    "Arrived at Loading point", "Loaded Date", "Dispatch date",
                    "Free Days at Loading Point",
                    "Billable days at Loading Point", "Demurrage cost at Loading Point"
                ])
                desired_columns.extend(border_keys) 
                desired_columns.extend([
                    "Free Days at Border", # Display the input free days
                    "Total Days at All Borders (Before Free Days)", # Optional: for debugging/visibility
                    "Billable days at Border", "Demurrage cost at Border",
                    "Date Arrived", "Date offloaded", "Cancel", "Flag", "Comment"
                ])
                desired_columns = list(dict.fromkeys(desired_columns))


                if active_trucks:
                    st.markdown("### ✅ Active Trucks")

                    cleaned_data = []
                    for truck_data in active_trucks:
                        row = {}
                        for col in desired_columns:
                            if col in ["Cancel", "Flag"]:
                                row[col] = bool(truck_data.get(col, False))
                            elif col in trailer_keys:
                                row[col] = truck_data.get("Trailers", {}).get(col, "")
                            elif col in border_keys:
                                row[col] = truck_data.get("Borders", {}).get(col, "")
                            else:
                                row[col] = truck_data.get(col, "")
                        cleaned_data.append(row)

                    active_df = pd.DataFrame(cleaned_data)

                    date_cols = [col for col in active_df.columns if any(s in col.lower() for s in ["date", "arrival", "dispatch", "eta"])]
                    for col in date_cols:
                        active_df[col] = (
                            pd.to_datetime(active_df[col], errors="coerce")
                            .dt.strftime("%Y-%m-%d %H:%M")
                            .fillna("")
                        )

                    num_cols = [col for col in active_df.columns if any(x in col.lower() for x in ["ton", "days", "cost", "rate", "weight"])]
                    for col in num_cols:
                        active_df[col] = (
                            pd.to_numeric(active_df[col], errors="coerce")
                            .apply(lambda x: f"{x:,.2f}" if pd.notna(x) else ("" if "cost" in col.lower() else ""))
                        )

                    column_config = {
                        col: st.column_config.TextColumn(col, disabled=True)
                        for col in active_df.columns
                    }

                    column_config["Cancel"] = st.column_config.CheckboxColumn("Cancel", disabled=True)
                    column_config["Flag"] = st.column_config.CheckboxColumn("Flag", disabled=True)

                    st.data_editor(
                        active_df,
                        use_container_width=True,
                        key=f"active_editor_{uid}",
                        hide_index=True,
                        column_config=column_config
                    )
                else:
                    st.info("No active trucks.")


                if cancelled_trucks:
                    st.markdown("### ❌ Cancelled Trucks")

                    border_keys_cancelled = extract_ordered_keys(cancelled_trucks, "Borders")
                    trailer_keys_cancelled = extract_ordered_keys(cancelled_trucks, "Trailers")

                    desired_columns_cancelled = [
                        "Truck Number", "Horse Number"
                    ]
                    desired_columns_cancelled.extend(trailer_keys_cancelled)
                    desired_columns_cancelled.extend([
                        "Driver Name", "Passport NO.", "Contact NO.",
                        "Tonnage", "ETA", "Status", "Cargo Description",
                        "Current Location", "Load Location", "Destination",
                        "Arrived at Loading point", "Loaded Date", "Dispatch date",
                        "Free Days at Loading Point",
                        "Billable days at Loading Point", "Demurrage cost at Loading Point"
                    ])
                    desired_columns_cancelled.extend(border_keys_cancelled)
                    desired_columns_cancelled.extend([
                        "Free Days at Border", # Display the input free days
                        "Total Days at All Borders (Before Free Days)", # Optional: for debugging/visibility
                        "Billable days at Border", "Demurrage cost at Border",
                        "Date Arrived", "Date offloaded", "Cancel", "Flag", "Comment"
                    ])
                    desired_columns_cancelled = list(dict.fromkeys(desired_columns_cancelled))


                    cleaned_data = []
                    for truck_data in cancelled_trucks:
                        row = {}
                        for col in desired_columns_cancelled:
                            if col in ["Cancel", "Flag"]:
                                row[col] = bool(truck_data.get(col, False))
                            elif col in trailer_keys_cancelled:
                                row[col] = truck_data.get("Trailers", {}).get(col, "")
                            elif col in border_keys_cancelled:
                                row[col] = truck_data.get("Borders", {}).get(col, "")
                            else:
                                row[col] = truck_data.get(col, "")
                        cleaned_data.append(row)

                    cancelled_df = pd.DataFrame(cleaned_data)

                    date_cols = [col for col in cancelled_df.columns if any(s in col.lower() for s in ["date", "arrival", "dispatch", "eta"])]
                    for col in date_cols:
                        cancelled_df[col] = (
                            pd.to_datetime(cancelled_df[col], errors="coerce")
                            .dt.strftime("%Y-%m-%d %H:%M")
                            .fillna("")
                        )

                    num_cols = [col for col in cancelled_df.columns if any(x in col.lower() for x in ["ton", "days", "cost", "rate", "weight"])]
                    for col in num_cols:
                        cancelled_df[col] = (
                            pd.to_numeric(cancelled_df[col], errors="coerce")
                            .apply(lambda x: f"{x:,.2f}" if pd.notna(x) else ("" if "cost" in col.lower() else ""))
                        )

                    column_config = {
                        col: st.column_config.TextColumn(col, disabled=True)
                        for col in cancelled_df.columns
                    }
                    column_config["Cancel"] = st.column_config.CheckboxColumn("Cancel", disabled=True)
                    column_config["Flag"] = st.column_config.CheckboxColumn("Flag", disabled=True)

                    st.data_editor(
                        cancelled_df,
                        use_container_width=True,
                        key=f"cancelled_editor_{uid}",
                        hide_index=True,
                        column_config=column_config,
                        disabled=True,
                        height=min(len(cancelled_df) * 35 + 50, 700),
                        column_order=cancelled_df.columns.tolist()
                    )
                else:
                    st.info("No cancelled trucks.")

                def render_truck_status_summary(df_summary, title="📊 Truck Status Summary"):
                    possible_status_cols = ["truck status", "status"]
                    status_col = next((col for col in df_summary.columns if col.strip().lower() in possible_status_cols), None)

                    if status_col and not df_summary.empty:
                        status_summary = df_summary[status_col].value_counts()
                        if not status_summary.empty:
                            st.markdown(f"### {title}:")
                            for label, count in status_summary.items():
                                st.markdown(f"- **{count} truck(s)** — {label}")
                        else:
                            st.info("No truck statuses to summarize.")
                    else:
                        st.info("No status column found to summarize.")

                if not active_df.empty:
                    render_truck_status_summary(active_df)
                else:
                    st.info("No active trucks for status summary.")

                download_df = pd.DataFrame(trucks)
                csv_data = download_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📄 Download Truck Data (CSV)",
                    data=csv_data,
                    file_name=f"{uid}_trucks.csv",
                    mime="text/csv",
                    key=f"dl_{uid}"
                )