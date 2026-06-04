"""Excel (.xlsx) exporter for leads using openpyxl.

Returns bytes so FastAPI can stream the response without touching the filesystem.
Applies minimal formatting: bold header row and auto-sized columns.
"""
import io

from openpyxl import Workbook
from openpyxl.styles import Font

from app.features.leads.schemas import LeadOut

_HEADERS = [
    ("business_id", "ID"),
    ("name", "Business name"),
    ("category", "Category"),
    ("score", "Score"),
    ("opportunity_type", "Opportunity type"),
    ("status", "Status"),
    ("has_website", "Has website"),
    ("website_url", "Website URL"),
    ("rating", "Rating"),
    ("reviews_count", "Reviews"),
    ("notes", "Notes"),
]


def leads_to_excel(leads: list[LeadOut]) -> bytes:
    """Serialise *leads* to an .xlsx file returned as bytes."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Leads"

    # Header row — bold
    header_font = Font(bold=True)
    for col_idx, (_, label) in enumerate(_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=label)
        cell.font = header_font

    # Data rows
    for lead in leads:
        row = [
            lead.business_id,
            lead.name,
            lead.category or "",
            lead.score,
            lead.opportunity_type or "",
            lead.status.value,
            lead.has_website,
            lead.website_url or "",
            float(lead.rating) if lead.rating is not None else "",
            lead.reviews_count if lead.reviews_count is not None else "",
            lead.notes or "",
        ]
        ws.append(row)

    # Auto-size columns based on content (capped at 60 chars)
    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 60)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
