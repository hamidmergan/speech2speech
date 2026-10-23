"""The way in, when a password is configured. Without one these routes still answer."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from src import access
from src.i18n import get_locale, t

router = APIRouter(tags=["access"])


class PasswordIn(BaseModel):
    password: str = Field(min_length=1, max_length=512)


@router.get("/access")
def access_state(request: Request) -> dict:
    """Whether a password is wanted, and whether this browser already gave it."""
    return {
        "required": access.required(),
        "authenticated": not access.required()
        or access.token_valid(request.cookies.get(access.COOKIE_NAME)),
    }


@router.post("/access/login")
def login(
    body: PasswordIn,
    response: Response,
    locale: str = Depends(get_locale),
) -> dict:
    if not access.required():
        # Nothing to give. Saying so beats handing out a cookie nobody checks.
        return {"required": False, "authenticated": True}
    if not access.password_matches(body.password):
        raise HTTPException(status_code=401, detail=t("access.wrongPassword", locale))
    response.set_cookie(
        key=access.COOKIE_NAME,
        value=access.make_token(),
        httponly=True,
        samesite="lax",
        max_age=access.COOKIE_MAX_AGE,
    )
    return {"required": True, "authenticated": True}


@router.post("/access/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(key=access.COOKIE_NAME)
    return {"required": access.required(), "authenticated": not access.required()}
