from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from shared.config import settings
from web.auth import create_access_token, get_current_admin
from web.routes import dashboard, analytics, withdrawals, users, settings as settings_route

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Moon666 Admin")

app.include_router(dashboard.router)
app.include_router(analytics.router)
app.include_router(withdrawals.router)
app.include_router(users.router)
app.include_router(settings_route.router)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == settings.admin_login and password == settings.admin_password:
        token = create_access_token({"sub": username})
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie("access_token", token, httponly=True, max_age=86400)
        return response
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "Неверный логин или пароль"}
    )


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response
