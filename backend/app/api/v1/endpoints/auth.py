from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.api.deps import (
    get_current_active_user,
    RoleChecker,
    login_rate_limiter
)
from app.models.user import User, UserRole
from app.schemas.v1.user import (
    UserCreate,
    UserOut,
    Token,
    LoginRequest,
    GoogleAuthRequest,
    EmailVerificationRequest,
    PasswordResetRequest,
    PasswordResetConfirm
)
from app.services.auth.auth_service import AuthService

router = APIRouter()

def set_tokens_in_cookies(response: Response, tokens: Token) -> None:
    is_secure = settings.ENV != "development"
    response.set_cookie(
        key="access_token",
        value=tokens.access_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

def clear_tokens_cookies(response: Response) -> None:
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")

@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Register a new user (initially unverified).
    """
    user = await AuthService.register_user(db, user_in)
    return user

@router.post("/login", response_model=Token, dependencies=[Depends(login_rate_limiter)])
async def login(
    response: Response,
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Authenticate email credentials and issue access + refresh tokens (and cookies).
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    tokens = await AuthService.login_user(
        db=db,
        login_data=login_data,
        ip_address=ip_address,
        user_agent=user_agent,
        device_info=user_agent
    )
    
    set_tokens_in_cookies(response, tokens)
    return tokens

@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    refresh_token: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Invalidate active refresh token in database and access token JTI in Redis blacklist.
    """
    # Try to extract refresh token from request body or cookie
    ref_token = refresh_token or request.cookies.get("refresh_token")
    acc_token = request.cookies.get("access_token") or request.headers.get("authorization")
    
    if acc_token and acc_token.startswith("Bearer "):
        acc_token = acc_token[7:]

    if not ref_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token is required to log out."
        )

    # Invalidate session
    await AuthService.logout_user(db, ref_token, acc_token or "")
    
    clear_tokens_cookies(response)
    return {"detail": "Successfully logged out."}

@router.post("/refresh", response_model=Token)
async def refresh(
    response: Response,
    request: Request,
    refresh_token: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Rotate and issue a fresh access + refresh token pair.
    """
    ref_token = refresh_token or request.cookies.get("refresh_token")
    if not ref_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing."
        )

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    tokens = await AuthService.refresh_jwt_tokens(
        db=db,
        refresh_token=ref_token,
        ip_address=ip_address,
        user_agent=user_agent,
        device_info=user_agent
    )
    
    set_tokens_in_cookies(response, tokens)
    return tokens

@router.post("/google", response_model=Token)
async def google_oauth(
    response: Response,
    request: Request,
    oauth_data: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Exchange Google OAuth code for JWT access + refresh tokens.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    tokens = await AuthService.exchange_google_oauth(
        db=db,
        code=oauth_data.code,
        ip_address=ip_address,
        user_agent=user_agent,
        device_info=user_agent
    )
    
    set_tokens_in_cookies(response, tokens)
    return tokens

@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_active_user)) -> Any:
    """
    Retrieve details of the currently authenticated active user.
    """
    return current_user

@router.post("/verify-email/request")
async def request_verification(
    req: EmailVerificationRequest,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Generate and dispatch a new email verification token.
    """
    await AuthService.request_email_verification(db, req.email)
    return {"detail": "If the account exists and is unverified, a verification email has been sent."}

@router.get("/verify-email/confirm")
async def confirm_verification(
    token: str,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Verify email verification token and activate user login privileges.
    """
    await AuthService.verify_email_token(db, token)
    return {"detail": "Email verified successfully. You can now log in."}

@router.post("/password-reset/request")
async def request_password_reset(
    req: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Generate and dispatch a password reset token to user email.
    """
    await AuthService.request_password_reset(db, req.email)
    return {"detail": "If the account exists, a password reset link has been sent to your email."}

@router.post("/password-reset/confirm")
async def confirm_password_reset(
    req: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Confirm password reset and configure new password credentials.
    """
    await AuthService.confirm_password_reset(db, req)
    return {"detail": "Password has been reset successfully. Previous sessions have been revoked."}

@router.get("/admin-only")
async def admin_only_test(
    current_user: User = Depends(RoleChecker([UserRole.ADMIN]))
) -> Any:
    """
    Protected route testing RBAC role validation dependencies.
    """
    return {"detail": f"Welcome Admin {current_user.email}!"}
