"""
Streamlit UI for Screenshot Report Generator (Cloud version)

Run locally:
    streamlit run app.py
"""

import streamlit as st
from core import LayoutConfig, build_pdf

# -------------------------------------------------------------------
# PAGE SETUP
# -------------------------------------------------------------------

st.set_page_config(page_title="ReportForge", page_icon="📊", layout="wide")

st.title("📊 ReportForge")
st.caption("Upload screenshots + notes → Generate structured PDF report")

# -------------------------------------------------------------------
# INPUTS
# -------------------------------------------------------------------

st.subheader("1. Upload Screenshots")

uploaded_files = st.file_uploader(
    "Upload your screenshots",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True
)

st.subheader("2. Add Notes")

notes = []
if uploaded_files:
    st.info(f"{len(uploaded_files)} files uploaded")

    for i, file in enumerate(uploaded_files, start=1):
        st.image(file, width=300)
        note = st.text_area(f"Note for {file.name}", key=f"note_{i}")
        notes.append(note)

# -------------------------------------------------------------------
# SETTINGS
# -------------------------------------------------------------------

st.subheader("3. Layout Settings")

col1, col2 = st.columns(2)

with col1:
    font_size = st.number_input("Font size", value=10.0)
    gap = st.number_input("Gap between image & text", value=40.0)

with col2:
    page_width = st.number_input("Page width", value=1196.0)
    page_height = st.number_input("Page height", value=595.0)

# -------------------------------------------------------------------
# GENERATE
# -------------------------------------------------------------------

if st.button("✨ Generate PDF", use_container_width=True):

    if not uploaded_files:
        st.error("Please upload screenshots first.")
        st.stop()

    config = LayoutConfig(
        page_width=page_width,
        page_height=page_height,
        font_size=font_size,
        gap=gap,
    )

    with st.spinner("Generating PDF..."):

        try:
            pdf_bytes = build_pdf(
                uploaded_files=uploaded_files,
                notes=notes,
                config=config
            )

            st.success("PDF generated successfully!")

            st.download_button(
                "⬇️ Download PDF",
                data=pdf_bytes,
                file_name="report.pdf",
                mime="application/pdf"
            )

        except Exception as e:
            st.error(f"Error: {e}")
