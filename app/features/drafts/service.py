"""Draft generation service — orchestrates context assembly, LLM call, and persistence.

Does not know about HTTP. Errors are raised as specific exceptions for the
router to translate into appropriate HTTP responses.
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.features.businesses import repository as businesses_repo
from app.features.drafts import repository as drafts_repo
from app.features.drafts.models import DraftChannel, MessageDraft
from app.features.drafts.schemas import DraftOut
from app.features.leads import repository as leads_repo
from app.integrations.llm.client import get_llm_client
from app.integrations.llm.prompts import DRAFT_SYSTEM_PROMPT, build_draft_prompt

logger = logging.getLogger(__name__)


class DraftGenerationError(Exception):
    """Raised when the LLM call fails or times out."""


async def generate_draft(
    session: AsyncSession,
    *,
    business_id: int,
    channel: DraftChannel,
    extra_context: str | None,
    created_by: int | None,
) -> DraftOut:
    """Generate and persist a personalised message draft for *business_id*.

    Raises:
        ValueError:           if the business does not exist.
        DraftGenerationError: if the LLM call fails or times out.
    """
    # --- Load context from DB --------------------------------------------------
    business = await businesses_repo.get_business_by_id(session, business_id)
    if business is None:
        raise ValueError(f"Business {business_id} not found")

    analysis = await businesses_repo.get_website_analysis(session, business_id)

    # opportunity_type comes from the lead score breakdown (set by scoring v2).
    # This is the final refined type (website/automation/both/low), not the raw
    # tech detection output — so it already accounts for automation signal gaps.
    lead_score = await leads_repo.get_lead_score(session, business_id)
    opportunity_type = "website"
    if lead_score and lead_score.breakdown:
        opportunity_type = lead_score.breakdown.get("opportunity_type", "website")

    # --- Build prompt and call LLM ---------------------------------------------
    user_prompt = build_draft_prompt(
        business_name=business.name,
        category=business.category,
        address=business.address,
        opportunity_type=opportunity_type,
        cms_detected=analysis.cms_detected if analysis else None,
        has_chat=analysis.has_chat if analysis else False,
        has_booking=analysis.has_booking if analysis else False,
        channel=channel.value,
        extra_context=extra_context,
    )

    try:
        llm = get_llm_client()
        raw_response = await llm.generate(DRAFT_SYSTEM_PROMPT, user_prompt)
    except Exception as exc:
        logger.error("Draft generation failed for business_id=%d: %s", business_id, exc)
        raise DraftGenerationError(str(exc)) from exc

    # --- Parse response and persist --------------------------------------------
    subject, body = _parse_email_response(raw_response, channel)

    draft = await drafts_repo.create_draft(
        session,
        business_id=business_id,
        channel=channel,
        subject=subject,
        body=body,
        model_used=get_settings().gemini_model,
        created_by=created_by,
    )
    return DraftOut.model_validate(draft)


async def list_drafts(
    session: AsyncSession,
    business_id: int,
) -> list[DraftOut]:
    drafts = await drafts_repo.list_drafts_for_business(session, business_id)
    return [DraftOut.model_validate(d) for d in drafts]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_email_response(raw: str, channel: DraftChannel) -> tuple[str | None, str]:
    """Split the LLM response into (subject, body).

    For email the model is instructed to output:
        SUBJECT: <subject line>
        <blank line>
        <body>

    For other channels the full response is the body with no subject.
    If the model ignores the format for email, the full text becomes the body.
    """
    if channel != DraftChannel.email:
        return None, raw.strip()

    lines = raw.strip().splitlines()
    if lines and lines[0].upper().startswith("SUBJECT:"):
        subject = lines[0][len("SUBJECT:"):].strip()
        rest = lines[2:] if len(lines) > 2 and lines[1].strip() == "" else lines[1:]
        return subject, "\n".join(rest).strip()

    return None, raw.strip()
