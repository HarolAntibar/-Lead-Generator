from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.core.dependencies import SessionDep
from app.features.auth import service
from app.features.auth.constants import SESSION_USER_ID_KEY
from app.features.auth.exceptions import InactiveUserError, InvalidCredentialsError

templates = Jinja2Templates(directory="app/web/templates")
router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    if request.session.get(SESSION_USER_ID_KEY):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "auth/login.html", {})


@router.post("/login")
async def login(request: Request, session: SessionDep) -> Response:
    form = await request.form()
    try:
        user = await service.authenticate(
            session,
            email=str(form["email"]),
            password=str(form["password"]),
        )
    except (InvalidCredentialsError, InactiveUserError):
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"error": "Invalid credentials or account is inactive"},
            status_code=401,
        )
    request.session[SESSION_USER_ID_KEY] = user.id
    next_url = request.query_params.get("next", "/")
    # Guard against open-redirect: only follow local paths
    if not next_url.startswith("/"):
        next_url = "/"
    return RedirectResponse(next_url, status_code=303)


@router.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/auth/login", status_code=303)
