import streamlit as st
import pandas as pd
from datetime import datetime
import io
import fitz  # PyMuPDF
from io import BytesIO

# --- Generate PDF with a Styled Table in the Template (COPIED FROM YOUR FIRST FILE) ---
def generate_pdf_with_template(template_path, shipment_data, unique_id):
    """
    Generates a PDF based on a template, populating a styled table with shipment data.
    """
    try:
        doc = fitz.open(template_path)
    except fitz.FileNotFoundError:
        st.error(f"PDF template file not found at: {template_path}")
        return None # Return None if template is not found

    page = doc[0]

    # Table layout dimensions
    x0, y0 = 50, 180  # Starting coordinates for the table
    col1_width = 150
    col2_width = 300
    row_height = 18
    font_size = 9

    # Fields to exclude from the PDF table (UPDATED EXCLUSION LIST)
    exclude_fields = [
        'Trucks', 'Borders', 'Unique ID', 'Trailers', '_id',
        'Agent Details (Country 1)', 'Agent Details (Country 2)', 'Free Days at Border', 'Free Days at Loading Point', 'Demurrage Rate',
        'Escorts arranged', 'Loading Capacity', 'Comments' # These are now excluded
    ]

    # Filter data: exclude unwanted fields and non-scalar types (lists/dicts)
    filtered_data = {
        k: v for k, v in shipment_data.items()
        if k not in exclude_fields and not isinstance(v, (list, dict))
    }

    # Draw Header row for the table
    header_rect = fitz.Rect(x0, y0, x0 + col1_width + col2_width, y0 + row_height)
    page.draw_rect(header_rect, color=(0, 0, 0), fill=(0.9, 0.9, 0.9)) # Black border, light gray fill
    page.insert_textbox(header_rect, "Shipment Details", fontsize=10, fontname="helv", align=fitz.TEXT_ALIGN_CENTER) # Align text to center
    y0 += row_height

    # Draw each data row with alternating colors and cell borders
    for idx, (key, value) in enumerate(filtered_data.items()):
        # Format datetime objects to string
        value_str = value.strftime("%Y-%m-%d") if isinstance(value, datetime) else str(value)

        # Define rectangles for key and value cells
        key_rect = fitz.Rect(x0, y0, x0 + col1_width, y0 + row_height)
        value_rect = fitz.Rect(x0 + col1_width, y0, x0 + col1_width + col2_width, y0 + row_height)

        # Alternating row background color
        fill_color = (0.96, 0.96, 0.96) if idx % 2 == 0 else (1, 1, 1) # Light gray or white

        # Draw key cell
        page.draw_rect(key_rect, color=(0.7, 0.7, 0.7), fill=fill_color, width=0.5) # Gray border, fill color
        page.insert_textbox(key_rect, key, fontsize=font_size, fontname="helv", align=fitz.TEXT_ALIGN_LEFT) # Align text to left

        # Draw value cell
        page.draw_rect(value_rect, color=(0.7, 0.7, 0.7), fill=fill_color, width=0.5) # Gray border, fill color
        page.insert_textbox(value_rect, value_str, fontsize=font_size, fontname="helv", align=fitz.TEXT_ALIGN_LEFT) # Align text to left

        y0 += row_height # Move down for the next row

    # Save the modified PDF to a BytesIO object
    output_stream = BytesIO()
    doc.save(output_stream)
    doc.close()
    output_stream.seek(0) # Reset stream position to the beginning
    return output_stream

def render_shipments(df):
    st.markdown("## 📁 All Past Shipment IDs (Metadata View)")

    if df.empty:
        st.info("No shipment data available in the database.")
        return

    # Handle 'Date Submitted' for display and sorting
    if "Date Submitted" in df.columns:
        df["Date Submitted"] = pd.to_datetime(df["Date Submitted"], errors="coerce")
        df_valid_dates = df.dropna(subset=["Date Submitted"]).copy()
    else:
        df_valid_dates = df.copy()

    if "Unique ID" in df_valid_dates.columns:
        df_valid_dates['Unique ID'] = df_valid_dates['Unique ID'].astype(str)

        if not df_valid_dates.empty:
            # Get the latest entry for each Unique ID
            metadata_table = (
                df_valid_dates.sort_values("Date Submitted", ascending=False)
                .groupby("Unique ID").first()
                .reset_index()
            )
        else:
            metadata_table = pd.DataFrame(columns=df_valid_dates.columns)

        display_cols = [
            "Unique ID", "Date Submitted", "Transporter", "Client",
            "Cargo Type", "Loading Point", "File Number", "Truck Count"
        ]
        display_cols_present = [col for col in display_cols if col in metadata_table.columns]
        metadata_table_display = metadata_table[display_cols_present].copy()

        if "Date Submitted" in metadata_table_display.columns:
            metadata_table_display["Date Submitted"] = (
                metadata_table_display["Date Submitted"]
                .dt.strftime("%Y-%m-%d %H:%M").fillna("")
            )

        metadata_table_display.index += 1
        st.dataframe(metadata_table_display, use_container_width=True)
        st.markdown("---")

        # Manual input for Shipment ID
        manual_id = st.text_input("Enter Shipment ID to generate PDF", key="manual_shipment_id_input")

        if manual_id:
            if st.button("Generate PDF", key="manual_generate_pdf_button"):
                shipment_data_row = df[df["Unique ID"].astype(str) == manual_id].copy()

                if not shipment_data_row.empty:
                    # Get the latest shipment data for the given ID
                    shipment_row = (
                        shipment_data_row.sort_values("Date Submitted", ascending=False).iloc[0]
                    )

                    # Extract all relevant fields into a dictionary for PDF generation
                    shipment_data = {
                        "Unique ID": shipment_row.get("Unique ID", ""),
                        "Date Submitted": shipment_row.get("Date Submitted", ""),
                        "Transporter": shipment_row.get("Transporter", ""),
                        "Transporter Details": shipment_row.get("Transporter Details", ""),
                        "Client": shipment_row.get("Client", ""),
                        "Cargo Type": shipment_row.get("Cargo Type", ""),
                        "Loading Point": shipment_row.get("Loading Point", ""),
                        "Offloading Point": shipment_row.get("Offloading Point", ""),
                        "Tonnage": shipment_row.get("Tonnage", ""),
                        "File Number": shipment_row.get("File Number", ""),
                        "Issued By": shipment_row.get("Issued By", ""),
                        "Truck Count": shipment_row.get("Truck Count", ""),
                        "Transporter Contact Details": shipment_row.get("Transporter Contact Details", ""),
                        "Agent Details (Country 1)": shipment_row.get("Agent Details (Country 1)", ""),
                        "Agent Details (Country 2)": shipment_row.get("Agent Details (Country 2)", ""),
                        "Payment Terms": shipment_row.get("Payment Terms", ""),
                        "Load Start Date": shipment_row.get("Load Start Date", ""),
                        "Load End Date": shipment_row.get("Load End Date", ""),
                        "Rate per Ton": shipment_row.get("Rate per Ton", ""),
                        "Truck Type": shipment_row.get("Truck Type", ""),
                        "Free Days at Border": shipment_row.get("Free Days at Border", ""),
                        "Free Days at Loading Point": shipment_row.get("Free Days at Loading Point", ""),
                        "Demurrage Rate": shipment_row.get("Demurrage Rate", ""),
                        # These fields are included here in the dict but will be filtered out by `generate_pdf_with_template`
                        "Escorts arranged": shipment_row.get("Escorts arranged", ""),
                        "Loading Capacity": shipment_row.get("Loading Capacity", ""),
                        "Comments": shipment_row.get("Comments", ""),
                        # Ensure lists/dicts are handled appropriately if you want them in PDF
                        # For now, they are excluded by generate_pdf_with_template's filter
                        "Borders": shipment_row.get("Borders", []),
                        "Trucks": shipment_row.get("Trucks", []),
                        "Trailers": shipment_row.get("Trailers", {}),
                    }

                    # --- UNIFIED PDF GENERATION CALL ---
                    pdf_stream = generate_pdf_with_template(
                        template_path="transport_order_template.pdf",
                        shipment_data=shipment_data,
                        unique_id=manual_id # Pass manual_id as unique_id
                    )

                    if pdf_stream: # Only proceed if PDF generation was successful (template found)
                        st.download_button(
                            label="Download Shipment PDF",
                            data=pdf_stream,
                            file_name=f"shipment_{manual_id}.pdf",
                            mime="application/pdf",
                            key=f"download_manual_pdf_{manual_id}" # Use a unique key for the button
                        )
                        st.success("PDF generated successfully.")
                    else:
                        st.warning("PDF could not be generated. Please ensure 'transport_order_template.pdf' is in the correct path.")

                else:
                    st.error(f"No data found for Shipment ID: {manual_id}")
    else:
        st.warning("Data is missing the 'Unique ID' column required for this view.")