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
    # TRAILERS
    trailers = []
    # for i in range(st.session_state.num_trailers):
    #     trailer_type = st.text_input(f"Trailer {i+1} Type", key=f"trailer_type_{i}")
    #     trailers.append(trailer_type.strip())

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

            # Add Borders and Trucks before saving to DB
            shipment_data["Borders"] = borders
            shipment_data["Trucks"] = trucks_array

            # Save the full shipment data to MongoDB
            shipments_collection.insert_one(shipment_data)

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

            # Add shipment info to PDF table (excluding 'Trucks', 'Trailers', and 'Borders')
            pdf.set_font('Arial', '', 10)
            for key, value in shipment_data.items():
                if key not in ['Trucks', 'Trucks Count', 'Trailers', 'Borders']:
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