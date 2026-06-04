from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_session
from app.core.rate_limit import limiter
from app.features.drafts.schemas import DraftOut, DraftRequest
from app.features.drafts.service import DraftGenerationError, generate_draft, list_drafts

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


@router.post("/{business_id}", response_model=DraftOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_draft(
    request: Request,
    business_id: int,
    payload: DraftRequest,
    session: AsyncSession = Depends(get_session),
) -> DraftOut:
    """Generate a personalised outreach draft for a lead.

    Rate-limited to 10 requests per minute per IP to prevent accidental loops
    that would burn LLM quota. Returns 503 if the LLM provider is unavailable.
    """
    try:
        return await generate_draft(
            session,
            business_id=business_id,
            channel=payload.channel,
            extra_context=payload.extra_context,
            created_by=None,  # Phase 5 will wire the authenticated user id here
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DraftGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Draft generation failed: {exc}",
        )


@router.get("/{business_id}", response_model=list[DraftOut])
async def get_drafts(
    business_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[DraftOut]:
    """Return all drafts generated for a business, newest first."""
    return await list_drafts(session, business_id=business_id)
