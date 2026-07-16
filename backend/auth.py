# c:/Stock_Price_Forecast/backend/auth.py
"""
自前セッション認証（REQUIREMENTS_v2.md 1節/1.2節/6.1参照）。

ドメインを所有しないためCloudflare Accessが使えず、代わりに
共有パスワード + 署名付きトークンによる最小限の認証を実装する。
自分専用アクセスが目的のため、ユーザー管理・ロール等は持たない。

2026-07-16改訂: Cookie方式からAuthorizationヘッダー(Bearerトークン)方式に変更。
フロントエンド(*.workers.dev)とバックエンド(DuckDNSドメイン)が別サイトのため、
ブラウザのサードパーティCookieブロック機能により、SameSite=None/Secureを
正しく設定してもCookieが保存/送信されないケースが確認されたため。
トークンをlocalStorageに保存しAuthorizationヘッダーで送る方式はこの制約を受けない。
"""

import os
import secrets

from fastapi import APIRouter, HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel

SESSION_MAX_AGE_SECONDS = 30 * 24 * 3600  # 30日間
_SALT = "stock-app-session"


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


def create_session_token() -> str:
    return _get_serializer().dumps({"authenticated": True})


def _extract_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.removeprefix("Bearer ").strip()
    return token or None


def is_authenticated(request: Request) -> bool:
    token = _extract_token(request)
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


class LoginResponse(BaseModel):
    authenticated: bool
    token: str = ""


class AuthStatusResponse(BaseModel):
    authenticated: bool


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    # タイミング攻撃対策のためsecrets.compare_digestで比較
    if not secrets.compare_digest(payload.password, _get_app_password()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="パスワードが違います")
    token = create_session_token()
    return LoginResponse(authenticated=True, token=token)


@router.post("/logout", response_model=AuthStatusResponse)
def logout():
    # トークンはステートレスなためサーバー側に破棄すべき状態はない。
    # クライアント側でlocalStorageから削除することでログアウトを実現する。
    return AuthStatusResponse(authenticated=False)


@router.get("/status", response_model=AuthStatusResponse)
def auth_status(request: Request):
    return AuthStatusResponse(authenticated=is_authenticated(request))
