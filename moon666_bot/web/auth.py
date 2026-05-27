from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt

from shared.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=ALGORITHM)


def verify_token(token: str) -> bool:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return payload.get("sub") == settings.admin_login
    except JWTError:
        return False


async def get_current_admin(request: Request):
    token = request.cookies.get("access_token")
    if not token or not verify_token(token):
        return RedirectResponse(url="/login", status_code=302)
    return True
