# c:/Stock_Price_Forecast/backend/auth.py
"""
自前セッション認証（REQUIREMENTS_v2.md 1節/1.2節/6.1参照）。

ドメインを所有しないためCloudflare Accessが使えず、代わりに
共有パスワード + 署名付きセッションCookieによる最小限の認証を実装する。
自分専用アクセスが目的のため、ユーザー管理・ロール等は持たない。
"""

import os
import secrets

from fastapi import APIRouter, HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel

SESSION_COOKIE_NAME = "session"
SESSION_MAX_AGE_SECONDS = 30 * 24 * 3600  # 30日間
_SALT = "stock-app-session"

# 本番(VM上のCaddy経由HTTPS)ではSecure Cookie + SameSite=Noneが必須
# （frontend: *.pages.dev, backend: DuckDNSドメインでオリジンが異なるため）。
# ローカル開発(http)ではSecure Cookieを送れないため、ENV=production以外は緩和する。
_IS_PRODUCTION = os.getenv("ENV", "development") == "production"


def _get_serializer() -> URLSafeTimedSerializer:
    secret = os.getenv("SESSION_SECRET")
    if not secret:
        raise RuntimeError("SESSION_SECRET が設定されていません（.env.example参照）")
    return URLSafeTimedSerializer(secret, salt=_SALT)


def _get_app_password() -> str:
    password = os.getenv("APP_PASSWORD")
    if not password:
        raise RuntimeError("APP_PASSWORD が設定されていません（.env.example参照）")
    return password


def set_session_cookie(response: Response) -> None:
    token = _get_serializer().dumps({"authenticated": True})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=_IS_PRODUCTION,
        samesite="none" if _IS_PRODUCTION else "lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=_IS_PRODUCTION,
        samesite="none" if _IS_PRODUCTION else "lax",
    )


def is_authenticated(request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return False
    try:
        _get_serializer().loads(token, max_age=SESSION_MAX_AGE_SECONDS)
        return True
    except (BadSignature, SignatureExpired):
        return False


def require_auth(request: Request) -> None:
    """保護したいエンドポイントに `Depends(require_auth)` として付与する。"""
    if not is_authenticated(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ログインが必要です")


# --------- ログイン用ルーター（require_authでは保護しない） ---------
router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


class AuthStatusResponse(BaseModel):
    authenticated: bool


@router.post("/login", response_model=AuthStatusResponse)
def login(payload: LoginRequest, response: Response):
    # タイミング攻撃対策のためsecrets.compare_digestで比較
    if not secrets.compare_digest(payload.password, _get_app_password()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="パスワードが違います")
    set_session_cookie(response)
    return AuthStatusResponse(authenticated=True)


@router.post("/logout", response_model=AuthStatusResponse)
def logout(response: Response):
    clear_session_cookie(response)
    return AuthStatusResponse(authenticated=False)


@router.get("/status", response_model=AuthStatusResponse)
def auth_status(request: Request):
    return AuthStatusResponse(authenticated=is_authenticated(request))
