"""Contact extraction — finds emails and owner names from raw HTML.

Single responsibility: given raw HTML and the page URL, return a list of
ExtractedContact dataclasses. No DB writes here — that is repository's job.

Sources searched (own site only — never third-party directories):
  - mailto: links anywhere on the page
  - Plain email addresses in text (regex)
  - Owner/team names from About or Team sections

GDPR note: every contact is flagged is_personal_data=True by the repository
when saving. The `source` field records WHERE each datum was found so it can
be audited or deleted on request.
"""
import re
from dataclasses import dataclass, field

from selectolax.parser import HTMLParser

from app.features.businesses.models import ContactSource

# Matches standard email addresses. Intentionally simple — we'd rather miss
# an edge case than produce false positives that waste a seller's time.
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

# Roles that suggest the person is an owner or key contact.
_OWNER_ROLE_KEYWORDS = [
    "owner", "founder", "ceo", "director", "manager",
    "president", "principal", "partner", "propietario",
    "dueño", "gerente", "fundador",
]


@dataclass
class ExtractedContact:
    email: str | None
    name: str | None
    role: str | None
    source: ContactSource
    confidence: float   # 0.0 – 1.0


def _extract_emails(html: str) -> list[tuple[str, ContactSource]]:
    """Return (email, source) pairs found via mailto: links and plain text."""
    results: list[tuple[str, ContactSource]] = []
    seen: set[str] = set()

    tree = HTMLParser(html)

    # mailto: links are the most reliable source.
    for node in tree.css("a[href^='mailto:']"):
        href = node.attributes.get("href", "")
        email = href.replace("mailto:", "").split("?")[0].strip().lower()
        if email and _EMAIL_RE.fullmatch(email) and email not in seen:
            seen.add(email)
            results.append((email, ContactSource.website_email))

    # Plain text fallback — catches emails written as text in contact sections.
    for match in _EMAIL_RE.finditer(html):
        email = match.group().lower()
        if email not in seen:
            seen.add(email)
            results.append((email, ContactSource.website_contact_page))

    return results


def _extract_owner(html: str) -> tuple[str | None, str | None]:
    """Best-effort extraction of owner name and role from About/Team sections.

    Returns (name, role) or (None, None) if nothing credible is found.
    This is intentionally conservative: we only pick up structured patterns
    (e.g. a heading followed by a role subtitle) to avoid random false matches.
    """
    tree = HTMLParser(html)

    # Look for headings inside sections that suggest an About or Team page.
    about_keywords = ["about", "team", "staff", "our-story", "meet", "who-we-are"]
    for section in tree.css("section, div, article"):
        section_id = (section.attributes.get("id") or "").lower()
        section_class = (section.attributes.get("class") or "").lower()
        context = section_id + " " + section_class

        if not any(kw in context for kw in about_keywords):
            continue

        # Inside an about/team section, find headings and their siblings.
        for heading in section.css("h1, h2, h3, h4"):
            name_candidate = (heading.text(strip=True) or "").strip()
            if not name_candidate or len(name_candidate) > 60:
                continue

            # Look for a role subtitle immediately after the heading.
            sibling = heading.next
            role_candidate: str | None = None
            while sibling and sibling.tag in ("p", "span", "small", "em"):
                text = (sibling.text(strip=True) or "").strip().lower()
                if any(kw in text for kw in _OWNER_ROLE_KEYWORDS):
                    role_candidate = sibling.text(strip=True)
                    break
                sibling = sibling.next

            if role_candidate:
                return name_candidate, role_candidate

    return None, None


def extract(html: str) -> list[ExtractedContact]:
    """Return all contacts found in *html*. May return an empty list."""
    contacts: list[ExtractedContact] = []

    # --- Emails ---
    for email, source in _extract_emails(html):
        # Skip generic no-reply addresses — not useful for sales outreach.
        if any(generic in email for generic in ("noreply", "no-reply", "donotreply")):
            continue
        contacts.append(ExtractedContact(
            email=email,
            name=None,
            role=None,
            source=source,
            confidence=0.9 if source == ContactSource.website_email else 0.7,
        ))

    # --- Owner name ---
    name, role = _extract_owner(html)
    if name:
        contacts.append(ExtractedContact(
            email=None,
            name=name,
            role=role,
            source=ContactSource.website_about_page,
            confidence=0.6,
        ))

    return contacts
