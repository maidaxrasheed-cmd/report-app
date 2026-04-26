"""
Core PDF generation logic — used by both the CLI script and the Streamlit app.

Layout per page:
  - Alternating: odd pages = text-left/image-right, even pages = image-left/text-right
  - Image box vertically centered; image scaled to fit (preserves aspect ratio)
  - Page number aligned to whichever side the text is on
"""

import csv
import io
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import requests
from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Frame


# ---------------------------------------------------------------------------
# Configuration object — holds everything tweakable from the UI
# ---------------------------------------------------------------------------

@dataclass
class LayoutConfig:
    # Page
    page_width: float = 1196
    page_height: float = 595

    # Image box
    image_box_width: float = 830
    image_box_height: float = 467

    # Spacing
    outer_margin: float = 40        # left and right page margins
    gap: float = 40                 # gap between image box and text column

    # Text style
    font_size: float = 10
    line_height_ratio: float = 1.4   # 140% leading
    text_color: str = "#545454"

    # Page number
    page_number_margin_x: float = 64
    page_number_margin_y: float = 64

    # Font path. If None, falls back to Helvetica.
    font_path: Optional[Path] = None

    # Source data
    paragraph_column_index: int = 0
    has_header_row: bool = False
    screenshot_name_pattern: str = "screenshot{n}"
    screenshot_extensions: Tuple[str, ...] = (".png", ".jpg", ".jpeg", ".webp")

    @property
    def text_column_width(self) -> float:
        """Computed width of the text column."""
        return (
            self.page_width
            - self.outer_margin
            - self.image_box_width
            - self.gap
            - self.outer_margin
        )


# ---------------------------------------------------------------------------
# Default Inter download (used if no font is provided)
# ---------------------------------------------------------------------------

DEFAULT_FONT_DIR = Path("./fonts")
DEFAULT_FONT_PATH = DEFAULT_FONT_DIR / "Inter-Regular.ttf"
INTER_DOWNLOAD_URL = (
    "https://github.com/google/fonts/raw/main/ofl/inter/static/Inter-Regular.ttf"
)


def ensure_font(config: LayoutConfig, log=print) -> str:
    """Register the font with reportlab and return the font name to use.

    If config.font_path is set and exists, uses it. Otherwise tries to
    download Inter. Falls back to Helvetica on any failure.
    """
    font_name = "Inter"
    candidate = config.font_path

    # If user didn't supply a path, try the default cache location
    if candidate is None:
        candidate = DEFAULT_FONT_PATH

    try:
        if not candidate.exists():
            log(f"Downloading Inter Regular to {candidate} ...")
            candidate.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(INTER_DOWNLOAD_URL, candidate)
        pdfmetrics.registerFont(TTFont(font_name, str(candidate)))
        return font_name
    except Exception as exc:
        log(f"  ! Could not load Inter ({exc}). Falling back to Helvetica.")
        return "Helvetica"


# ---------------------------------------------------------------------------
# Sheet fetching
# ---------------------------------------------------------------------------

def sheet_url_to_csv(url: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if not match:
        raise ValueError(f"Could not find sheet ID in URL: {url}")
    sheet_id = match.group(1)

    gid_match = re.search(r"[?&#]gid=(\d+)", url)
    gid = gid_match.group(1) if gid_match else "0"

    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/export?format=csv&gid={gid}"
    )


def fetch_paragraphs(sheet_url: str, column_index: int, skip_header: bool) -> List[str]:
    csv_url = sheet_url_to_csv(sheet_url)
    response = requests.get(csv_url, timeout=30)
    response.raise_for_status()

    reader = csv.reader(io.StringIO(response.text))
    rows = list(reader)
    if skip_header and rows:
        rows = rows[1:]

    paragraphs = []
    for row in rows:
        cell = row[column_index].strip() if column_index < len(row) else ""
        paragraphs.append(cell)

    while paragraphs and not paragraphs[-1]:
        paragraphs.pop()

    return paragraphs


# ---------------------------------------------------------------------------
# Screenshot lookup
# ---------------------------------------------------------------------------

def find_screenshot(
    screenshot_dir: Path, index_1based: int, config: LayoutConfig
) -> Optional[Path]:
    base_name = config.screenshot_name_pattern.format(n=index_1based)
    for ext in config.screenshot_extensions:
        candidate = screenshot_dir / f"{base_name}{ext}"
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def draw_page(
    c: canvas.Canvas,
    image_path: Path,
    paragraph_text: str,
    font_name: str,
    page_number: int,
    total_pages: int,
    config: LayoutConfig,
) -> None:
    image_on_left = (page_number % 2 == 0)

    if image_on_left:
        image_box_x = config.outer_margin
        text_x = config.outer_margin + config.image_box_width + config.gap
    else:
        text_x = config.outer_margin
        image_box_x = config.outer_margin + config.text_column_width + config.gap

    image_box_y = (config.page_height - config.image_box_height) / 2

    with Image.open(image_path) as img:
        img_w, img_h = img.size

    scale = min(config.image_box_width / img_w, config.image_box_height / img_h)
    draw_w = img_w * scale
    draw_h = img_h * scale

    img_x = image_box_x + (config.image_box_width - draw_w) / 2
    img_y = image_box_y + (config.image_box_height - draw_h) / 2

    c.drawImage(
        str(image_path),
        img_x, img_y,
        width=draw_w, height=draw_h,
        preserveAspectRatio=True,
        mask="auto",
    )

    # --- Text column ---
    text_y = image_box_y
    text_height = config.image_box_height

    body_style = ParagraphStyle(
        "Body",
        fontName=font_name,
        fontSize=config.font_size,
        leading=config.font_size * config.line_height_ratio,
        textColor=HexColor(config.text_color),
        spaceAfter=config.font_size * config.line_height_ratio,
        alignment=0,
    )

    blocks = re.split(r"\n\s*\n", paragraph_text)
    flowables = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        safe = (
            block.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;")
                 .replace("\n", "<br/>")
        )
        flowables.append(Paragraph(safe, body_style))
    if not flowables:
        flowables = [Paragraph("&nbsp;", body_style)]

    frame = Frame(
        text_x, text_y,
        config.text_column_width, text_height,
        leftPadding=0, rightPadding=0,
        topPadding=0, bottomPadding=0,
        showBoundary=0,
    )
    frame.addFromList(flowables, c)

    # --- Page number ---
    pad_width = max(2, len(str(total_pages)))
    page_label = f"Page {page_number:0{pad_width}d} / {total_pages:0{pad_width}d}"

    c.setFont(font_name, config.font_size)
    c.setFillColor(HexColor(config.text_color))

    if image_on_left:
        c.drawRightString(
            config.page_width - config.page_number_margin_x,
            config.page_number_margin_y,
            page_label,
        )
    else:
        c.drawString(
            config.page_number_margin_x,
            config.page_number_margin_y,
            page_label,
        )


# ---------------------------------------------------------------------------
# Top-level entrypoint
# ---------------------------------------------------------------------------

def build_pdf(
    *,
    sheet_url: str,
    screenshot_dir: Path,
    output_path: Path,
    config: LayoutConfig,
    log=print,
) -> int:
    """Build the PDF. Returns the number of pages written."""
    font_name = ensure_font(config, log=log)

    paragraphs = fetch_paragraphs(
        sheet_url, config.paragraph_column_index, config.has_header_row
    )
    log(f"Got {len(paragraphs)} paragraph(s) from the sheet.")

    pairs: List[Tuple[Path, str]] = []
    for i, text in enumerate(paragraphs, start=1):
        image_path = find_screenshot(screenshot_dir, i, config)
        if image_path is None:
            base = config.screenshot_name_pattern.format(n=i)
            log(f"  Row {i}: no screenshot for '{base}' — skipping")
            continue
        pairs.append((image_path, text))

    total_pages = len(pairs)
    if total_pages == 0:
        raise RuntimeError("No pages to render. Check screenshot folder and sheet URL.")

    log(f"Rendering {total_pages} page(s)...")
    c = canvas.Canvas(str(output_path), pagesize=(config.page_width, config.page_height))
    for page_number, (image_path, text) in enumerate(pairs, start=1):
        side = "image-left" if page_number % 2 == 0 else "text-left"
        log(f"  Page {page_number}/{total_pages}: {image_path.name} ({side})")
        draw_page(c, image_path, text, font_name, page_number, total_pages, config)
        c.showPage()
    c.save()
    return total_pages
"""
Core PDF generation logic — used by both the CLI script and the Streamlit app.

Layout per page:
  - Alternating: odd pages = text-left/image-right, even pages = image-left/text-right
  - Image box vertically centered; image scaled to fit (preserves aspect ratio)
  - Page number aligned to whichever side the text is on
"""

import csv
import io
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import requests
from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Frame


# ---------------------------------------------------------------------------
# Configuration object — holds everything tweakable from the UI
# ---------------------------------------------------------------------------

@dataclass
class LayoutConfig:
    # Page
    page_width: float = 1196
    page_height: float = 595

    # Image box
    image_box_width: float = 830
    image_box_height: float = 467

    # Spacing
    outer_margin: float = 40        # left and right page margins
    gap: float = 40                 # gap between image box and text column

    # Text style
    font_size: float = 10
    line_height_ratio: float = 1.4   # 140% leading
    text_color: str = "#545454"

    # Page number
    page_number_margin_x: float = 64
    page_number_margin_y: float = 64

    # Font path. If None, falls back to Helvetica.
    font_path: Optional[Path] = None

    # Source data
    paragraph_column_index: int = 0
    has_header_row: bool = False
    screenshot_name_pattern: str = "screenshot{n}"
    screenshot_extensions: Tuple[str, ...] = (".png", ".jpg", ".jpeg", ".webp")

    @property
    def text_column_width(self) -> float:
        """Computed width of the text column."""
        return (
            self.page_width
            - self.outer_margin
            - self.image_box_width
            - self.gap
            - self.outer_margin
        )


# ---------------------------------------------------------------------------
# Default Inter download (used if no font is provided)
# ---------------------------------------------------------------------------

DEFAULT_FONT_DIR = Path("./fonts")
DEFAULT_FONT_PATH = DEFAULT_FONT_DIR / "Inter-Regular.ttf"
INTER_DOWNLOAD_URL = (
    "https://github.com/google/fonts/raw/main/ofl/inter/static/Inter-Regular.ttf"
)


def ensure_font(config: LayoutConfig, log=print) -> str:
    """Register the font with reportlab and return the font name to use.

    If config.font_path is set and exists, uses it. Otherwise tries to
    download Inter. Falls back to Helvetica on any failure.
    """
    font_name = "Inter"
    candidate = config.font_path

    # If user didn't supply a path, try the default cache location
    if candidate is None:
        candidate = DEFAULT_FONT_PATH

    try:
        if not candidate.exists():
            log(f"Downloading Inter Regular to {candidate} ...")
            candidate.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(INTER_DOWNLOAD_URL, candidate)
        pdfmetrics.registerFont(TTFont(font_name, str(candidate)))
        return font_name
    except Exception as exc:
        log(f"  ! Could not load Inter ({exc}). Falling back to Helvetica.")
        return "Helvetica"


# ---------------------------------------------------------------------------
# Sheet fetching
# ---------------------------------------------------------------------------

def sheet_url_to_csv(url: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if not match:
        raise ValueError(f"Could not find sheet ID in URL: {url}")
    sheet_id = match.group(1)

    gid_match = re.search(r"[?&#]gid=(\d+)", url)
    gid = gid_match.group(1) if gid_match else "0"

    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/export?format=csv&gid={gid}"
    )


def fetch_paragraphs(sheet_url: str, column_index: int, skip_header: bool) -> List[str]:
    csv_url = sheet_url_to_csv(sheet_url)
    response = requests.get(csv_url, timeout=30)
    response.raise_for_status()

    reader = csv.reader(io.StringIO(response.text))
    rows = list(reader)
    if skip_header and rows:
        rows = rows[1:]

    paragraphs = []
    for row in rows:
        cell = row[column_index].strip() if column_index < len(row) else ""
        paragraphs.append(cell)

    while paragraphs and not paragraphs[-1]:
        paragraphs.pop()

    return paragraphs


# ---------------------------------------------------------------------------
# Screenshot lookup
# ---------------------------------------------------------------------------

def find_screenshot(
    screenshot_dir: Path, index_1based: int, config: LayoutConfig
) -> Optional[Path]:
    base_name = config.screenshot_name_pattern.format(n=index_1based)
    for ext in config.screenshot_extensions:
        candidate = screenshot_dir / f"{base_name}{ext}"
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def draw_page(
    c: canvas.Canvas,
    image_path: Path,
    paragraph_text: str,
    font_name: str,
    page_number: int,
    total_pages: int,
    config: LayoutConfig,
) -> None:
    image_on_left = (page_number % 2 == 0)

    if image_on_left:
        image_box_x = config.outer_margin
        text_x = config.outer_margin + config.image_box_width + config.gap
    else:
        text_x = config.outer_margin
        image_box_x = config.outer_margin + config.text_column_width + config.gap

    image_box_y = (config.page_height - config.image_box_height) / 2

    with Image.open(image_path) as img:
        img_w, img_h = img.size

    scale = min(config.image_box_width / img_w, config.image_box_height / img_h)
    draw_w = img_w * scale
    draw_h = img_h * scale

    img_x = image_box_x + (config.image_box_width - draw_w) / 2
    img_y = image_box_y + (config.image_box_height - draw_h) / 2

    c.drawImage(
        str(image_path),
        img_x, img_y,
        width=draw_w, height=draw_h,
        preserveAspectRatio=True,
        mask="auto",
    )

    # --- Text column ---
    text_y = image_box_y
    text_height = config.image_box_height

    body_style = ParagraphStyle(
        "Body",
        fontName=font_name,
        fontSize=config.font_size,
        leading=config.font_size * config.line_height_ratio,
        textColor=HexColor(config.text_color),
        spaceAfter=config.font_size * config.line_height_ratio,
        alignment=0,
    )

    blocks = re.split(r"\n\s*\n", paragraph_text)
    flowables = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        safe = (
            block.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;")
                 .replace("\n", "<br/>")
        )
        flowables.append(Paragraph(safe, body_style))
    if not flowables:
        flowables = [Paragraph("&nbsp;", body_style)]

    frame = Frame(
        text_x, text_y,
        config.text_column_width, text_height,
        leftPadding=0, rightPadding=0,
        topPadding=0, bottomPadding=0,
        showBoundary=0,
    )
    frame.addFromList(flowables, c)

    # --- Page number ---
    pad_width = max(2, len(str(total_pages)))
    page_label = f"Page {page_number:0{pad_width}d} / {total_pages:0{pad_width}d}"

    c.setFont(font_name, config.font_size)
    c.setFillColor(HexColor(config.text_color))

    if image_on_left:
        c.drawRightString(
            config.page_width - config.page_number_margin_x,
            config.page_number_margin_y,
            page_label,
        )
    else:
        c.drawString(
            config.page_number_margin_x,
            config.page_number_margin_y,
            page_label,
        )


# ---------------------------------------------------------------------------
# Top-level entrypoint
# ---------------------------------------------------------------------------

def build_pdf(
    *,
    sheet_url: str,
    screenshot_dir: Path,
    output_path: Path,
    config: LayoutConfig,
    log=print,
) -> int:
    """Build the PDF. Returns the number of pages written."""
    font_name = ensure_font(config, log=log)

    paragraphs = fetch_paragraphs(
        sheet_url, config.paragraph_column_index, config.has_header_row
    )
    log(f"Got {len(paragraphs)} paragraph(s) from the sheet.")

    pairs: List[Tuple[Path, str]] = []
    for i, text in enumerate(paragraphs, start=1):
        image_path = find_screenshot(screenshot_dir, i, config)
        if image_path is None:
            base = config.screenshot_name_pattern.format(n=i)
            log(f"  Row {i}: no screenshot for '{base}' — skipping")
            continue
        pairs.append((image_path, text))

    total_pages = len(pairs)
    if total_pages == 0:
        raise RuntimeError("No pages to render. Check screenshot folder and sheet URL.")

    log(f"Rendering {total_pages} page(s)...")
    c = canvas.Canvas(str(output_path), pagesize=(config.page_width, config.page_height))
    for page_number, (image_path, text) in enumerate(pairs, start=1):
        side = "image-left" if page_number % 2 == 0 else "text-left"
        log(f"  Page {page_number}/{total_pages}: {image_path.name} ({side})")
        draw_page(c, image_path, text, font_name, page_number, total_pages, config)
        c.showPage()
    c.save()
    return total_pages
