import streamlit as st
import pandas as pd
import os
from datetime import datetime
import uuid
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import pandas as pd # Ensure pandas is imported if not already (it was)
import streamlit as st
from fpdf import FPDF
from datetime import datetime
import uuid


# --- Set Page Config (MUST be the first Streamlit command) ---
# This should be the very first Streamlit command called.
st.set_page_config(page_title="Seamaster Dashboard", layout="wide")


# --- MongoDB Connection ---
mongo_uri = st.secrets["mongo_uri"]
client = MongoClient(mongo_uri)
db = client["seamaster"]
shipments_collection = db["shipments"]

@st.cache_resource
def init_connection():
    """Initializes and caches the MongoDB connection."""
    try:
        # Ensure secrets are available
        if "mongo_uri" not in st.secrets:
             st.error("🚫 MongoDB URI not found in Streamlit secrets.")
             return None

        # Use the connection string from secrets
        client = MongoClient(st.secrets["mongo_uri"])

        # It confirms that the client can connect to MongoDB.
        client.admin.command('ping')
        st.success("✅ Connected to MongoDB!")
        return client

    except ConnectionFailure as e:
        st.error(f"🚫 Could not connect to MongoDB: {e}")
        st.info("Please check your MongoDB connection string and network access.")
        return None
    except Exception as e:
         st.error(f"🚫 An unexpected error occurred during MongoDB connection: {e}")
         return None


# Attempt to initialize connection immediately when the script runs
client = init_connection()

# Initialize database and collection variables;
db = None
collection = None

if client is not None:
    try:
        db = client.get_database("seamaster")
        collection = db.get_collection("shipments")
        # print(f"Collection found: {collection.name}") # For debugging
    except Exception as e:
        st.error(f"🚫 Error accessing database or collection: {e}")
        db = None
        collection = None

# --- Data Loading from MongoDB ---
def load_data():
    """Loads data from the MongoDB collection into a pandas DataFrame."""
    if collection is None:
        return pd.DataFrame()  # Return an empty DataFrame if no connection/collection

    try:
        # Retrieve all documents from the collection
        items = collection.find()
        # Convert the cursor to a list and then to a DataFrame
        df = pd.DataFrame(list(items))

        # --- Data Cleaning and Type Conversion ---
        if not df.empty:
            # Convert MongoDB ObjectId to string for easier handling/display
            if '_id' in df.columns:
                 df['_id'] = df['_id'].astype(str)

            # List of columns expected to contain dates/datetimes
            date_cols = [
                "Date Submitted", "Date", "Load Start Date", "Load End Date",
                "ETA", "Actual arrival date", "Actual loading date",
                "Offloading arrival", "Date offloaded"
                ] + [col for col in df.columns if "arrival at" in col.lower() or "dispatch from" in col.lower()] # Include dynamic border columns

            for col in date_cols:
                if col in df.columns:
                    # Convert to datetime, coercing errors (invalid dates become NaT)
                    df[col] = pd.to_datetime(df[col], errors="coerce")

            # List of columns expected to contain numeric values
            numeric_cols = [
                "Truck Count", "Truck Number", "Load capacity",
                "Gross weight", "Net weight", "Standing time billable days",
                "Standing time charges", "Whiskey in", "Whiskey out",
                "Standing days", "Billable standing days", "Rate per Ton",
                "Free Days at Border", "Free Days at Offloading Point", "Days on site"
                ]

            for col in numeric_cols:
                if col in df.columns:
                     # Convert to numeric, coercing errors (invalid values become NaN)
                     df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    except Exception as e:
        st.error(f"⚠️ Error loading data from MongoDB: {e}")
        return pd.DataFrame()

# --- Data Insertion into MongoDB ---
def insert_shipment_data(row_dict):
    """Inserts a single document into the MongoDB collection."""
    # Check if the collection object is available
    if collection is None:
        st.error("🚫 Not connected to MongoDB. Cannot save data.")
        return False # Indicate failure

    try:
        # Ensure the MongoDB primary key (_id) is not in the dictionary,
        # as MongoDB will generate it automatically.
        if '_id' in row_dict:
             del row_dict['_id']

        # Perform the insertion
        insert_result = collection.insert_one(row_dict)

        # Check if insertion was acknowledged and an ID was generated
        if insert_result.acknowledged:
            # st.success(f"✅ Shipment data saved to MongoDB! (ID: {insert_result.inserted_id})")
            return True # Indicate success
        else:
            st.error("🚨 Error saving data to MongoDB: Insert not acknowledged.")
            return False # Indicate failure

    except Exception as e:
        st.error(f"🚨 Error saving data to MongoDB: {e}")
        return False # Indicate failure

# --- Unique ID Generation ---
def generate_unique_id(transporter, cargo, file_number):
    """Generates a simple unique ID based on input and current data count."""
    latest_df = load_data() # Loads potentially cached data unless cache is cleared/invalidated
    date_str = datetime.now().strftime("%Y%m%d")

    suffix = str(len(latest_df) + 1).zfill(3)

    trans_abbrev = transporter[:3].upper() if transporter and len(transporter) >= 3 else "TRN" # Default if too short/empty
    cargo_abbrev = cargo[:3].upper() if cargo and len(cargo) >= 3 else "CAR" # Default if too short/empty
    file_abbrev = file_number if file_number else "FIL" # Default if empty

    # Sanitize file_number part - keep only alphanumeric characters
    file_abbrev_sanitized = ''.join(filter(str.isalnum, file_abbrev)) or "000" # Ensure it's not empty after filtering

    # Combine parts for the main abbreviation block
    abbrev_block = f"{trans_abbrev}{cargo_abbrev}{file_abbrev_sanitized}"[:10]

    return f"{abbrev_block}-{date_str}-{suffix}"


def convert_dates(obj):
    if isinstance(obj, dict):
        return {k: convert_dates(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_dates(i) for i in obj]
    elif isinstance(obj, datetime.date) and not isinstance(obj, datetime.datetime):
        return datetime.datetime(obj.year, obj.month, obj.day)
    return obj
# --- Streamlit App Layout ---
# The page title is already set at the very top using st.set_page_config
st.title("📦 Seamaster Shipment Dashboard")

# This function is called every time the script reruns
df = load_data()

# --- Sidebar Navigation ---
st.session_state.setdefault("view", "Dashboard")

with st.sidebar:
    st.markdown("### 🥝 Navigation")
    btn_style = {"use_container_width": True}
    if st.button("Dashboard", **btn_style):
        st.session_state.view = "Dashboard"
    if st.button("Generate ID", **btn_style):
        st.session_state.view = "Generate ID"
    if st.button("All Past Shipment Metadata", **btn_style):
        st.session_state.view = "All Past Shipment Metadata"

view = st.session_state.view
st.title(f"📍 {view}")


def generate_unique_id(transporter, cargo, file_number):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{transporter[:3].upper()}-{cargo[:3].upper()}-{file_number}-{timestamp}"

# --- Content Area based on View Selection ---
# --- Streamlit Setup ---
if st.session_state.get("view") == "Generate ID":
    st.markdown("### 🎯 Generate a New Shipment ID")

    # --- Initialize session state ---
    st.session_state.num_borders = st.session_state.get("num_borders", 3)
    current_names = st.session_state.get("border_names", [])
    st.session_state.border_names = current_names[:st.session_state.num_borders] + [""] * (
        st.session_state.num_borders - len(current_names)
    )

    st.session_state.num_trailers = st.session_state.get("num_trailers", 2)

    # --- Input Forms ---
    st.subheader("Basic Shipment Information")
    col1, col2 = st.columns(2)
    with col1:
        transporter = st.text_input("Transporter Name", max_chars=50, key="transporter_input")
        cargo = st.text_input("Cargo Type", max_chars=50, key="cargo_input")
        load_point = st.text_input("Loading Point", max_chars=50, key="load_point_input")
        offloading_point = st.text_input("Offloading Point", max_chars=100, key="offloading_point_input")
    with col2:
        file_number = st.text_input("File Number", max_chars=20, key="file_number_input")
        date_submitted_manual = st.date_input("Date of Submission", value=datetime.now().date(), key="date_submitted_manual_input")
        issued_by = st.text_input("Issued By", max_chars=50, key="issued_by_input")
        truck_count = st.number_input("Number of Trucks", min_value=1, max_value=1000, value=1, step=1, key="truck_count_input")

    st.subheader("Transporter and Agent Details")
    col3, col4 = st.columns(2)
    with col3:
        transporter_contact = st.text_input("Transporter Contact Details", max_chars=200, key="transporter_contact_input")
        agent_details_country1 = st.text_input("Agent Details (Country 1)", max_chars=200, key="agent_country1_input")
        agent_details_country2 = st.text_input("Agent Details (Country 2)", max_chars=200, key="agent_country2_input")
    with col4:
        payment_terms = st.text_input("Payment Terms", max_chars=200, key="payment_terms_input")
        client_name = st.text_input("Client Name", max_chars=100, key="client_name_input")

    st.subheader("Load and Rate Details")
    col5, col6 = st.columns(2)
    with col5:
        load_start_date = st.date_input("Load Start Date", value=None, key="load_start_date_input")
        load_end_date = st.date_input("Load End Date", value=None, key="load_end_date_input")
        rate_per_ton = st.number_input("Rate per Ton", min_value=0.0, step=0.01, format="%.2f", key="rate_per_ton_input")
    with col6:
        truck_type = st.text_input("Truck Type", max_chars=50, key="truck_type_input")
        free_days_border = st.number_input("Free Days at Border", min_value=0, value=0, step=1, key="free_days_border_input")
        free_days_offloading = st.number_input("Free Days at Offloading Point", min_value=0, value=0, step=1, key="free_days_offloading_input")

    st.subheader("Additional Truck Details")
    col7, col8 = st.columns(2)
    with col7:
        escorts_arranged = st.text_input("Escorts Arranged", max_chars=100, key="escorts_input")
        loading_capacity = st.text_input("Loading Capacity", max_chars=50, key="loading_capacity_input")
    with col8:
        comments = st.text_area("Comments", max_chars=300, key="comments_input")

    # --- Border Customization ---
    st.markdown("### 📜 Customize Border Names")
    cols = st.columns([1, 6, 1])
    with cols[0]:
        if st.button("➖ Remove Border", key="dec_borders") and st.session_state.num_borders > 0:
            st.session_state.num_borders -= 1
            st.rerun()
    with cols[2]:
        if st.button("➕ Add Border", key="inc_borders"):
            st.session_state.num_borders += 1
            st.rerun()

    borders = []
    for i in range(st.session_state.num_borders):
        border_name = st.text_input(f"Name for Border {i+1}", key=f"border_name_{i}")
        borders.append(border_name.strip())

    # --- Trailer Customization ---
    trailers = []
    for i in range(st.session_state.num_trailers):
        trailer_type = st.text_input(f"Trailer {i+1} Type", key=f"trailer_type_{i}")
        trailers.append(trailer_type.strip())

    # --- Submit Form ---
    if st.button("🚀 Generate and Save", key="generate_save_button"):
        required_fields = [transporter, cargo, load_point, offloading_point, file_number, client_name]
        if not all(required_fields):
            st.warning("Please fill in all required fields.")
        else:
            # Generate Unique ID
            unique_id = str(uuid.uuid4())

            trucks_array = []

            for i in range(truck_count):
                truck_data = {
                    "Truck Number": i + 1,
                    "Truck": f"Truck-{i+1}",
                    "Trailers": trailers,
                    "Trailer Type": trailers,
                    "Driver": "",
                    "Passport": "",
                    "Contact": "",
                    "Driver contact number": "",
                    "Truck status": "Waiting to load",
                    "Current location": load_point,
                    "Destination": offloading_point,
                    "Rate per Ton": rate_per_ton,
                    "Free Days at Border": free_days_border,
                    "Free Days at Offloading Point": free_days_offloading,
                    "Client": client_name,
                    "Transporter": transporter,
                    "Cargo Type": cargo,
                    "Loading Point": load_point,
                    "Truck Count": truck_count,
                    "File Number": file_number,
                    "Date": datetime.combine(date_submitted_manual, datetime.min.time()),
                    "Issued By": issued_by,
                    "Transporter Contact Details": transporter_contact,
                    "Agent Details (Country 1)": agent_details_country1,
                    "Agent Details (Country 2)": agent_details_country2,
                    "Payment Terms": payment_terms,
                    "Load Start Date": datetime.combine(load_start_date, datetime.min.time()) if load_start_date else None,
                    "Load End Date": datetime.combine(load_end_date, datetime.min.time()) if load_end_date else None,
                    "Truck Type": truck_type,
                    "Escorts arranged": escorts_arranged,
                    "Comments": comments
                }

                for border in borders:
                    truck_data[f"Actual arrival at {border}"] = None
                    truck_data[f"Actual dispatch from {border}"] = None

                trucks_array.append(truck_data)

            shipment_data = {
                "Unique ID": unique_id,
                "Date Submitted": datetime.combine(date_submitted_manual, datetime.min.time()),
                "Transporter": transporter,
                "Client": client_name,
                "Cargo Type": cargo,
                "Loading Point": load_point,
                "Offloading Point": offloading_point,
                "File Number": file_number,
                "Issued By": issued_by,
                "Truck Count": truck_count,
                "Transporter Contact Details": transporter_contact,
                "Agent Details (Country 1)": agent_details_country1,
                "Agent Details (Country 2)": agent_details_country2,
                "Payment Terms": payment_terms,
                "Load Start Date": datetime.combine(load_start_date, datetime.min.time()) if load_start_date else None,
                "Load End Date": datetime.combine(load_end_date, datetime.min.time()) if load_end_date else None,
                "Rate per Ton": rate_per_ton,
                "Truck Type": truck_type,
                "Free Days at Border": free_days_border,
                "Free Days at Offloading Point": free_days_offloading,
            }

            # Save the full shipment data to MongoDB
            # shipments_collection.insert_one(shipment_data)

            # --- Generate PDF (excluding Trucks and Trailers) ---
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(200, 10, "Shipment Details", ln=True, align='C')

            # Add table header
            pdf.ln(10)
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(90, 10, "Field", border=1, align='C')
            pdf.cell(90, 10, "Value", border=1, align='C')
            pdf.ln()

            # Add shipment info to PDF table (excluding 'Trucks' and 'Trailers')
            pdf.set_font('Arial', '', 10)
            for key, value in shipment_data.items():
                if key not in ['Trucks', 'Trucks Count', 'Trailers']:  # Exclude trucks and trailers
                    pdf.cell(90, 10, key, border=1)
                    pdf.cell(90, 10, str(value), border=1)
                    pdf.ln()

            # Save the PDF file to a valid path
            pdf_output_path = "/tmp/shipment_document.pdf"  # Define the file path here
            pdf.output(pdf_output_path)

            # Provide download link for the generated PDF
            with open(pdf_output_path, "rb") as f:
                st.download_button(
                    label="Download Shipment PDF",
                    data=f,
                    file_name="shipment_document.pdf",
                    mime="application/pdf"
                )

            st.success("Shipment details saved and PDF generated successfully!")

elif view == "All Past Shipment Metadata":
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

if view == "Dashboard":
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

    # Calculate the total trucks, charges, and days on site
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


    # CSS for styling
    st.markdown("""
    <style>
        /* Highlight selected rows */
        tr[data-testid='stDataFrameRowSelected'] {
            background-color: #e6f3ff !important;
        }
        
        /* Style for cancelled trucks */
        tr.cancelled-row {
            background-color: #f5f5f5 !important;
            color: #999 !important;
            text-decoration: line-through;
        }
        
        /* Style for the Cancel Truck button */
        button.cancel-btn {
            background-color: #ff4b4b;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 2px 8px;
            cursor: pointer;
            font-size: 12px;
        }
        
        button.cancel-btn:hover {
            background-color: #ff2b2b;
        }
        
        /* Make sure rows are selectable */
        .stDataFrame [data-testid='stDataFrameRow'] {
            cursor: pointer;
        }
    </style>
    """, unsafe_allow_html=True)

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

    # Status Icon and Label
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
            # Create a copy of trucks to avoid modifying the original
            trucks_data = [truck.copy() for truck in trucks]
            
            # Initialize IsCancelled if not exists
            for truck in trucks_data:
                if "IsCancelled" not in truck:
                    truck["IsCancelled"] = False
            
            # Separate cancelled and active trucks
            cancelled_trucks = [truck for truck in trucks_data if truck.get("IsCancelled")]
            active_trucks = [truck for truck in trucks_data if not truck.get("IsCancelled")]
            
            # Combine with cancelled trucks at the bottom
            sorted_trucks = active_trucks + cancelled_trucks
            trucks_df = pd.DataFrame(sorted_trucks)
            
            # Format date/time columns
            date_cols = [col for col in trucks_df.columns if any(s in col.lower() for s in ["date", "arrival", "dispatch", "eta"])]
            for col in date_cols:
                if pd.api.types.is_datetime64_any_dtype(trucks_df[col]):
                    trucks_df[col] = trucks_df[col].dt.strftime("%Y-%m-%d %H:%M").fillna("")
                else:
                    trucks_df[col] = trucks_df[col].astype(str).replace('nan', '')
            
            # Format numbers
            num_cols = [col for col in trucks_df.columns if any(x in col.lower() for x in ["ton", "days", "charges", "weight"])]
            for col in num_cols:
                if pd.api.types.is_numeric_dtype(trucks_df[col]):
                    trucks_df[col] = trucks_df[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "")
                else:
                    trucks_df[col] = trucks_df[col].astype(str).replace("nan", "")
            
            # Create a unique key for this widget
            editor_key = f"truck_editor_{uid}"
            
            # Display the editable dataframe
            edited_df = st.data_editor(
                trucks_df,
                use_container_width=True,
                key=editor_key,
                disabled=[col for col in trucks_df.columns if col != "Action"],
                hide_index=True,
                column_config={
                    "Action": st.column_config.Column(
                        "Action",
                        width="small",
                        disabled=False
                    ),
                    "IsCancelled": st.column_config.CheckboxColumn(
                        "Cancel",
                        help="Is this truck cancelled?",
                        default=False,
                    )
                }
            )
            
            # Apply row styling for cancelled trucks
            st.markdown(
                f"""
                <script>
                document.addEventListener('DOMContentLoaded', function() {{
                    const table = document.querySelector('[data-testid="stDataFrame-container"]');
                    if (table) {{
                        const rows = table.querySelectorAll('[data-testid="stDataFrameRow"]');
                        rows.forEach((row, index) => {{
                            const isCancelled = {edited_df['IsCancelled'].tolist()}[index];
                            if (isCancelled) {{
                                row.classList.add('cancelled-row');
                            }}
                            // Make entire row clickable
                            row.style.cursor = 'pointer';
                            row.addEventListener('click', (e) => {{
                                if (!e.target.closest('button')) {{
                                    rows.forEach(r => r.classList.remove('row-selected'));
                                    row.classList.add('row-selected');
                                }}
                            }});
                        }});
                    }}
                }});
                </script>
                """,
                unsafe_allow_html=True
            )
            
            # Check for button clicks
            if editor_key in st.session_state:
                for idx, row in st.session_state[editor_key]['edited_rows'].items():
                    if "Action" in row and row["Action"] == "🚫 Cancel":
                        if idx < len(trucks_data):
                            trucks_data[idx]["IsCancelled"] = True
                            st.rerun()
            
            # --- Truck Status Summary ---
            status_col = None
            for candidate in ["Truck status", "Status", "Truck Status"]:
                if candidate in trucks_df.columns:
                    status_col = candidate
                    break

            if status_col:
                # Filter out cancelled trucks
                non_cancelled_trucks = trucks_df[trucks_df["IsCancelled"] == False]

                status_summary = non_cancelled_trucks[status_col].value_counts()
                
                if not status_summary.empty:
                    st.markdown("### 📊 Truck Status Summary:")
                    for label, count in status_summary.items():
                        st.markdown(f"- **{count} truck(s)** — {label}")
            else:
                st.info("No status column found to summarize.")
            
            # Update button if any changes were made
            # if any(truck.get("IsCancelled") for truck in trucks_data):
            #     if st.button(f"💾 Save Changes for {uid}", key=f"save_{uid}"):
            #         # Here you would update your database
            #         # Example: update_shipment_in_db(uid, trucks_data)
            #         st.success(f"Changes for shipment {uid} saved successfully!")
            #         st.rerun()
            
            # Download Button
            csv_data = edited_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label=f"📄 Download Truck Data (CSV)",
                data=csv_data,
                file_name=f"{uid}_trucks.csv",
                mime="text/csv",
                key=f"dl_{uid}"
            )