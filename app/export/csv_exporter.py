"""CSV exporter for leads.

Builds a CSV string from a list of LeadOut objects so the caller can stream
it directly as a file download. No file I/O — returns bytes so FastAPI can
stream the response without touching the filesystem.
"""
import csv
import io

from app.features.leads.schemas import LeadOut

_COLUMNS = [
    "business_id",
    "name",
    "category",
    "score",
    "opportunity_type",
    "status",
    "has_website",
    "website_url",
    "rating",
    "reviews_count",
    "notes",
]


def leads_to_csv(leads: list[LeadOut]) -> bytes:
    """Serialise *leads* to UTF-8 CSV bytes (with BOM for Excel compatibility)."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for lead in leads:
        writer.writerow({
            "business_id": lead.business_id,
            "name": lead.name,
            "category": lead.category or "",
            "score": lead.score,
            "opportunity_type": lead.opportunity_type or "",
            "status": lead.status.value,
            "has_website": lead.has_website,
            "website_url": lead.website_url or "",
            "rating": lead.rating if lead.rating is not None else "",
            "reviews_count": lead.reviews_count if lead.reviews_count is not None else "",
            "notes": lead.notes or "",
        })
    # UTF-8 BOM so Excel opens the file without encoding issues
    return "﻿".encode("utf-8") + buf.getvalue().encode("utf-8")
