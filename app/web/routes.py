from datetime import date

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import SessionDep
from app.features.businesses import service as business_service
from app.features.businesses.constants import BusinessSortBy
from app.features.campaigns import repository as campaign_repo
from app.features.campaigns import service as campaign_service
from app.features.campaigns.schemas import CampaignCreate
from app.features.drafts import service as drafts_service
from app.features.leads import service as leads_service
from app.features.leads.models import LeadStatusChoice
from app.features.leads.schemas import LeadStatusUpdate
from app.pipeline import orchestrator

templates = Jinja2Templates(directory="app/web/templates")
router = APIRouter(tags=["web"])


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, session: SessionDep) -> HTMLResponse:
    stats = await leads_service.get_dashboard_stats(session)
    top_leads = await leads_service.list_leads(
        session, page=1, size=5, has_website=None,
    )
    recent_runs = await campaign_repo.list_recent_runs(session, limit=5)
    return templates.TemplateResponse(request, "home.html", {
        "stats": stats,
        "top_leads": top_leads,
        "recent_runs": recent_runs,
        "today": date.today().strftime("%A, %d %b %Y"),
        "all_statuses": [s.value for s in LeadStatusChoice],
        "all_opp_types": ["website", "both", "automation", "low"],
    })


@router.get("/campaigns", response_class=HTMLResponse)
async def campaigns_page(request: Request, session: SessionDep) -> HTMLResponse:
    campaigns = await campaign_service.list_campaigns(session, offset=0, limit=50)
    return templates.TemplateResponse(request, "campaigns/index.html", {"campaigns": campaigns})


@router.post("/campaigns", response_class=RedirectResponse)
async def create_campaign_form(request: Request, session: SessionDep) -> RedirectResponse:
    form = await request.form()
    lat = form.get("lat")
    lng = form.get("lng")
    radius = form.get("radius_meters")

    location_bias = None
    if lat and lng:
        from app.features.campaigns.schemas import LocationBiasSchema
        location_bias = LocationBiasSchema(
            lat=float(lat),
            lng=float(lng),
            radius_meters=float(radius) if radius else 5000.0,
        )

    data = CampaignCreate(
        name=str(form["name"]),
        area_text=str(form["area_text"]),
        business_type=str(form["business_type"]),
        location_bias=location_bias,
    )
    campaign = await campaign_service.create_campaign(session, data)
    return RedirectResponse(url=f"/campaigns/{campaign.id}", status_code=303)


@router.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
async def campaign_detail(
    request: Request, campaign_id: int, session: SessionDep
) -> HTMLResponse:
    campaign = await campaign_service.get_campaign_or_404(session, campaign_id)
    runs = await campaign_service.list_search_runs(session, campaign_id)
    return templates.TemplateResponse(
        request, "campaigns/detail.html", {"campaign": campaign, "runs": runs}
    )


@router.post("/campaigns/{campaign_id}/runs", response_class=RedirectResponse)
async def trigger_run_form(
    campaign_id: int,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> RedirectResponse:
    campaign = await campaign_service.get_campaign_or_404(session, campaign_id)
    run = await campaign_repo.create_search_run(session, campaign.id)
    background_tasks.add_task(orchestrator.run_search, run.id, campaign_id)
    return RedirectResponse(
        url=f"/campaigns/{campaign_id}/runs/{run.id}", status_code=303
    )


@router.get("/campaigns/{campaign_id}/runs/{run_id}", response_class=HTMLResponse)
async def run_status_page(
    request: Request, campaign_id: int, run_id: int, session: SessionDep
) -> HTMLResponse:
    campaign = await campaign_service.get_campaign_or_404(session, campaign_id)
    run = await campaign_service.get_search_run_or_404(session, run_id)
    return templates.TemplateResponse(
        request, "campaigns/run_status.html", {
            "campaign": campaign,
            "run": run,
            "campaign_id": campaign_id,
        }
    )


@router.get("/campaigns/{campaign_id}/runs/{run_id}/poll", response_class=HTMLResponse)
async def run_status_poll(
    request: Request, campaign_id: int, run_id: int, session: SessionDep
) -> HTMLResponse:
    run = await campaign_service.get_search_run_or_404(session, run_id)
    return templates.TemplateResponse(
        request, "campaigns/_run_poll.html", {"run": run, "campaign_id": campaign_id}
    )


@router.get("/businesses", response_class=HTMLResponse)
async def businesses_page(
    request: Request,
    session: SessionDep,
    sort_by: BusinessSortBy = BusinessSortBy.name,
    ref_lat: float | None = None,
    ref_lng: float | None = None,
) -> HTMLResponse:
    businesses = await business_service.list_businesses(
        session, offset=0, limit=100, sort_by=sort_by, ref_lat=ref_lat, ref_lng=ref_lng
    )
    return templates.TemplateResponse(
        request,
        "businesses/list.html",
        {"businesses": businesses, "sort_by": sort_by, "ref_lat": ref_lat, "ref_lng": ref_lng},
    )


@router.get("/leads", response_class=HTMLResponse)
async def leads_page(
    request: Request,
    session: SessionDep,
    status: LeadStatusChoice | None = None,
    opportunity_type: str | None = None,
) -> HTMLResponse:
    leads = await leads_service.list_leads(
        session, page=1, size=100,
        has_website=None, status=status, opportunity_type=opportunity_type,
    )
    return templates.TemplateResponse(
        request, "leads/list.html", {
            "leads": leads,
            "status_filter": status,
            "opportunity_type_filter": opportunity_type,
            "all_statuses": list(LeadStatusChoice),
            "all_opportunity_types": ["website", "automation", "both", "low"],
        },
    )


@router.get("/leads/table", response_class=HTMLResponse)
async def leads_table(
    request: Request,
    session: SessionDep,
    status: LeadStatusChoice | None = None,
    opportunity_type: str | None = None,
) -> HTMLResponse:
    leads = await leads_service.list_leads(
        session, page=1, size=100,
        has_website=None, status=status, opportunity_type=opportunity_type,
    )
    return templates.TemplateResponse(
        request, "leads/_table.html", {
            "leads": leads,
            "status_filter": status,
            "opportunity_type_filter": opportunity_type,
            "all_statuses": list(LeadStatusChoice),
        },
    )


@router.patch("/leads/{business_id}/status", response_class=HTMLResponse)
async def update_lead_status_inline(
    request: Request,
    business_id: int,
    session: SessionDep,
) -> HTMLResponse:
    """HTMX endpoint: inline status dropdown in the leads list.

    Receives form data with only 'status' — notes are intentionally NOT
    included so the salesperson's existing notes are preserved.
    """
    form = await request.form()
    status_str = str(form["status"])
    payload = LeadStatusUpdate(status=LeadStatusChoice(status_str))
    await leads_service.update_status(session, business_id, payload)
    lead = await leads_service.get_lead_or_404(session, business_id)
    return templates.TemplateResponse(
        request, "leads/_row.html", {
            "lead": lead,
            "all_statuses": list(LeadStatusChoice),
        },
    )


@router.post("/leads/{business_id}/status", response_class=RedirectResponse)
async def update_lead_status_form(
    request: Request,
    business_id: int,
    session: SessionDep,
) -> RedirectResponse:
    """Form POST from the lead detail page — saves status + notes together."""
    form = await request.form()
    status_str = str(form["status"])
    notes = form.get("notes")
    payload = LeadStatusUpdate(
        status=LeadStatusChoice(status_str),
        notes=str(notes) if notes else None,
    )
    await leads_service.update_status(session, business_id, payload)
    return RedirectResponse(url=f"/leads/{business_id}", status_code=303)


@router.get("/leads/{business_id}", response_class=HTMLResponse)
async def lead_detail(
    request: Request,
    business_id: int,
    session: SessionDep,
) -> HTMLResponse:
    lead = await leads_service.get_lead_or_404(session, business_id)
    business = await business_service.get_business_or_404(session, business_id)
    analysis = await business_service.get_website_analysis(session, business_id)
    contacts = await business_service.get_contacts(session, business_id)
    drafts = await drafts_service.list_drafts(session, business_id)
    return templates.TemplateResponse(
        request, "leads/detail.html", {
            "lead": lead,
            "business": business,
            "analysis": analysis,
            "contacts": contacts,
            "drafts": drafts,
            "all_statuses": list(LeadStatusChoice),
        },
    )


@router.get("/businesses/table", response_class=HTMLResponse)
async def businesses_table(
    request: Request,
    session: SessionDep,
    sort_by: BusinessSortBy = BusinessSortBy.name,
    ref_lat: float | None = None,
    ref_lng: float | None = None,
) -> HTMLResponse:
    businesses = await business_service.list_businesses(
        session, offset=0, limit=100, sort_by=sort_by, ref_lat=ref_lat, ref_lng=ref_lng
    )
    return templates.TemplateResponse(
        request,
        "businesses/_table.html",
        {"businesses": businesses, "sort_by": sort_by, "ref_lat": ref_lat, "ref_lng": ref_lng},
    )
