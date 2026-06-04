"""Technology detection — classifies a site's tech stack from raw HTML.

Single responsibility: given raw HTML, return a TechResult with:
  - cms_detected  : human-readable name of the CMS or framework found
  - tech_stack    : dict of all detected technologies (stored as JSONB)
  - opportunity_type: "website" | "automation" | "both" | "low"

Detection strategy — HTML fingerprinting (no JS execution needed):
  Modern frameworks (React, Next.js, Vue, Nuxt, Angular) leave clear traces in
  the HTML shell the server sends. We check script src paths, meta tags, and
  data attributes. Legacy CMS (WordPress, Wix, Squarespace, Joomla) embed
  generator meta tags or characteristic asset paths.

opportunity_type logic:
  - Modern framework detected  → "automation"  (tech is fine; sell automations)
  - Legacy/no-CMS detected     → "website"     (sell a new/better site)
  - Legacy + no signals later  → may become "both" in scoring stage
  - (Signals like chat/booking refine this further in signals.py)
"""
import re
from dataclasses import dataclass, field

from selectolax.parser import HTMLParser


@dataclass
class TechResult:
    cms_detected: str | None
    tech_stack: dict
    opportunity_type: str  # "website" | "automation" | "both" | "low"


# ---------------------------------------------------------------------------
# Pattern tables
# ---------------------------------------------------------------------------

# Each entry: (human label, list of patterns to search in the full HTML text)
_MODERN_FRAMEWORK_PATTERNS: list[tuple[str, list[str]]] = [
    ("Next.js",  ["/_next/static/", "__NEXT_DATA__", "next/dist"]),
    ("Nuxt.js",  ["__NUXT__", "/_nuxt/", "nuxt.config"]),
    ("Angular",  ["ng-version=", 'ng-version="', "<app-root", "angular.min.js"]),
    ("Vue.js",   ["vue.min.js", "vue.runtime", "data-v-", "__vue_app__"]),
    ("React",    ["react.production.min.js", "react-dom", "__reactFiber", 'id="root"']),
    ("Gatsby",   ["/gatsby-", "___gatsby", "gatsby-image"]),
    ("Svelte",   ["__svelte", "svelte/internal"]),
    ("Remix",    ["__remixContext", "/_remix/"]),
    ("Astro",    ["astro-island", "/_astro/"]),
]

_LEGACY_CMS_PATTERNS: list[tuple[str, list[str]]] = [
    ("WordPress",    ['content="WordPress', "/wp-content/", "/wp-includes/", "wp-json"]),
    ("Wix",          ["wix.com", "wixstatic.com", "wixsite.com", "X-Wix-"]),
    ("Squarespace",  ["squarespace.com", "squarespace-cdn", "Squarespace"]),
    ("Joomla",       ["/components/com_", "Joomla!", "joomla.javascript"]),
    ("Drupal",       ["Drupal.settings", "/sites/default/files/", "drupal.js"]),
    ("Shopify",      ["cdn.shopify.com", "Shopify.shop", "/shopify/"]),
    ("Webflow",      ["webflow.com", "Webflow", "wf-form"]),
    ("GoDaddy",      ["godaddy.com/websites", "secureserver.net"]),
    ("PrestaShop",   ["prestashop", "presta-"]),
    ("OpenCart",     ["catalog/view/theme", "OpenCart"]),
]


def _detect_patterns(
    html: str,
    patterns: list[tuple[str, list[str]]],
) -> list[str]:
    """Return the labels of all entries whose patterns match in *html*."""
    found: list[str] = []
    for label, signals in patterns:
        if any(signal in html for signal in signals):
            found.append(label)
    return found


def _has_https(html: str) -> bool:
    """Heuristic: check if canonical/og:url points to HTTPS."""
    canonical = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', html)
    if canonical:
        return canonical.group(1).startswith("https")
    og_url = re.search(r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)', html)
    if og_url:
        return og_url.group(1).startswith("https")
    return True  # assume HTTPS if we can't tell


def analyze(html: str) -> TechResult:
    """Classify the tech stack from raw *html* and derive the opportunity type."""
    modern = _detect_patterns(html, _MODERN_FRAMEWORK_PATTERNS)
    legacy = _detect_patterns(html, _LEGACY_CMS_PATTERNS)

    tech_stack: dict = {}
    if modern:
        tech_stack["modern_frameworks"] = modern
    if legacy:
        tech_stack["legacy_cms"] = legacy

    has_https = _has_https(html)
    tech_stack["has_https"] = has_https

    # Primary CMS label: prefer modern framework name, then legacy CMS name.
    if modern:
        cms_detected = modern[0]
        opportunity_type = "automation"
    elif legacy:
        cms_detected = legacy[0]
        opportunity_type = "website"
    else:
        cms_detected = None
        opportunity_type = "website"

    # Outdated HTTPS is an extra signal that keeps opportunity_type as "website".
    # Note: signals.py will later refine "website" → "both" if automation gaps exist.

    return TechResult(
        cms_detected=cms_detected,
        tech_stack=tech_stack,
        opportunity_type=opportunity_type,
    )
