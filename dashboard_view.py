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
                arrived_lp_date_str = truck_copy.get("Arrived at Loading point")
                dispatch_date_lp_str = truck_copy.get("Dispatch date")
                free_days_lp = int(truck_copy.get("Free Days at Loading Point", 0) or 0)

                # Refined Robust parsing of Arrived at Loading point for calculations
                arrived_lp_dt = None
                if arrived_lp_date_str is not None and str(arrived_lp_date_str).strip() != '':
                    try:
                        if isinstance(arrived_lp_date_str, (int, float)):
                            arrived_lp_dt = pd.to_datetime(arrived_lp_date_str, unit='ms', errors='coerce')
                        else: # Assume string
                            arrived_lp_dt = pd.to_datetime(arrived_lp_date_str, errors='coerce')
                    except Exception as e:
                        st.warning(f"Could not parse 'Arrived at Loading point' for truck {truck_number}: {arrived_lp_date_str}. Error: {e}")
                        arrived_lp_dt = pd.NaT # Set to NaT if parsing fails

                dispatch_dt_lp = None
                if dispatch_date_lp_str is not None and str(dispatch_date_lp_str).strip() != '':
                    try:
                        if isinstance(dispatch_date_lp_str, (int, float)):
                            dispatch_dt_lp = pd.to_datetime(dispatch_date_lp_str, unit='ms', errors='coerce')
                        else:
                            dispatch_dt_lp = pd.to_datetime(dispatch_date_lp_str, errors='coerce')
                    except Exception as e:
                        st.warning(f"Could not parse 'Dispatch date' (LP) for truck {truck_number}: {dispatch_date_lp_str}. Error: {e}")
                        dispatch_dt_lp = pd.NaT


                billable_days_lp = 0
                demurrage_cost_lp = 0.0

                if pd.notna(arrived_lp_dt):
                    end_date_lp_calc = dispatch_dt_lp if pd.notna(dispatch_dt_lp) else pd.Timestamp(datetime.now())
                    days_at_loading = (end_date_lp_calc.floor('D') - arrived_lp_dt.floor('D')).days

                    billable_days_lp = max(0, days_at_loading - free_days_lp)
                    demurrage_cost_lp = billable_days_lp * demurrage_rate_truck

                truck_copy["Billable days at Loading Point"] = billable_days_lp
                truck_copy["Demurrage cost at Loading Point"] = demurrage_cost_lp


                # --- Calculate Billable days and Demurrage cost per Border ---
                total_overall_billable_days_at_all_borders = 0
                total_overall_demurrage_cost_at_all_borders = 0.0

                free_days_border = int(truck_copy.get("Free Days at Border", 0) or 0)

                # Logic to preserve border order from the 'Borders' object
                ordered_border_names_and_keys = []
                if "Borders" in truck_copy and isinstance(truck_copy["Borders"], dict):
                    seen_border_names = set()
                    for key in truck_copy["Borders"].keys():
                        if "actual arrival at" in key.lower():
                            name_part = key.replace("Actual arrival at ", "").strip()
                            if name_part not in seen_border_names:
                                ordered_border_names_and_keys.append((name_part, key, f"Actual dispatch from {name_part}"))
                                seen_border_names.add(name_part)
                
                for border_name, arrival_key, dispatch_key in ordered_border_names_and_keys:
                    # Refined Robust parsing for border dates for calculations
                    border_arrival_val = truck_copy["Borders"].get(arrival_key)
                    border_dispatch_val = truck_copy["Borders"].get(dispatch_key)

                    border_arrival_dt = None
                    if border_arrival_val is not None and str(border_arrival_val).strip() != '':
                        try:
                            if isinstance(border_arrival_val, (int, float)):
                                border_arrival_dt = pd.to_datetime(border_arrival_val, unit='ms', errors='coerce')
                            else:
                                border_arrival_dt = pd.to_datetime(border_arrival_val, errors='coerce')
                        except Exception as e:
                            st.warning(f"Could not parse 'Actual arrival at {border_name}' for truck {truck_number}: {border_arrival_val}. Error: {e}")
                            border_arrival_dt = pd.NaT

                    border_dispatch_dt = None
                    if border_dispatch_val is not None and str(border_dispatch_val).strip() != '':
                        try:
                            if isinstance(border_dispatch_val, (int, float)):
                                border_dispatch_dt = pd.to_datetime(border_dispatch_val, unit='ms', errors='coerce')
                            else:
                                border_dispatch_dt = pd.to_datetime(border_dispatch_val, errors='coerce')
                        except Exception as e:
                            st.warning(f"Could not parse 'Actual dispatch from {border_name}' for truck {truck_number}: {border_dispatch_val}. Error: {e}")
                            border_dispatch_dt = pd.NaT


                    billable_days_at_this_individual_border = 0
                    demurrage_cost_at_this_individual_border = 0.0

                    if pd.notna(border_arrival_dt):
                        end_date_border_calc = border_dispatch_dt if pd.notna(border_dispatch_dt) else pd.Timestamp(datetime.now())
                        days_at_this_border_raw = (end_date_border_calc.floor('D') - border_arrival_dt.floor('D')).days
                        
                        billable_days_at_this_individual_border = max(0, days_at_this_border_raw - free_days_border)
                        demurrage_cost_at_this_individual_border = billable_days_at_this_individual_border * demurrage_rate_truck

                    truck_copy[f"Billable days at {border_name}"] = billable_days_at_this_individual_border
                    truck_copy[f"Demurrage cost at {border_name}"] = demurrage_cost_at_this_individual_border

                    total_overall_billable_days_at_all_borders += billable_days_at_this_individual_border
                    total_overall_demurrage_cost_at_all_borders += demurrage_cost_at_this_individual_border

                truck_copy["Total Billable days at Borders"] = total_overall_billable_days_at_all_borders
                truck_copy["Total Demurrage cost at Border"] = total_overall_demurrage_cost_at_all_borders


                total_demurrage_costs_sum += demurrage_cost_lp + total_overall_demurrage_cost_at_all_borders

                if "Days on site" in truck_copy and pd.notna(truck_copy["Days on site"]):
                    total_days_on_site += truck_copy["Days on site"]
                    truck_count_for_avg_days += 1

                trucks_with_demurrage.append(truck_copy)

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

    def get_ordered_unique_border_names_from_truck(truck):
        ordered_border_names = []
        if "Borders" in truck and isinstance(truck["Borders"], dict):
            seen_names = set()
            for key in truck["Borders"].keys():
                if "actual arrival at" in key.lower():
                    name_part = key.replace("Actual arrival at ", "").strip()
                    if name_part not in seen_names:
                        ordered_border_names.append(name_part)
                        seen_names.add(name_part)
        return ordered_border_names


    for _, row in grouped_df.iterrows():
        uid = row["Unique ID"]
        client = row.get("Client", "Unknown")
        transporter = row.get("Transporter", "Unknown")
        trucks = row.get("Trucks", [])
        date_submitted = row.get("Date Submitted")
        truck_count = len(trucks)

        all_offloaded = all(truck.get("Date offloaded") for truck in trucks) if trucks else False
        
        all_dispatched_from_borders = True
        if trucks:
            for truck in trucks:
                truck_border_names = get_ordered_unique_border_names_from_truck(truck)
                if truck_border_names:
                    last_border_name = truck_border_names[-1]
                    dispatch_key = f"Actual dispatch from {last_border_name}"
                    if not (truck.get("Borders", {}) and pd.notna(truck["Borders"].get(dispatch_key))):
                        all_dispatched_from_borders = False
                        break
        else:
            all_dispatched_from_borders = False

        partial_dispatch = any(any(f"Actual dispatch from {bn}" in truck.get("Borders", {}) and pd.notna(truck.get("Borders", {}).get(f"Actual dispatch from {bn}")) for bn in get_ordered_unique_border_names_from_truck(truck)) for truck in trucks) and not all_offloaded and not all_dispatched_from_borders


        if not trucks:
            status_icon, label = "🔴", "No Truck Data"
        elif all_offloaded:
            status_icon, label = "🟢", "All Offloaded"
        elif all_dispatched_from_borders:
            status_icon, label = "🟡", "Dispatched, Pending Offload"
        elif partial_dispatch:
            status_icon, label = "🟠", "Partially Dispatched"
        else:
            status_icon, label = "🔴", "Pending Dispatch"

        # *** MODIFIED: Changed strftime format to remove timestamp ***
        submitted_str = date_submitted.strftime("%Y-%m-%d") if pd.notna(date_submitted) else "N/A"
        header = f"{status_icon} **{uid}** | 🏢 {client} | 🚚 {transporter} | 🛻 Trucks: {truck_count} | 🕒 {submitted_str} — *{label}*"

        with st.expander(header):
            if not trucks:
                st.info("No truck data found.")
            else:
                active_trucks = [t.copy() for t in trucks if not t.get("Cancel")]
                cancelled_trucks = [t.copy() for t in trucks if t.get("Cancel")]

                def get_all_unique_keys_from_nested_dict(trucks_list, parent_key):
                    all_keys = set()
                    for t in trucks_list:
                        if parent_key in t and isinstance(t[parent_key], dict):
                            all_keys.update(t[parent_key].keys())
                    return list(all_keys)

                all_trucks_combined = active_trucks + cancelled_trucks

                trailer_keys_all_possible = get_all_unique_keys_from_nested_dict(all_trucks_combined, "Trailers")
                
                all_border_names_ordered_globally = []
                seen_global_border_names = set()
                for truck_data in all_trucks_combined:
                    if "Borders" in truck_data and isinstance(truck_data["Borders"], dict):
                        for key in truck_data["Borders"].keys():
                            if "actual arrival at" in key.lower():
                                name_part = key.replace("Actual arrival at ", "").strip()
                                if name_part not in seen_global_border_names:
                                    all_border_names_ordered_globally.append(name_part)
                                    seen_global_border_names.add(name_part)
                
                border_display_columns = []
                for border_name in all_border_names_ordered_globally:
                    border_display_columns.append(f"Actual arrival at {border_name}")
                    border_display_columns.append(f"Actual dispatch from {border_name}")
                    border_display_columns.append(f"Billable days at {border_name}")
                    border_display_columns.append(f"Demurrage cost at {border_name}")


                # Define the insertion point for trailers
                base_columns_prefix = [
                    "Truck Number", "Horse Number"
                ]
                base_columns_suffix = [
                    "Driver Name", "Passport NO.", "Contact NO.",
                    "Tonnage", "ETA", "Status", "Cargo Description",
                    "Current Location", "Load Location", "Destination",
                    "Arrived at Loading point", "Loaded Date", "Dispatch date",
                    "Billable days at Loading Point", "Demurrage cost at Loading Point"
                ]

                desired_columns = (
                    base_columns_prefix +
                    trailer_keys_all_possible +
                    base_columns_suffix +
                    border_display_columns +
                    [
                        "Date Arrived", "Date offloaded",
                        "Total Billable days at Borders", "Total Demurrage cost at Border",
                        "Cancel", "Flag", "Comment"
                    ]
                )
                desired_columns = list(dict.fromkeys(desired_columns))


                # Helper function for consistent date formatting
                def format_date_for_display(value):
                    if value is None or (isinstance(value, str) and value.strip() == ''):
                        return ""
                    try:
                        if isinstance(value, (int, float)):
                            dt_obj = pd.to_datetime(value, unit='ms', errors='coerce')
                        else: # Assume string
                            dt_obj = pd.to_datetime(value, errors='coerce')
                        
                        if pd.notna(dt_obj):
                            # *** MODIFIED: Changed strftime format to remove timestamp ***
                            return dt_obj.strftime("%Y-%m-%d") 
                        else:
                            return ""
                    except Exception as e:
                        # You can add more specific logging here if needed
                        # st.warning(f"Error parsing date '{value}': {e}")
                        return str(value) # Fallback to original value string representation if all else fails


                if active_trucks:
                    st.markdown("### ✅ Active Trucks")

                    cleaned_data = []
                    for truck_data in active_trucks:
                        row = {}
                        for border_name in all_border_names_ordered_globally:
                            row[f"Actual arrival at {border_name}"] = ""
                            row[f"Actual dispatch from {border_name}"] = ""
                            row[f"Billable days at {border_name}"] = ""
                            row[f"Demurrage cost at {border_name}"] = ""
                        row["Total Billable days at Borders"] = ""
                        row["Total Demurrage cost at Border"] = ""


                        for col in desired_columns:
                            if col in ["Cancel", "Flag"]:
                                row[col] = bool(truck_data.get(col, False))
                            elif col in truck_data.get("Trailers", {}):
                                row[col] = truck_data.get("Trailers", {}).get(col, "")
                            elif col.startswith("Actual arrival at ") or col.startswith("Actual dispatch from "):
                                if "Borders" in truck_data and isinstance(truck_data["Borders"], dict):
                                    row[col] = format_date_for_display(truck_data["Borders"].get(col))
                            # Apply the helper function for other direct date columns
                            elif col in ["Arrived at Loading point", "Loaded Date", "Dispatch date", "Date Arrived", "Date offloaded", "ETA"]:
                                row[col] = format_date_for_display(truck_data.get(col))
                            elif col.startswith("Billable days at ") or col.startswith("Demurrage cost at ") or \
                                col == "Total Billable days at Borders" or col == "Total Demurrage cost at Border":
                                row[col] = truck_data.get(col, "")
                            else:
                                row[col] = truck_data.get(col, "")
                        cleaned_data.append(row)

                    active_df = pd.DataFrame(cleaned_data)

                    num_cols = [col for col in active_df.columns if any(x in col.lower() for x in ["ton", "days", "cost", "rate", "weight"])]
                    for col in num_cols:
                        active_df[col] = (
                            pd.to_numeric(active_df[col], errors="coerce")
                            .apply(lambda x: f"{x:,.2f}" if pd.notna(x) else ("" if "cost" in col.lower() else ""))
                        )
                        if "cost" in col.lower():
                            active_df[col] = active_df[col].apply(lambda x: f"R {x}" if x not in ["", None, "R "] else "")

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
                        column_config=column_config,
                        column_order=desired_columns
                    )
                else:
                    st.info("No active trucks.")


                if cancelled_trucks:
                    st.markdown("### ❌ Cancelled Trucks")

                    cleaned_data = []
                    for truck_data in cancelled_trucks:
                        row = {}
                        for border_name in all_border_names_ordered_globally:
                            row[f"Actual arrival at {border_name}"] = ""
                            row[f"Actual dispatch from {border_name}"] = ""
                            row[f"Billable days at {border_name}"] = ""
                            row[f"Demurrage cost at {border_name}"] = ""
                        row["Total Billable days at Borders"] = ""
                        row["Total Demurrage cost at Border"] = ""

                        for col in desired_columns:
                            if col in ["Cancel", "Flag"]:
                                row[col] = bool(truck_data.get(col, False))
                            elif col in truck_data.get("Trailers", {}):
                                row[col] = truck_data.get("Trailers", {}).get(col, "")
                            elif col.startswith("Actual arrival at ") or col.startswith("Actual dispatch from "):
                                if "Borders" in truck_data and isinstance(truck_data["Borders"], dict):
                                    row[col] = format_date_for_display(truck_data["Borders"].get(col))
                            # Apply the helper function for other direct date columns
                            elif col in ["Arrived at Loading point", "Loaded Date", "Dispatch date", "Date Arrived", "Date offloaded", "ETA"]:
                                row[col] = format_date_for_display(truck_data.get(col))
                            elif col.startswith("Billable days at ") or col.startswith("Demurrage cost at ") or \
                                col == "Total Billable days at Borders" or col == "Total Demurrage cost at Border":
                                row[col] = truck_data.get(col, "")
                            else:
                                row[col] = truck_data.get(col, "")
                        cleaned_data.append(row)

                    cancelled_df = pd.DataFrame(cleaned_data)

                    num_cols = [col for col in cancelled_df.columns if any(x in col.lower() for x in ["ton", "days", "cost", "rate", "weight"])]
                    for col in num_cols:
                        cancelled_df[col] = (
                            pd.to_numeric(cancelled_df[col], errors="coerce")
                            .apply(lambda x: f"{x:,.2f}" if pd.notna(x) else ("" if "cost" in col.lower() else ""))
                        )
                        if "cost" in col.lower():
                            cancelled_df[col] = cancelled_df[col].apply(lambda x: f"R {x}" if x not in ["", None, "R "] else "")


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
                        column_order=desired_columns
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