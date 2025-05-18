import streamlit as st
import pandas as pd
import uuid
from fpdf import FPDF
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from datetime import datetime

mongo_uri = st.secrets["mongo_uri"]
client = MongoClient(mongo_uri)
db = client["seamaster"]
shipments_collection = db["shipments"]

def render_generateID(df):
    st.markdown("### 🎯 Generate a New Shipment ID")

    # --- Initialize session state ---
    st.session_state.num_borders = st.session_state.get("num_borders", 3)
    current_names = st.session_state.get("border_names", [])
    st.session_state.border_names = current_names[:st.session_state.num_borders] + [""] * (
        st.session_state.num_borders - len(current_names)
    )

    # --- Input Forms ---
    st.subheader("Basic Shipment Information")
    col1, col2 = st.columns(2)
    with col1:
        transporter = st.text_input("Transporter Name", max_chars=50)
        cargo = st.text_input("Cargo Type", max_chars=50)
        truck_count = st.number_input("Number of Trucks", min_value=1, max_value=1000, value=1, step=1)
        loading_point = st.text_input("Loading Point", max_chars=100)
    with col2:
        file_number = st.text_input("File Number", max_chars=20)
        date_submitted_manual = st.date_input("Date of Submission", value=datetime.now().date())
        issued_by = st.text_input("Issued By", max_chars=50)

    st.subheader("Transporter and Agent Details")
    col3, col4 = st.columns(2)
    with col3:
        transporter_contact = st.text_input("Transporter Contact Details", max_chars=200)
        agent_details_country1 = st.text_input("Agent Details (Country 1)", max_chars=200)
        agent_details_country2 = st.text_input("Agent Details (Country 2)", max_chars=200)
    with col4:
        payment_terms = st.text_input("Payment Terms", max_chars=200)
        client_name = st.text_input("Client Name", max_chars=100)

    st.subheader("Load and Rate Details")
    col5, col6 = st.columns(2)
    with col5:
        load_start_date = st.date_input("Load Start Date", value=None)
        load_end_date = st.date_input("Load End Date", value=None)
        rate_per_ton = st.number_input("Rate per Ton", min_value=0.0, step=0.01, format="%.2f")
    with col6:
        truck_type = st.text_input("Truck Type", max_chars=50)
        free_days_border = st.number_input("Free Days at Border", min_value=0, value=0, step=1)
        free_days_loading = st.number_input("Free Days at Loading Point", min_value=0, value=0, step=1)

    st.subheader("Additional Truck Details")
    col7, col8 = st.columns(2)
    with col7:
        escorts_arranged = st.text_input("Escorts Arranged", max_chars=100)
        loading_capacity = st.text_input("Loading Capacity", max_chars=50)
    with col8:
        comments = st.text_area("Comments", max_chars=300)

    # --- Border Customization ---
    st.markdown("### 📜 Customize Border Names")
    cols = st.columns([1, 6, 1])
    with cols[0]:
        if st.button("➖ Remove Border") and st.session_state.num_borders > 0:
            st.session_state.num_borders -= 1
            st.rerun()
    with cols[2]:
        if st.button("➕ Add Border"):
            st.session_state.num_borders += 1
            st.rerun()

    borders = []
    for i in range(st.session_state.num_borders):
        border_name = st.text_input(f"Name for Border {i+1}", key=f"border_name_{i}")
        borders.append(border_name.strip())

    # --- Trailer Selection ---
    st.markdown("### 🚛 Trailer Setup")
    trailer_count = st.selectbox("Select number of trailers per truck", options=[1, 2])

    # --- Submit Form ---
    if st.button("🚀 Generate and Save"):
        required_fields = [transporter, cargo, loading_point, file_number, client_name]
        if not all(required_fields):
            st.warning("Please fill in all required fields.")
        else:
            unique_id = str(uuid.uuid4())
            trucks_array = []

            # Fixed trailer setup
            trailers = ["Trailer A"]
            if trailer_count == 2:
                trailers.append("Trailer B")

            for i in range(truck_count):
                truck_data = {
                    "Truck Number": i + 1,
                    "Truck": f"Truck-{i+1}",
                    "Trailers": {trailer: None for trailer in trailers},
                    "Driver": "",
                    "Passport": "",
                    "Contact": "",
                    "Driver contact number": "",
                    "Status": "Waiting to load",
                    "Current location": loading_point,
                    "Destination": loading_point,
                    "Rate per Ton": rate_per_ton,
                    "Free Days at Border": free_days_border,
                    "Free Days at Loading Point": free_days_loading,
                    "Client": client_name,
                    "Transporter": transporter,
                    "Cargo Type": cargo,
                    "Loading Capacity": loading_capacity,
                    "Load Location": loading_point,
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

                borders_data = {}
                for border in borders:
                    borders_data[f"Actual arrival at {border}"] = None
                    borders_data[f"Actual dispatch from {border}"] = None

                truck_data["Borders"] = borders_data
                
                trucks_array.append(truck_data)

            shipment_data = {
                "Unique ID": unique_id,
                "Date Submitted": datetime.combine(date_submitted_manual, datetime.min.time()),
                "Transporter": transporter,
                "Client": client_name,
                "Cargo Type": cargo,
                "Loading Point": loading_point,
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
                "Free Days at Loading Point": free_days_loading,
                "Borders": borders,
                "Trucks": trucks_array,
                "Trailers": {trailer: None for trailer in trailers},
            }

            # Save to MongoDB
            borders_data = {}
            for border in borders:
                borders_data[f"Actual arrival at {border}"] = None
                borders_data[f"Actual dispatch from {border}"] = None

            shipment_data["Borders"] = borders_data
            
            shipments_collection.insert_one(shipment_data)

            # Generate PDF (excluding Trucks and Borders)
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(200, 10, "Shipment Details", ln=True, align='C')
            pdf.ln(10)
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(90, 10, "Field", border=1, align='C')
            pdf.cell(90, 10, "Value", border=1, align='C')
            pdf.ln()

            pdf.set_font('Arial', '', 10)
            for key, value in shipment_data.items():
                if key not in ['Trucks', 'Borders']:
                    pdf.cell(90, 10, key, border=1)
                    pdf.cell(90, 10, str(value), border=1)
                    pdf.ln()

            pdf_output_path = "/tmp/shipment_document.pdf"
            pdf.output(pdf_output_path)

            with open(pdf_output_path, "rb") as f:
                st.download_button(
                    label="Download Shipment PDF",
                    data=f,
                    file_name="shipment_document.pdf",
                    mime="application/pdf"
                )

            st.success("Shipment details saved and PDF generated successfully!")