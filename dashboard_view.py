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
        
        st.markdown("---")

        # NEW: File Number Filter
        if "File Number" in df_filtered.columns and not df_filtered["File Number"].dropna().empty:
            file_number_options = sorted(df_filtered["File Number"].dropna().unique().tolist())
            selected_file_numbers = st.multiselect("🗄️ Filter by File Number", options=file_number_options, key="filter_file_numbers")
            if selected_file_numbers:
                df_filtered = df_filtered[df_filtered["File Number"].isin(selected_file_numbers)]
        else:
            st.info("No file number data available.")
        

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

        # Ensure 'Demurrage Rate' from shipment level is used if not present at truck level
        shipment_demurrage_rate = float(shipment_copy.get("Demurrage Rate", 0.0) or 0.0)

        if "Trucks" in shipment_copy and isinstance(shipment_copy["Trucks"], list):
            for truck in shipment_copy["Trucks"]:
                truck_copy = truck.copy()

                # Use truck's demurrage rate, or fall back to shipment's
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
                        arrived_lp_dt = pd.NaT # Set to NaT if parsing fails

                dispatch_dt_lp = None
                if dispatch_date_lp_str is not None and str(dispatch_date_lp_str).strip() != '':
                    try:
                        if isinstance(dispatch_date_lp_str, (int, float)):
                            dispatch_dt_lp = pd.to_datetime(dispatch_date_lp_str, unit='ms', errors='coerce')
                        else:
                            dispatch_dt_lp = pd.to_datetime(dispatch_date_lp_str, errors='coerce')
                    except Exception as e:
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
                            border_arrival_dt = pd.NaT

                    border_dispatch_dt = None
                    if border_dispatch_val is not None and str(border_dispatch_val).strip() != '':
                        try:
                            if isinstance(border_dispatch_val, (int, float)):
                                border_dispatch_dt = pd.to_datetime(border_dispatch_val, unit='ms', errors='coerce')
                            else:
                                border_dispatch_dt = pd.to_datetime(border_dispatch_val, errors='coerce')
                        except Exception as e:
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


    # --- Shipment Overview (now grouped by File Number) ---
    st.subheader("📋 Shipment Overview by File Number")
    
    # Convert processed shipments to DataFrame for easier grouping
    df_processed = pd.DataFrame(processed_shipments_with_demurrage)

    if "File Number" not in df_processed.columns or df_processed["File Number"].empty:
        st.warning("No 'File Number' data available to group shipments. Displaying all shipments directly.")
        # Fallback to original shipment overview if no file numbers
        # We need a way to call the individual rendering without the file number context, if this happens
        render_individual_shipment_overview(df_processed, file_number_key_prefix="no_file_")
        return # Exit to prevent further errors if no file numbers

    unique_file_numbers = sorted(df_processed["File Number"].dropna().unique().tolist())

    # Helper function for consistent date formatting
    def format_date_for_display(value):
        if value is None or (isinstance(value, str) and str(value).strip() == ''):
            return ""
        try:
            if isinstance(value, (int, float)):
                dt_obj = pd.to_datetime(value, unit='ms', errors='coerce')
            else: # Assume string
                dt_obj = pd.to_datetime(value, errors='coerce')
            
            if pd.notna(dt_obj):
                return dt_obj.strftime("%Y-%m-%d") 
            else:
                return ""
        except Exception as e:
            return str(value)

    # Function to get ordered border names for a truck (re-used)
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

    # Function to render individual shipment details (extracted for re-use)
    # This function is now designed to be called directly, not within an expander
    def render_individual_shipment_overview(df_shipments_to_render, file_number_key_prefix=""):
        if "Date Submitted" in df_shipments_to_render.columns:
            df_shipments_to_render["Date Submitted"] = pd.to_datetime(df_shipments_to_render["Date Submitted"], errors='coerce')
            df_shipments_to_render = df_shipments_to_render.sort_values("Date Submitted", ascending=False)
        else:
            st.warning("'Date Submitted' column missing or invalid for sorting in grouped_df.")

        for _, row in df_shipments_to_render.iterrows():
            uid = row["Unique ID"]
            client = row.get("Client", "Unknown")
            transporter = row.get("Transporter", "Unknown")
            trucks = row.get("Trucks", [])
            date_submitted = row.get("Date Submitted")
            truck_count = len(trucks)

            shipment_type_raw = row.get("Shipment Type")
            if pd.isna(shipment_type_raw) or shipment_type_raw is None:
                shipment_geo_type = "Unknown"
            else:
                shipment_geo_type = str(shipment_type_raw).replace("-", " ")

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
                    elif shipment_geo_type.lower() == "cross border": # If shipment is explicitly cross-border but this truck has no border data
                        if not truck.get("Date offloaded"): # and this truck isn't offloaded
                            all_dispatched_from_borders = False
                            break
            else: # No trucks in shipment
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

            submitted_str = date_submitted.strftime("%Y-%m-%d") if pd.notna(date_submitted) else "N/A"
            
            header = f"{status_icon} **{uid}** | 🏢 {client} | 🚚 {transporter} | 🛻 Trucks: {truck_count} | 🌍 **{shipment_geo_type}** | 🕒 {submitted_str} — *{label}*"

            # This is the individual shipment expander
            with st.expander(header, expanded=False): 
                # --- Shipment Financial & Time Details (Cross Border Only) ---
                if shipment_geo_type.lower() == "cross border":
                    st.markdown("#### ⚙️ Shipment Financial & Time Details")

                    # Data from Generator (main shipment data)
                    free_days_lp_gen = row.get("Free Days at Loading Point", 0)
                    # Assuming "Free days at offloading" for Cross Border refers to Free Days at Border
                    free_days_offloading_gen = row.get("Free Days at Border", 0)
                    demurrage_rate_gen = row.get("Demurrage Rate", 0.0)
                    payment_terms_gen = row.get("Payment Terms", "N/A")

                    # Calculated across all trucks within THIS specific shipment
                    current_shipment_total_demurrage_cost = 0.0
                    current_shipment_total_standing_time = 0.0
                    current_shipment_truck_count_for_avg_standing = 0

                    for truck in trucks: # 'trucks' here are already processed and contain calculated demurrage costs
                        current_shipment_total_demurrage_cost += truck.get("Demurrage cost at Loading Point", 0.0)
                        current_shipment_total_demurrage_cost += truck.get("Total Demurrage cost at Border", 0.0)

                        if pd.notna(truck.get("Days on site")):
                            current_shipment_total_standing_time += truck.get("Days on site", 0.0)
                            current_shipment_truck_count_for_avg_standing += 1

                    avg_standing_time_shipment = current_shipment_total_standing_time / current_shipment_truck_count_for_avg_standing \
                                                if current_shipment_truck_count_for_avg_standing > 0 else 0.0

                    st.write(f"**Free days at Loading Point:** {free_days_lp_gen} days")
                    st.write(f"**Free days at Offloading (Border):** {free_days_offloading_gen} days")
                    st.write(f"**Demurrage Rate:** R {demurrage_rate_gen:,.2f} per day")
                    st.write(f"**Payment Terms:** {payment_terms_gen}")
                    st.write(f"**Total Demurrage Cost for this Shipment:** R {current_shipment_total_demurrage_cost:,.2f}")
                    st.write(f"**Average Standing Time per Truck:** {avg_standing_time_shipment:.1f} days")
                    st.markdown("---") # Visual separator

                if not trucks:
                    st.info("No truck data found for this shipment.")
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


                    if active_trucks:
                        st.markdown("#### ✅ Active Trucks")

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
                                .apply(lambda x: f"{x:,.2f}" if pd.notna(x) else ("" if "cost" in col.lower() or "days" in col.lower() else ""))
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
                            key=f"active_editor_{file_number_key_prefix}{uid}", # Unique key for editor
                            hide_index=True,
                            column_config=column_config,
                            column_order=desired_columns
                        )
                    else:
                        st.info("No active trucks.")


                    if cancelled_trucks:
                        st.markdown("#### ❌ Cancelled Trucks")

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
                                .apply(lambda x: f"{x:,.2f}" if pd.notna(x) else ("" if "cost" in col.lower() or "days" in col.lower() else ""))
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
                            key=f"cancelled_editor_{file_number_key_prefix}{uid}", # Unique key for editor
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
                                st.markdown(f"##### {title}:") # Changed to h5 for nested hierarchy
                                for label, count in status_summary.items():
                                    st.markdown(f"- **{count} truck(s)** — {label}")
                            else:
                                st.info("No truck statuses to summarize.")
                        else:
                            st.info("No status column found to summarize.")

                    if not active_df.empty:
                        render_truck_status_summary(active_df, title="Active Truck Status Summary")
                    else:
                        st.info("No active trucks for status summary.")

                    # --- Original Individual Shipment Download Button ---
                    download_df_single_shipment = pd.DataFrame(trucks)
                    csv_data_single_shipment = download_df_single_shipment.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label="📄 Download Truck Data (CSV) for this Shipment",
                        data=csv_data_single_shipment,
                        file_name=f"{uid}_trucks.csv",
                        mime="text/csv",
                        key=f"dl_single_{file_number_key_prefix}{uid}"
                    )


    # Main loop for File Number grouping - NO NESTED EXPANDERS HERE
    for file_num in unique_file_numbers:
        file_shipments = df_processed[df_processed["File Number"] == file_num]
        
        # Calculate summary for the file number for the header
        file_total_shipments = file_shipments["Unique ID"].nunique()
        file_total_trucks = sum(len(s.get("Trucks", [])) for _, s in file_shipments.iterrows())
        
        # Using markdown for a prominent header instead of an expander
        st.markdown(f"---") # Separator between file numbers
        st.markdown(f"## 🗄️ File Number: {file_num} | Shipments: {file_total_shipments} | Trucks: {file_total_trucks}")
        
        # Render individual shipments for this file number directly below the header
        render_individual_shipment_overview(file_shipments, file_number_key_prefix=f"{file_num}_")

        # --- NEW: Consolidated Download for the entire File Number ---
        all_trucks_for_file = []
        for _, shipment_row in file_shipments.iterrows():
            for truck_data in shipment_row.get("Trucks", []):
                # Make a copy to avoid modifying original nested data
                truck_copy_for_excel = truck_data.copy() 
                # Add shipment-level details to each truck row for context in Excel
                truck_copy_for_excel["Parent Shipment ID"] = shipment_row.get("Unique ID")
                truck_copy_for_excel["Parent Shipment Type"] = shipment_row.get("Shipment Type")
                truck_copy_for_excel["Parent Shipment Client"] = shipment_row.get("Client")
                truck_copy_for_excel["Parent Shipment Transporter"] = shipment_row.get("Transporter")
                truck_copy_for_excel["Parent Shipment Date Submitted"] = format_date_for_display(shipment_row.get("Date Submitted"))
                truck_copy_for_excel["File Number"] = shipment_row.get("File Number") # Ensure File Number is on truck level

                # Flatten 'Trailers' and 'Borders' dictionaries into top-level columns for Excel export
                if "Trailers" in truck_copy_for_excel and isinstance(truck_copy_for_excel["Trailers"], dict):
                    for k, v in truck_copy_for_excel["Trailers"].items():
                        truck_copy_for_excel[f"Trailer - {k}"] = v
                    del truck_copy_for_excel["Trailers"] # Remove the nested dict

                if "Borders" in truck_copy_for_excel and isinstance(truck_copy_for_excel["Borders"], dict):
                    for k, v in truck_copy_for_excel["Borders"].items():
                        # Format border dates for Excel
                        if "arrival at" in k.lower() or "dispatch from" in k.lower():
                            truck_copy_for_excel[f"Border - {k}"] = format_date_for_display(v)
                        else:
                            truck_copy_for_excel[f"Border - {k}"] = v
                    del truck_copy_for_excel["Borders"] # Remove the nested dict

                all_trucks_for_file.append(truck_copy_for_excel)

        if all_trucks_for_file:
            # Create a DataFrame from the flattened truck data
            consolidated_truck_df = pd.DataFrame(all_trucks_for_file)

            # Re-apply date formatting for direct date columns that might not have been flattened
            date_cols_to_format = [
                "ETA", "Date Arrived", "Date offloaded", 
                "Arrived at Loading point", "Loaded Date", "Dispatch date"
            ]
            for col in date_cols_to_format:
                if col in consolidated_truck_df.columns:
                    consolidated_truck_df[col] = consolidated_truck_df[col].apply(format_date_for_display)

            preferred_order_for_excel = [
                "File Number", # Moved to be very prominent
                "Parent Shipment ID", "Parent Shipment Type", "Parent Shipment Client",
                "Parent Shipment Transporter", "Parent Shipment Date Submitted",
                "Unique ID", # The original shipment ID for the truck's parent (might be redundant with Parent Shipment ID)
                "Truck Number", "Horse Number"
            ]
            # Add all trailer and border specific columns dynamically
            trailer_cols = sorted([col for col in consolidated_truck_df.columns if col.startswith("Trailer - ")]) # Sort for consistency
            border_cols = sorted([col for col in consolidated_truck_df.columns if col.startswith("Border - ")]) # Sort for consistency
            
            # Add other standard truck columns
            other_cols = [col for col in consolidated_truck_df.columns if col not in preferred_order_for_excel + trailer_cols + border_cols]
            
            # Sort other_cols alphabetically for consistency
            other_cols.sort()

            final_excel_column_order = preferred_order_for_excel + trailer_cols + border_cols + other_cols
            
            # Filter to only include columns that actually exist in the DataFrame
            final_excel_column_order_existing = [col for col in final_excel_column_order if col in consolidated_truck_df.columns]

            consolidated_truck_df = consolidated_truck_df[final_excel_column_order_existing]


            csv_data_file = consolidated_truck_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label=f"⬇️ Download All Trucks for File {file_num} (CSV)",
                data=csv_data_file,
                file_name=f"File_{file_num}_All_Trucks.csv",
                mime="text/csv",
                key=f"dl_file_{file_num}"
            )
        else:
            st.info(f"No truck data available for File Number {file_num} to download.")