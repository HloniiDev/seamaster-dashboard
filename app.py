import streamlit as st
import pandas as pd
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import pandas as pd
import streamlit as st
from dashboard_view import render_dashboard
from generateId_view import render_generateID
from pastShipments_view import render_shipments

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

# --- Content Area based on View Selection ---
if st.session_state.get("view") == "Generate ID":
    render_generateID(df)

elif view == "All Past Shipment Metadata":
    render_shipments(df)

if view == "Dashboard":
    render_dashboard(df)