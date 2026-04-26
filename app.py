"""
Streamlit UI for the screenshot report generator.

Run with:
    streamlit run app.py
    # or, if `streamlit` isn't on PATH:
    python3 -m streamlit run app.py

To select your screenshot folder, drag the folder from Finder into the path
field (Finder will paste its full path) or type/paste it manually.
"""

import sys
import tempfile
from pathlib import Path

import streamlit as st

# Make sure we can import the core module from the same folder
sys.path.insert(0, str(Path(__file__).parent.resolve()))
from core import LayoutConfig, build_pdf


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Screenshot Report", page_icon="📄", layout="wide")
st.title("📄 Screenshot Report Generator")
st.caption("Build a multi-page PDF pairing screenshots with paragraphs from a Google Sheet.")

# Persist the picked folder across reruns
if "screenshot_dir" not in st.session_state:
    st.session_state.screenshot_dir = ""

# ---------------------------------------------------------------------------
# Sources panel
# ---------------------------------------------------------------------------

st.subheader("1. Sources")

st.markdown(
    "**Tip:** drag your screenshots folder from Finder onto the field below — "
    "macOS will paste its full path automatically. You can also type or paste a path."
)

st.session_state.screenshot_dir = st.text_input(
    "Screenshot folder",
    value=st.session_state.screenshot_dir,
    placeholder="/Users/you/Downloads/screenshots",
)

# Live feedback so you see immediately whether the path is valid and how many
# screenshots it contains.
if st.session_state.screenshot_dir:
    folder = Path(st.session_state.screenshot_dir.strip().strip("'\""))
    if folder.exists() and folder.is_dir():
        image_files = sorted(
            f for f in folder.iterdir()
            if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        )
        if image_files:
            st.success(f"✅ Found {len(image_files)} image file(s) in this folder.")
        else:
            st.warning("Folder exists but contains no .png/.jpg/.jpeg/.webp files.")
    else:
        st.error("That path doesn't exist or isn't a folder.")

sheet_url = st.text_input(
    "Google Sheet URL",
    placeholder="https://docs.google.com/spreadsheets/d/.../edit#gid=0",
    help="The sheet must be shared as 'Anyone with the link → Viewer'.",
)

with st.expander("Sheet options"):
    col_a, col_b = st.columns(2)
    with col_a:
        column_letter = st.text_input(
            "Column letter (paragraph)",
            value="A",
            help="Which column in your sheet holds the paragraph text.",
        )
    with col_b:
        has_header = st.checkbox("First row is a header (skip it)", value=False)

with st.expander("Screenshot naming"):
    name_pattern = st.text_input(
        "Filename pattern",
        value="screenshot{n}",
        help="{n} is replaced by the row number (1, 2, 3 …). Extensions tried automatically: .png, .jpg, .jpeg, .webp",
    )

# ---------------------------------------------------------------------------
# Layout settings
# ---------------------------------------------------------------------------

st.subheader("2. Layout")

with st.expander("Page & image dimensions", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        page_width = st.number_input("Page width (pt)", min_value=200.0, value=1196.0, step=10.0)
        image_box_width = st.number_input("Image box width (pt)", min_value=100.0, value=830.0, step=10.0)
        outer_margin = st.number_input("Outer margin (pt)", min_value=0.0, value=40.0, step=4.0)
    with col2:
        page_height = st.number_input("Page height (pt)", min_value=200.0, value=595.0, step=10.0)
        image_box_height = st.number_input("Image box height (pt)", min_value=100.0, value=467.0, step=10.0)
        gap = st.number_input("Gap between image and text (pt)", min_value=0.0, value=40.0, step=4.0)

with st.expander("Typography", expanded=False):
    col1, col2, col3 = st.columns(3)
    with col1:
        font_size = st.number_input("Font size (pt)", min_value=4.0, value=10.0, step=0.5)
    with col2:
        line_height = st.number_input("Line height (×)", min_value=1.0, value=1.4, step=0.1)
    with col3:
        text_color = st.color_picker("Text color", value="#545454")

with st.expander("Page number", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        pn_margin_x = st.number_input("Horizontal margin (pt)", min_value=0.0, value=64.0, step=4.0)
    with col2:
        pn_margin_y = st.number_input("Vertical margin from bottom (pt)", min_value=0.0, value=64.0, step=4.0)

# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

st.subheader("3. Generate")

# Helper: convert a column letter (A, B, AA…) to a 0-based index
def column_letter_to_index(letter: str) -> int:
    letter = letter.strip().upper()
    if not letter or not letter.isalpha():
        return 0
    n = 0
    for ch in letter:
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


generate = st.button("✨ Generate PDF", type="primary", use_container_width=True)

if generate:
    # Normalize the path: Finder drag often wraps in quotes; if user types
    # an escaped path (e.g. "/Users/My\ Folder"), un-escape the backslashes.
    raw_path = st.session_state.screenshot_dir.strip().strip("'\"")
    raw_path = raw_path.replace("\\ ", " ")  # un-escape spaces
    screenshot_dir = Path(raw_path).expanduser()

    # Validate inputs
    errors = []
    if not raw_path:
        errors.append("Pick a screenshot folder.")
    elif not screenshot_dir.exists():
        errors.append(f"Folder does not exist: {screenshot_dir}")
    if not sheet_url.strip():
        errors.append("Paste your Google Sheet URL.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        config = LayoutConfig(
            page_width=page_width,
            page_height=page_height,
            image_box_width=image_box_width,
            image_box_height=image_box_height,
            outer_margin=outer_margin,
            gap=gap,
            font_size=font_size,
            line_height_ratio=line_height,
            text_color=text_color,
            page_number_margin_x=pn_margin_x,
            page_number_margin_y=pn_margin_y,
            paragraph_column_index=column_letter_to_index(column_letter),
            has_header_row=has_header,
            screenshot_name_pattern=name_pattern,
        )

        # Build the PDF into a temp file
        log_lines = []
        def log(msg):
            log_lines.append(str(msg))

        with st.spinner("Generating PDF..."):
            try:
                output_path = Path(tempfile.gettempdir()) / "screenshot_report.pdf"
                pages = build_pdf(
                    sheet_url=sheet_url.strip(),
                    screenshot_dir=screenshot_dir,
                    output_path=output_path,
                    config=config,
                    log=log,
                )
            except Exception as exc:
                st.error(f"❌ {exc}")
                with st.expander("Log"):
                    st.code("\n".join(log_lines) or "(no log output)")
            else:
                st.success(f"✅ Generated {pages}-page PDF.")
                with output_path.open("rb") as f:
                    st.download_button(
                        "⬇️ Download PDF",
                        data=f.read(),
                        file_name="screenshot_report.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                with st.expander("Log"):
                    st.code("\n".join(log_lines))
