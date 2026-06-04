"""Website scraper — downloads raw HTML using httpx.

Single responsibility: given a URL, return the HTML string or None.
No parsing, no extraction — those happen in tech_detect, signals, and extract stages.

Design decisions:
- httpx only (no JS execution): the HTML shell is enough to fingerprint the tech stack
  and detect signals. Modern-framework sites (React, Next.js, Vue) leave clear traces
  in script tags even without rendering.
- robots.txt is checked before fetching any page. We skip the site if it disallows
  the root path for our User-Agent. Using stdlib urllib.robotparser — no extra dep.
- Content is capped at scraper_max_content_bytes to avoid downloading PDFs or huge
  pages that would waste memory and add no value to the analysis.
"""
import logging
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _build_client() -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        timeout=settings.scraper_timeout_seconds,
        max_redirects=settings.scraper_max_redirects,
        headers={"User-Agent": settings.scraper_user_agent},
        follow_redirects=True,
    )


async def _is_allowed_by_robots(client: httpx.AsyncClient, url: str) -> bool:
    """Return True if our bot is allowed to fetch *url* per robots.txt."""
    parsed = urlparse(url)
    robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")

    try:
        response = await client.get(robots_url)
        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        settings = get_settings()
        return parser.can_fetch(settings.scraper_user_agent, url)
    except Exception:
        # If robots.txt is unreachable we assume access is allowed — common for
        # small business sites that don't publish one.
        return True


async def fetch_html(url: str) -> str | None:
    """Fetch *url* and return the raw HTML, or None on any failure.

    Checks robots.txt first. Caps the response body at scraper_max_content_bytes
    so we never pull in a 50 MB file by accident.
    """
    settings = get_settings()

    async with _build_client() as client:
        if not await _is_allowed_by_robots(client, url):
            logger.info("scraper: robots.txt disallows %s — skipping", url)
            return None

        try:
            # stream=True lets us read only up to the byte cap without downloading
            # the whole response body first.
            async with client.stream("GET", url) as response:
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                if "html" not in content_type.lower():
                    logger.info(
                        "scraper: non-HTML content-type '%s' at %s — skipping",
                        content_type, url,
                    )
                    return None

                chunks: list[bytes] = []
                bytes_read = 0
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    chunks.append(chunk)
                    bytes_read += len(chunk)
                    if bytes_read >= settings.scraper_max_content_bytes:
                        logger.debug(
                            "scraper: content cap reached (%d bytes) for %s",
                            bytes_read, url,
                        )
                        break

                return b"".join(chunks).decode("utf-8", errors="replace")

        except httpx.HTTPStatusError as exc:
            logger.warning("scraper: HTTP %d for %s", exc.response.status_code, url)
            return None
        except httpx.TimeoutException:
            logger.warning("scraper: timeout for %s", url)
            return None
        except httpx.RequestError as exc:
            logger.warning("scraper: request error for %s — %s", url, exc)
            return None
