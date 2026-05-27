import logging
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from decimal import Decimal

from shared.config import settings as app_settings
from web.auth import get_current_admin

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
logger = logging.getLogger(__name__)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    _: bool = Depends(get_current_admin),
):
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "active": "settings",
        "settings": app_settings,
        "saved": False,
    })


@router.post("/settings")
async def settings_save(
    request: Request,
    bonus_join: str = Form(...),
    bonus_reaction: str = Form(...),
    bonus_retention: str = Form(...),
    min_withdrawal: str = Form(...),
    _: bool = Depends(get_current_admin),
):
    # Update runtime values (apply until restart — persisted in .env manually)
    app_settings.bonus_join = Decimal(bonus_join)
    app_settings.bonus_reaction = Decimal(bonus_reaction)
    app_settings.bonus_retention = Decimal(bonus_retention)
    app_settings.min_withdrawal = Decimal(min_withdrawal)
    logger.info("Settings updated: join=%s reaction=%s retention=%s min_withdrawal=%s",
                bonus_join, bonus_reaction, bonus_retention, min_withdrawal)

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "active": "settings",
        "settings": app_settings,
        "saved": True,
    })
