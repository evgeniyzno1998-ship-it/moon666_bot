from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from shared.database import get_session
from shared.models import User, Referral
from web.auth import get_current_admin

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/users", response_class=HTMLResponse)
async def users_page(
    request: Request,
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    query = (
        select(User, func.count(Referral.id).label("ref_count"))
        .outerjoin(Referral, Referral.referrer_id == User.id)
        .group_by(User.id)
        .order_by(func.count(Referral.id).desc())
    )
    if search:
        query = query.where(User.username.ilike(f"%{search}%"))

    result = await session.execute(query)
    users = result.all()

    return templates.TemplateResponse("users.html", {
        "request": request,
        "active": "users",
        "users": users,
        "search": search or "",
    })
