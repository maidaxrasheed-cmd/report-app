"""
Core PDF generation logic — FINAL Streamlit Cloud version
"""

import csv
import io
import re
from dataclasses import dataclass
from typing import List

import requests
from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.utils import ImageReader


# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------

@dataclass
class LayoutConfig:
    page_width: float = 1196
    page_height: float = 595
    font_size: float = 10
    gap: float = 40


# -------------------------------------------------------------------
# SHEET → PARAGRAPHS
# -------------------------------------------------------------------

def sheet_url_to_csv(url: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if not match:
        raise ValueError("Invalid Google Sheet URL")

    sheet_id = match.group(1)

    gid = "0"
    if "gid=" in url:
        gid = re.search(r"gid=(\d+)", url).group(1)

    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


def fetch_paragraphs(sheet_url: str, column_index: int = 0) -> List[str]:
    csv_url = sheet_url_to_csv(sheet_url)
    response = requests.get(csv_url)
    response.raise_for_status()

    reader = csv.reader(io.StringIO(response.text))
    return [row[column_index] if len(row) > column_index else "" for row in reader]


# -------------------------------------------------------------------
# IMAGE + TEXT RENDER
# -------------------------------------------------------------------

def draw_page(c, img_file, text, font_name, config, page_num, total_pages):

    image_on_left = (page_num % 2 == 0)

    image_box_w = 830
    image_box_h = 467
    margin = 40
    gap = config.gap

    if image_on_left:
        image_x = margin
        text_x = margin + image_box_w + gap
    else:
        text_x = margin
        image_x = margin + 500

    image_y = (config.page_height - image_box_h) / 2

    # ---------------- IMAGE FIX (FINAL STABLE VERSION) ----------------

    img_bytes = img_file.read()
    img_stream = io.BytesIO(img_bytes)

    img = Image.open(img_stream)

    scale = min(image_box_w / img.width, image_box_h / img.height)
    w, h = img.width * scale, img.height * scale

    img_stream.seek(0)  # important safety reset

    img_reader = ImageReader(img_stream)

    c.drawImage(
        img_reader,
        image_x,
        image_y,
        width=w,
        height=h,
        preserveAspectRatio=True,
        mask="auto"
    )

    # ---------------- TEXT ----------------

    style = ParagraphStyle(
        "Body",
        fontName=font_name,
        fontSize=config.font_size,
        textColor=HexColor("#444444"),
        leading=config.font_size * 1.4
    )

    frame = Frame(
        text_x,
        image_y,
        400,
        image_box_h
    )

    paragraph = Paragraph(text or "", style)
    frame.addFromList([paragraph], c)


# -------------------------------------------------------------------
# MAIN ENTRY
# -------------------------------------------------------------------

def build_pdf(uploaded_files, notes, config: LayoutConfig):

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(config.page_width, config.page_height))

    total_pages = len(uploaded_files)

    # safety alignment
    notes += [""] * (len(uploaded_files) - len(notes))

    for i, (file, note) in enumerate(zip(uploaded_files, notes), start=1):
        draw_page(
            c,
            file,
            note,
            "Helvetica",
            config,
            i,
            total_pages
        )
        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.read()
