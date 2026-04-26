"""
Core PDF generation logic — Streamlit Cloud version
Works with uploaded files (NOT folders)
"""

import csv
import io
import re
import urllib.request
from dataclasses import dataclass
from typing import List, Tuple

import requests
from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Frame


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
# FONT (safe fallback)
# -------------------------------------------------------------------

def ensure_font():
    try:
        pdfmetrics.registerFont(TTFont("Inter", "Inter-Regular.ttf"))
        return "Inter"
    except:
        return "Helvetica"


# -------------------------------------------------------------------
# SHEET → PARAGRAPHS
# -------------------------------------------------------------------

def sheet_url_to_csv(url: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    sheet_id = match.group(1)

    gid = "0"
    if "gid=" in url:
        gid = re.search(r"gid=(\d+)", url).group(1)

    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


def fetch_paragraphs(sheet_url: str, column_index: int = 0) -> List[str]:
    csv_url = sheet_url_to_csv(sheet_url)
    response = requests.get(csv_url)
    reader = csv.reader(io.StringIO(response.text))

    return [row[column_index] if len(row) > column_index else "" for row in reader]


# -------------------------------------------------------------------
# MATCH FILES (IMPORTANT CHANGE)
# -------------------------------------------------------------------

def match_files(uploaded_files):
    """
    Converts uploaded Streamlit files into usable image objects.
    Keeps order consistent with sheet rows.
    """
    return list(uploaded_files)


# -------------------------------------------------------------------
# DRAW PAGE
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

    # --- IMAGE ---
    img = Image.open(img_file)

    scale = min(image_box_w / img.width, image_box_h / img.height)
    w, h = img.width * scale, img.height * scale

    c.drawImage(
        img_file,
        image_x,
        image_y,
        width=w,
        height=h,
        preserveAspectRatio=True
    )

    # --- TEXT ---
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

    para = Paragraph(text, style)
    frame.addFromList([para], c)


# -------------------------------------------------------------------
# MAIN ENTRY
# -------------------------------------------------------------------

def build_pdf(uploaded_files, notes, config: LayoutConfig):

    font_name = ensure_font()

    buffer = io.BytesIO()

    c = canvas.Canvas(buffer, pagesize=(config.page_width, config.page_height))

    total_pages = len(uploaded_files)

    for i, (file, note) in enumerate(zip(uploaded_files, notes), start=1):
        draw_page(c, file, note, font_name, config, i, total_pages)
        c.showPage()

    c.save()

    buffer.seek(0)
    return buffer.read()
