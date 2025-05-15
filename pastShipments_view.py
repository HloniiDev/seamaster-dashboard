import streamlit as st
import pandas as pd
from datetime import datetime
import io
from fpdf import FPDF
import tempfile

def render_shipments(df):
    st.markdown("## 📁 All Past Shipment IDs (Metadata View)")

    if df.empty:
        st.info("No shipment data available in the database.")
        return

    # Handle 'Date Submitted'
    if "Date Submitted" in df.columns:
        df["Date Submitted"] = pd.to_datetime(df["Date Submitted"], errors="coerce")
        df_valid_dates = df.dropna(subset=["Date Submitted"]).copy()
    else:
        df_valid_dates = df.copy()

    if "Unique ID" in df_valid_dates.columns:
        df_valid_dates['Unique ID'] = df_valid_dates['Unique ID'].astype(str)

        if not df_valid_dates.empty:
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
                    shipment_row = (
                        shipment_data_row.sort_values("Date Submitted", ascending=False).iloc[0]
                    )

                    shipment_data = {
                        "Unique ID": shipment_row.get("Unique ID", ""),
                        "Date Submitted": shipment_row.get("Date Submitted", ""),
                        "Transporter": shipment_row.get("Transporter", ""),
                        "Client": shipment_row.get("Client", ""),
                        "Cargo Type": shipment_row.get("Cargo Type", ""),
                        "Loading Point": shipment_row.get("Loading Point", ""),
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
                        "Borders": shipment_row.get("Borders", ""),
                        "Trucks": shipment_row.get("Trucks", ""),
                        "Trailers": shipment_row.get("Trailers", ""),
                    }

                    # Generate PDF
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
                            pdf.cell(90, 10, str(key), border=1)
                            pdf.cell(90, 10, str(value), border=1)
                            pdf.ln()

                    # Save PDF and stream for download
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
                        pdf.output(tmpfile.name)

                        with open(tmpfile.name, "rb") as f:
                            st.download_button(
                                label="Download Shipment PDF",
                                data=f,
                                file_name=f"shipment_{manual_id}_details.pdf",
                                mime="application/pdf",
                                key=f"download_manual_pdf_{manual_id}"
                            )
                    st.success("PDF generated successfully.")
                else:
                    st.error(f"No data found for Shipment ID: {manual_id}")
    else:
        st.warning("Data is missing the 'Unique ID' column required for this view.")