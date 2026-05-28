from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_session
from shared.models import Campaign, CampaignBonusType
from web.auth import get_current_admin

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/campaigns", response_class=HTMLResponse)
async def campaigns_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    result = await session.execute(select(Campaign).order_by(Campaign.starts_at.desc()))
    campaigns = result.scalars().all()
    now = datetime.now(timezone.utc)
    return templates.TemplateResponse("campaigns.html", {
        "request": request,
        "active": "campaigns",
        "campaigns": campaigns,
        "now": now,
    })


@router.get("/campaigns/new", response_class=HTMLResponse)
async def new_campaign_form(
    request: Request,
    _: bool = Depends(get_current_admin),
):
    return templates.TemplateResponse("campaign_form.html", {
        "request": request,
        "active": "campaigns",
        "campaign": None,
        "bonus_types": list(CampaignBonusType),
    })


@router.post("/campaigns")
async def create_campaign(
    name: str = Form(...),
    bonus_multiplier: Decimal = Form(...),
    applies_to: str = Form(...),
    starts_at: str = Form(...),
    ends_at: str = Form(...),
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    campaign = Campaign(
        name=name,
        bonus_multiplier=bonus_multiplier,
        applies_to=CampaignBonusType(applies_to),
        starts_at=datetime.fromisoformat(starts_at).replace(tzinfo=timezone.utc),
        ends_at=datetime.fromisoformat(ends_at).replace(tzinfo=timezone.utc),
    )
    session.add(campaign)
    await session.commit()
    return RedirectResponse(url="/campaigns", status_code=302)


@router.get("/campaigns/{campaign_id}/edit", response_class=HTMLResponse)
async def edit_campaign_form(
    campaign_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    campaign = await session.get(Campaign, campaign_id)
    if not campaign:
        return RedirectResponse(url="/campaigns", status_code=302)
    return templates.TemplateResponse("campaign_form.html", {
        "request": request,
        "active": "campaigns",
        "campaign": campaign,
        "bonus_types": list(CampaignBonusType),
    })


@router.post("/campaigns/{campaign_id}")
async def update_campaign(
    campaign_id: int,
    name: str = Form(...),
    bonus_multiplier: Decimal = Form(...),
    applies_to: str = Form(...),
    starts_at: str = Form(...),
    ends_at: str = Form(...),
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    campaign = await session.get(Campaign, campaign_id)
    if campaign:
        campaign.name = name
        campaign.bonus_multiplier = bonus_multiplier
        campaign.applies_to = CampaignBonusType(applies_to)
        campaign.starts_at = datetime.fromisoformat(starts_at).replace(tzinfo=timezone.utc)
        campaign.ends_at = datetime.fromisoformat(ends_at).replace(tzinfo=timezone.utc)
        await session.commit()
    return RedirectResponse(url="/campaigns", status_code=302)


@router.post("/campaigns/{campaign_id}/delete")
async def delete_campaign(
    campaign_id: int,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    campaign = await session.get(Campaign, campaign_id)
    if campaign:
        await session.delete(campaign)
        await session.commit()
    return RedirectResponse(url="/campaigns", status_code=302)
