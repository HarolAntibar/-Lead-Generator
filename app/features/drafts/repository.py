from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.drafts.models import DraftChannel, MessageDraft


async def create_draft(
    session: AsyncSession,
    *,
    business_id: int,
    channel: DraftChannel,
    subject: str | None,
    body: str,
    model_used: str | None,
    created_by: int | None,
) -> MessageDraft:
    draft = MessageDraft(
        business_id=business_id,
        channel=channel,
        subject=subject,
        body=body,
        model_used=model_used,
        created_by=created_by,
    )
    session.add(draft)
    await session.commit()
    await session.refresh(draft)
    return draft


async def list_drafts_for_business(
    session: AsyncSession,
    business_id: int,
) -> list[MessageDraft]:
    result = await session.execute(
        select(MessageDraft)
        .where(MessageDraft.business_id == business_id)
        .order_by(MessageDraft.id.desc())
    )
    return list(result.scalars().all())
