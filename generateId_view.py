import streamlit as st
import pandas as pd
import uuid
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from datetime import datetime
import fitz  # PyMuPDF
from io import BytesIO

# --- MongoDB Setup ---
try:
    mongo_uri = st.secrets["mongo_uri"]
    client = MongoClient(mongo_uri)
    db = client["seamaster"]
    shipments_collection = db["shipments"]
except ConnectionFailure as e:
    st.error(f"Could not connect to MongoDB: {e}")
    st.stop()


# --- Generate PDF with a Styled Table in the Template ---
def generate_pdf_with_template(template_path, shipment_data, unique_id):
    doc = fitz.open(template_path)
    page = doc[0]

    # Table layout
    x0, y0 = 50, 180
    col1_width = 150
    col2_width = 300
    row_height = 18
    font_size = 9

    # Exclude unwanted fields
    exclude_fields = [
        'Trucks', 'Borders', 'Unique ID', 'Trailers', '_id',
        'Agent Details (Country 1)', 'Agent Details (Country 2)', 'Free Days at Border', 'Free Days at Loading Point', 'Demurrage Rate',
    ]
    filtered_data = {
        k: v for k, v in shipment_data.items()
        if k not in exclude_fields and not isinstance(v, (list, dict))
    }

    # Header row
    header_rect = fitz.Rect(x0, y0, x0 + col1_width + col2_width, y0 + row_height)
    page.draw_rect(header_rect, color=(0, 0, 0), fill=(0.9, 0.9, 0.9))
    page.insert_textbox(header_rect, "Shipment Details", fontsize=10, fontname="helv", align=1)
    y0 += row_height

    # Draw each row with alternating colors and cell borders
    for idx, (key, value) in enumerate(filtered_data.items()):
        value = value.strftime("%Y-%m-%d") if isinstance(value, datetime) else str(value)

        key_rect = fitz.Rect(x0, y0, x0 + col1_width, y0 + row_height)
        value_rect = fitz.Rect(x0 + col1_width, y0, x0 + col1_width + col2_width, y0 + row_height)

        # Alternating row color
        fill_color = (0.96, 0.96, 0.96) if idx % 2 == 0 else (1, 1, 1)

        # Draw key cell
        page.draw_rect(key_rect, color=(0.7, 0.7, 0.7), fill=fill_color, width=0.5)
        page.insert_textbox(key_rect, key, fontsize=font_size, fontname="helv", align=0)

        # Draw value cell
        page.draw_rect(value_rect, color=(0.7, 0.7, 0.7), fill=fill_color, width=0.5)
        page.insert_textbox(value_rect, value, fontsize=font_size, fontname="helv", align=0)

        y0 += row_height

    # Save output
    output_stream = BytesIO()
    doc.save(output_stream)
    doc.close()
    output_stream.seek(0)
    return output_stream


# --- Streamlit Form Logic ---
def render_generateID(df):
    st.markdown("### 🎯 Generate a New Shipment ID")

    st.session_state.num_borders = st.session_state.get("num_borders", 3)
    current_names = st.session_state.get("border_names", [])
    st.session_state.border_names = current_names[:st.session_state.num_borders] + [""] * (
        st.session_state.num_borders - len(current_names)
    )

    st.subheader("Basic Shipment Information")
    col1, col2 = st.columns(2)
    with col1:
        transporter = st.text_input("Transporter Name")
        cargo = st.text_input("Cargo Type")
        truck_count = st.number_input("Number of Trucks", min_value=1, max_value=1000, value=1, step=1)
        loading_point = st.text_input("Loading Point")
        offloading_point = st.text_input("Offloading Point")
    with col2:
        file_number = st.text_input("File Number")
        date_submitted_manual = st.date_input("Date of Submission", value=datetime.now().date())
        issued_by = st.text_input("Issued By")
        tonnage = st.number_input("Tonnage", min_value=0.0, step=0.01, format="%.2f")

    st.subheader("Transporter and Agent Details")
    col3, col4 = st.columns(2)
    with col3:
        transporter_contact = st.text_input("Transporter Contact Details")
        transporter_details = st.text_area("Transporter Additional Details")
        agent_details_country1 = st.text_input("Agent Details (Country 1)")
        agent_details_country2 = st.text_input("Agent Details (Country 2)")
    with col4:
        payment_terms = st.text_input("Payment Terms")
        client_name = st.text_input("Client Name")

    st.subheader("Load and Rate Details")
    col5, col6 = st.columns(2)
    with col5:
        load_start_date = st.date_input("Load Start Date", value=None)
        load_end_date = st.date_input("Load End Date", value=None)
        rate_per_ton = st.number_input("Rate per Ton", min_value=0.0, step=0.01, format="%.2f")
    with col6:
        truck_type = st.text_input("Truck Type")
        free_days_border = st.number_input("Free Days at Border", min_value=0)
        free_days_loading = st.number_input("Free Days at Loading Point", min_value=0)
        demurrage_rate = st.number_input("Demurrage Rate", min_value=0.0, step=0.01, format="%.2f")

    st.subheader("Additional Truck Details")
    col7, col8 = st.columns(2)
    with col7:
        escorts_arranged = st.text_input("Escorts Arranged")
        loading_capacity = st.text_input("Loading Capacity")
    with col8:
        comments = st.text_area("Comments")

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

    borders = [st.text_input(f"Name for Border {i+1}", key=f"border_name_{i}").strip()
               for i in range(st.session_state.num_borders)]

    st.markdown("### 🚛 Trailer Setup")
    trailer_count = st.selectbox("Select number of trailers per truck", options=[1, 2])

    if st.button("🚀 Generate and Save"):
        required_fields = [transporter, cargo, loading_point, offloading_point, file_number, client_name]
        if not all(required_fields):
            st.warning("Please fill in all required fields.")
        else:
            unique_id = str(uuid.uuid4())
            trailers = ["Trailer A"] + (["Trailer B"] if trailer_count == 2 else [])
            trucks_array = []

            for i in range(truck_count):
                truck_data = {
                    "Truck Number": i + 1,
                    "Truck": f"Truck-{i+1}",
                    "Trailers": {t: None for t in trailers},
                    "Driver": "", "Passport": "", "Contact": "", "Driver contact number": "",
                    "Status": "Booked", "Current location": loading_point,
                    "Destination": offloading_point,
                    "Rate per Ton": rate_per_ton,
                    "Free Days at Border": free_days_border,
                    "Free Days at Loading Point": free_days_loading,
                    "Demurrage Rate": demurrage_rate,
                    "Client": client_name, "Transporter": transporter,
                    "Cargo Type": cargo, "Loading Capacity": loading_capacity,
                    "Load Location": loading_point, "Offloading Point": offloading_point,
                    "Tonnage": tonnage, "Transporter Details": transporter_details,
                    "Truck Count": truck_count, "File Number": file_number,
                    "Date": datetime.combine(date_submitted_manual, datetime.min.time()),
                    "Issued By": issued_by, "Transporter Contact Details": transporter_contact,
                    "Agent Details (Country 1)": agent_details_country1,
                    "Agent Details (Country 2)": agent_details_country2,
                    "Payment Terms": payment_terms,
                    "Load Start Date": datetime.combine(load_start_date, datetime.min.time()) if load_start_date else None,
                    "Load End Date": datetime.combine(load_end_date, datetime.min.time()) if load_end_date else None,
                    "Truck Type": truck_type, "Escorts arranged": escorts_arranged,
                    "Comments": comments
                }
                truck_data["Borders"] = {f"Actual arrival at {b}": None for b in borders}
                truck_data["Borders"].update({f"Actual dispatch from {b}": None for b in borders})
                trucks_array.append(truck_data)

            shipment_data = {
                "Unique ID": unique_id,
                "Date Submitted": datetime.combine(date_submitted_manual, datetime.min.time()),
                "Transporter": transporter, "Transporter Details": transporter_details, "Client": client_name, "Cargo Type": cargo,
                "Loading Point": loading_point, "Offloading Point": offloading_point,
                "Tonnage": tonnage,
                "File Number": file_number, "Issued By": issued_by,
                "Truck Count": truck_count, "Transporter Contact Details": transporter_contact,
                "Agent Details (Country 1)": agent_details_country1,
                "Agent Details (Country 2)": agent_details_country2,
                "Payment Terms": payment_terms,
                "Load Start Date": datetime.combine(load_start_date, datetime.min.time()) if load_start_date else None,
                "Load End Date": datetime.combine(load_end_date, datetime.min.time()) if load_end_date else None,
                "Rate per Ton": rate_per_ton, "Truck Type": truck_type,
                "Free Days at Border": free_days_border,
                "Free Days at Loading Point": free_days_loading,
                "Demurrage Rate": demurrage_rate,
                "Borders": borders,
                "Trucks": trucks_array,
                "Trailers": {t: None for t in trailers}
            }

            # Save to MongoDB
            shipments_collection.insert_one(shipment_data)

            # Generate and stream the PDF
            pdf_stream = generate_pdf_with_template(
                template_path="transport_order_template.pdf",
                shipment_data=shipment_data,
                unique_id=unique_id
            )

            st.download_button(
                label="Download Shipment PDF",
                data=pdf_stream,
                file_name=f"shipment_{unique_id}.pdf",
                mime="application/pdf"
            )

            st.success("Shipment saved and PDF generated successfully!")