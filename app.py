import streamlit as st
from core import LayoutConfig, build_pdf

# -------------------------------------------------------------------
# PAGE SETUP
# -------------------------------------------------------------------

st.set_page_config(page_title="ReportForge", page_icon="📊", layout="wide")

st.title("📊 ReportForge")
st.caption("Screenshots → Notes → Beautiful PDF Reports")

# -------------------------------------------------------------------
# MODE SELECTOR
# -------------------------------------------------------------------

mode = st.radio(
    "Choose input method",
    ["Manual Notes", "Google Sheets"],
    horizontal=True
)

# -------------------------------------------------------------------
# SCREENSHOTS
# -------------------------------------------------------------------

st.subheader("1. Upload Screenshots")

uploaded_files = st.file_uploader(
    "Upload screenshots",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True
)

if not uploaded_files:
    st.stop()

# -------------------------------------------------------------------
# NOTES INPUT (MODE SWITCH)
# -------------------------------------------------------------------

notes = []

if mode == "Manual Notes":

    st.subheader("2. Add Notes Manually")

    for i, file in enumerate(uploaded_files, start=1):
        st.image(file, width=250)
        note = st.text_area(f"Note for {file.name}", key=f"note_{i}")
        notes.append(note)

elif mode == "Google Sheets":

    st.subheader("2. Google Sheets Input")

    sheet_url = st.text_input("Paste Google Sheet URL")

    column_index = st.number_input("Column Index for Notes", value=0, step=1)

    if st.button("Load Notes from Sheet"):
        from core import fetch_paragraphs
        notes = fetch_paragraphs(sheet_url, int(column_index))
        st.success("Notes loaded from sheet!")

# -------------------------------------------------------------------
# LAYOUT SETTINGS
# -------------------------------------------------------------------

st.subheader("3. Design Settings")

col1, col2, col3 = st.columns(3)

with col1:
    font_size = st.slider("Font size", 8, 20, 10)
    text_color = st.color_picker("Notes color", "#444444")

with col2:
    gap = st.slider("Gap between image & text", 10, 100, 40)
    margin = st.slider("Page margin", 10, 120, 40)

with col3:
    page_width = st.number_input("Page width", value=1196.0)
    page_height = st.number_input("Page height", value=595.0)

# -------------------------------------------------------------------
# PAGE NUMBER STYLE OPTION
# -------------------------------------------------------------------

page_number_side = st.radio(
    "Page number alignment",
    ["Follow Notes Side", "Always Left", "Always Right"]
)

# -------------------------------------------------------------------
# BUILD CONFIG
# -------------------------------------------------------------------

config = LayoutConfig(
    page_width=page_width,
    page_height=page_height,
    font_size=font_size,
    gap=gap,
    outer_margin=margin,
    text_color=text_color
)

# attach extra UI setting dynamically
config.page_number_side = page_number_side

# -------------------------------------------------------------------
# GENERATE
# -------------------------------------------------------------------

st.subheader("4. Generate PDF")

if st.button("✨ Generate PDF", use_container_width=True):

    # safety
    if mode == "Google Sheets" and not notes:
        st.error("Load notes from Google Sheets first.")
        st.stop()

    if len(notes) < len(uploaded_files):
        notes += [""] * (len(uploaded_files) - len(notes))

    with st.spinner("Building PDF..."):

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
                file_name="reportforge.pdf",
                mime="application/pdf"
            )

        except Exception as e:
            st.error(f"Error: {e}")
