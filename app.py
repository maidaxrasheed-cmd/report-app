import streamlit as st
from core import LayoutConfig, build_pdf, fetch_paragraphs

# -------------------------------------------------------------------
# PAGE SETUP
# -------------------------------------------------------------------

st.set_page_config(page_title="ReportForge", page_icon="📊", layout="wide")

st.title("📊 ReportForge")
st.caption("Screenshots → Notes → Clean PDF Reports")

# -------------------------------------------------------------------
# STEP 1 — UPLOAD
# -------------------------------------------------------------------

st.subheader("1. Upload Screenshots")

uploaded_files = st.file_uploader(
    "Drop screenshots here",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True
)

if not uploaded_files:
    st.stop()

st.success(f"{len(uploaded_files)} screenshots loaded")

# -------------------------------------------------------------------
# STEP 2 — INPUT MODE
# -------------------------------------------------------------------

st.subheader("2. Add Notes")

mode = st.radio(
    "Choose input method",
    ["Manual Notes", "Google Sheets"],
    horizontal=True
)

notes = []

# ---------------- MANUAL ----------------

if mode == "Manual Notes":
    for i, file in enumerate(uploaded_files, start=1):
        st.image(file, width=200)
        notes.append(st.text_area(f"Note {i}", key=f"n{i}"))

# ---------------- SHEETS (AUTO LOAD) ----------------

else:
    sheet_url = st.text_input("Google Sheet URL")

    column_index = st.number_input("Column Index", value=0, step=1)

    if sheet_url:
        try:
            notes = fetch_paragraphs(sheet_url, int(column_index))
            st.success(f"Loaded {len(notes)} notes from sheet")
        except Exception as e:
            st.error(f"Sheet error: {e}")

# padding safety
notes += [""] * max(0, len(uploaded_files) - len(notes))

# -------------------------------------------------------------------
# STEP 3 — SETTINGS (MINIMAL & CLEAN)
# -------------------------------------------------------------------

st.subheader("3. Layout")

col1, col2 = st.columns(2)

with col1:
    font_size = st.slider("Font size", 8, 18, 10)
    text_color = st.color_picker("Text color", "#444444")

with col2:
    gap = st.slider("Spacing", 10, 100, 40)
    margin = st.slider("Page margin", 10, 120, 40)

config = LayoutConfig(
    font_size=font_size,
    gap=gap,
    outer_margin=margin,
    text_color=text_color
)

# -------------------------------------------------------------------
# STEP 4 — GENERATE (UNCHANGED BUTTON)
# -------------------------------------------------------------------

st.subheader("4. Export")

if st.button("✨ Generate PDF", use_container_width=True):

    with st.spinner("Building your report..."):

        try:
            pdf_bytes = build_pdf(
                uploaded_files=uploaded_files,
                notes=notes,
                config=config
            )

            st.success("Done — your report is ready")

            st.download_button(
                "⬇️ Download PDF",
                data=pdf_bytes,
                file_name="reportforge.pdf",
                mime="application/pdf"
            )

        except Exception as e:
            st.error(f"Error: {e}")
