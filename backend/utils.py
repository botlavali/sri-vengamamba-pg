"""Utility functions: file uploads + PDF receipt generation."""
import os
import secrets
from datetime import datetime
from typing import Iterable, List, Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Flowable
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
RECEIPT_DIR = os.path.join(UPLOAD_DIR, "receipts")
DOCS_DIR = os.path.join(UPLOAD_DIR, "docs")
os.makedirs(RECEIPT_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)

ALLOWED_IMG = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_DOC = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB

# Branding colors (must match the boutique theme)
_BRAND_GREEN = colors.HexColor("#1A3B2B")
_BRAND_TERRACOTTA = colors.HexColor("#C85A32")
_BRAND_CREAM = colors.HexColor("#F9F6F0")
_BORDER = colors.HexColor("#E5E7EB")
_BORDER_DARK = colors.HexColor("#CBD5E1")


# ---------- Uploads ----------
def save_uploaded_file(filename: str, raw: bytes, allowed: Iterable[str]) -> str:
    """Save file with a random name, return public /uploads/... path."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed:
        raise ValueError(f"Extension {ext} not allowed. Allowed: {', '.join(allowed)}")
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError(f"File too large (max {MAX_FILE_BYTES // (1024*1024)} MB)")
    if len(raw) == 0:
        raise ValueError("Empty file")
    name = f"{secrets.token_hex(10)}{ext}"
    fpath = os.path.join(DOCS_DIR, name)
    with open(fpath, "wb") as f:
        f.write(raw)
    return f"/uploads/docs/{name}"


# ---------- PDF table style helpers ----------
def _kv_table_style() -> TableStyle:
    """Style for a 2-column key/value table."""
    return TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.4, _BORDER_DARK),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, _BORDER),
        ("BACKGROUND", (0, 0), (0, -1), _BRAND_CREAM),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ])


def _data_table_style() -> TableStyle:
    """Style for a multi-column data table with branded header."""
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _BRAND_GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (-2, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.3, _BORDER_DARK),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ])


def _summary_table_style() -> TableStyle:
    """Style for the payment-summary table (last row highlighted)."""
    return TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.4, _BORDER_DARK),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, _BORDER),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), _BRAND_TERRACOTTA),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ])


# ---------- Section builders ----------
def _build_header(pg: dict, styles) -> List[Flowable]:
    """PG branding header."""
    h1 = styles["Heading1"]
    h1.textColor = _BRAND_GREEN
    h2 = styles["Heading2"]
    h2.textColor = _BRAND_GREEN
    return [
        Paragraph(f"<b>{pg.get('name', 'Sri Vengamamba PG')}</b>", h1),
        Paragraph(pg.get("tagline", "S.V PG Hostel – Gents"), styles["Italic"]),
        Paragraph(pg.get("address", ""), styles["Normal"]),
        Paragraph(f"Phone: {pg.get('phone','')} · Email: {pg.get('email','')}", styles["Normal"]),
        Spacer(1, 12),
        Paragraph("PAYMENT RECEIPT", h2),
    ]


def _build_meta_section(booking_group_id: str, first: dict) -> Table:
    """Receipt no., date, payment id, status."""
    rows = [
        ["Receipt No.", booking_group_id.upper()],
        ["Date", datetime.now().strftime("%d %b %Y, %I:%M %p")],
        ["Payment ID", first.get("razorpay_payment_id") or "—"],
        ["Status", "PAID"],
    ]
    tbl = Table(rows, colWidths=[55 * mm, 110 * mm])
    tbl.setStyle(_kv_table_style())
    return tbl


def _build_guest_section(first: dict) -> Table:
    """Guest details table."""
    rows = [
        ["Name", first.get("name", "—")],
        ["Phone", first.get("phone", "—")],
        ["Email", first.get("email", "—")],
        ["Aadhaar", first.get("aadhaar_number") or "—"],
        ["Join date", first.get("join_date") or "—"],
    ]
    tbl = Table(rows, colWidths=[55 * mm, 110 * mm])
    tbl.setStyle(_kv_table_style())
    return tbl


def _build_bed_section(bookings: List[dict]) -> Table:
    """Bed allocation table."""
    rows = [["Floor", "Room", "Bed", "Sharing", "Monthly Rent"]]
    for b in bookings:
        rows.append([
            str(b.get("floor", "")),
            b.get("room_number", ""),
            str(b.get("bed", "")),
            f"{b.get('sharing_type', '-')}-share",
            f"INR {b.get('monthly_rent', 0):,}",
        ])
    tbl = Table(rows, colWidths=[22 * mm, 30 * mm, 22 * mm, 32 * mm, 39 * mm])
    tbl.setStyle(_data_table_style())
    return tbl


def _build_payment_summary(rent_total: int, advance: int, total: int) -> Table:
    """Payment breakdown with highlighted TOTAL row."""
    rows = [
        ["Bed rent (first month)", f"INR {rent_total:,}"],
        ["Refundable advance", f"INR {advance:,}"],
        ["TOTAL PAID", f"INR {total:,}"],
    ]
    tbl = Table(rows, colWidths=[110 * mm, 55 * mm])
    tbl.setStyle(_summary_table_style())
    return tbl


def _build_footer(styles) -> Paragraph:
    return Paragraph(
        "<i>Thank you for choosing Sri Vengamamba PG. "
        "This is an electronically generated receipt and does not require a signature. "
        "Advance is refundable on giving 2 months notice as per house rules.</i>",
        styles["Italic"],
    )


# ---------- Main entry ----------
def generate_receipt(booking_group_id: str, pg: dict, bookings: List[dict]) -> str:
    """Generate a PDF receipt for a paid booking group. Returns public URL."""
    out_path = os.path.join(RECEIPT_DIR, f"{booking_group_id}.pdf")
    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    first = bookings[0]
    totals: Dict[str, int] = {
        "rent": sum(b.get("monthly_rent", 0) for b in bookings),
        "advance": first.get("advance", 0),
    }
    totals["total"] = totals["rent"] + totals["advance"]

    story: List[Any] = []
    story.extend(_build_header(pg, styles))
    story.append(_build_meta_section(booking_group_id, first))
    story.append(Spacer(1, 12))
    story.append(Paragraph("<b>Guest Details</b>", styles["Heading3"]))
    story.append(_build_guest_section(first))
    story.append(Spacer(1, 12))
    story.append(Paragraph("<b>Bed Allocation</b>", styles["Heading3"]))
    story.append(_build_bed_section(bookings))
    story.append(Spacer(1, 14))
    story.append(Paragraph("<b>Payment Summary</b>", styles["Heading3"]))
    story.append(_build_payment_summary(totals["rent"], totals["advance"], totals["total"]))
    story.append(Spacer(1, 18))
    story.append(_build_footer(styles))

    doc.build(story)
    return f"/uploads/receipts/{booking_group_id}.pdf"
