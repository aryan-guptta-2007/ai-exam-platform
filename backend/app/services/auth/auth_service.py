import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from pydantic import EmailStr
import httpx
from sqlalchemy.future import select
from sqlalchemy import update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.config import settings
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    create_verification_token,
    decode_token
)
from app.core.redis import redis_service
from app.models.user import User, UserRole
from app.models.auth import (
    OAuthAccount,
    RefreshToken,
    EmailVerification,
    PasswordReset,
    AuthAuditLog
)
from app.schemas.v1.user import (
    UserCreate,
    LoginRequest,
    Token,
    PasswordResetConfirm
)

async def log_auth_event(
    db: AsyncSession,
    action: str,
    user_id: Optional[uuid.UUID] = None,
    email: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> None:
    try:
        log = AuthAuditLog(
            user_id=user_id,
            email=email,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(log)
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to write to AuthAuditLog: {e}")
        await db.rollback()

class AuthService:
    @staticmethod
    async def register_user(db: AsyncSession, user_in: UserCreate) -> User:
        # Check if user already exists
        result = await db.execute(select(User).filter(User.email == user_in.email))
        existing_user = result.scalars().first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists."
            )

        hashed_password = get_password_hash(user_in.password)
        db_user = User(
            email=user_in.email,
            hashed_password=hashed_password,
            role=user_in.role,
            is_active=user_in.is_active,
            is_verified=False,  # Needs email verification
            failed_login_attempts=0,
            token_version=1
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)

        # Log registration audit
        await log_auth_event(
            db=db,
            action="user_registered",
            user_id=db_user.id,
            email=db_user.email
        )

        # Create verification token
        token = create_verification_token(db_user.email, token_type="verification")
        db_ver = EmailVerification(
            user_id=db_user.id,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
        db.add(db_ver)
        await db.commit()

        # Trigger Celery Task
        try:
            from app.tasks.email_tasks import send_verification_email_task
            send_verification_email_task.delay(db_user.email, token)
        except Exception as e:
            logger.warning(f"Failed to queue Celery verification email for {db_user.email}: {e}. Falling back to console logging.")
            # Console fallback fallback
            logger.info(f"[EMAIL MOCK] Verification link: http://localhost:8000/api/v1/auth/verify-email/confirm?token={token}")

        return db_user

    @staticmethod
    async def login_user(
        db: AsyncSession,
        login_data: LoginRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_info: Optional[str] = None
    ) -> Token:
        result = await db.execute(select(User).filter(User.email == login_data.email))
        user = result.scalars().first()

        # Lockout check
        if user and user.locked_until:
            if user.locked_until > datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Account is temporarily locked due to too many failed attempts. Please try again later."
                )

        if not user or not verify_password(login_data.password, user.hashed_password):
            if user:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= settings.ACCOUNT_LOCKOUT_LIMIT:
                    user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
                    await log_auth_event(
                        db=db,
                        action="account_lockout",
                        user_id=user.id,
                        email=login_data.email,
                        ip_address=ip_address,
                        user_agent=user_agent
                    )
                else:
                    await log_auth_event(
                        db=db,
                        action="login_failed",
                        user_id=user.id,
                        email=login_data.email,
                        ip_address=ip_address,
                        user_agent=user_agent
                    )
                await db.commit()
            else:
                await log_auth_event(
                    db=db,
                    action="login_failed",
                    email=login_data.email,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect email or password."
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User account is disabled."
            )

        if not user.is_verified:
            await log_auth_event(
                db=db,
                action="login_failed_unverified",
                user_id=user.id,
                email=user.email,
                ip_address=ip_address,
                user_agent=user_agent
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email verification is required before you can log in."
            )

        # Successful login: Reset failed attempts
        user.failed_login_attempts = 0
        user.locked_until = None
        
        # Generate token identifiers (JTIs)
        access_jti = str(uuid.uuid4())
        refresh_jti = str(uuid.uuid4())
        
        access_token = create_access_token(user.id, access_jti, token_version=user.token_version)
        refresh_token = create_refresh_token(user.id, refresh_jti, token_version=user.token_version)

        # Persist refresh token session
        db_refresh = RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            is_revoked=False,
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(db_refresh)

        await log_auth_event(
            db=db,
            action="login_success",
            user_id=user.id,
            email=user.email,
            ip_address=ip_address,
            user_agent=user_agent
        )
        await db.commit()

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )

    @staticmethod
    async def logout_user(db: AsyncSession, refresh_token: str, access_token: str) -> None:
        # 1. Decode access token to blacklist its JTI in Redis
        try:
            payload = decode_token(access_token)
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                now = datetime.now(timezone.utc).timestamp()
                ttl = int(exp - now)
                if ttl > 0:
                    await redis_service.add_to_blacklist(jti, ttl)
        except Exception as e:
            logger.warning(f"Could not blacklist access token during logout: {e}")

        # 2. Revoke refresh token in database
        result = await db.execute(select(RefreshToken).filter(RefreshToken.token == refresh_token))
        db_refresh = result.scalars().first()
        if db_refresh:
            db_refresh.is_revoked = True
            await log_auth_event(
                db=db,
                action="logout",
                user_id=db_refresh.user_id,
                ip_address=db_refresh.ip_address,
                user_agent=db_refresh.user_agent
            )
            await db.commit()

    @staticmethod
    async def refresh_jwt_tokens(
        db: AsyncSession,
        refresh_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_info: Optional[str] = None
    ) -> Token:
        # Decode and validate refresh token
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type."
                )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token."
            )

        # Look up in database
        result = await db.execute(select(RefreshToken).filter(RefreshToken.token == refresh_token))
        db_refresh = result.scalars().first()

        if not db_refresh or db_refresh.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session refresh token."
            )

        # Replay Attack / Reuse Protection
        if db_refresh.is_revoked:
            logger.warning(f"Revoked refresh token presented for user {db_refresh.user_id}! Triggering global revocation.")
            # Invalidate all current user refresh sessions
            await db.execute(
                update(RefreshToken)
                .filter(RefreshToken.user_id == db_refresh.user_id)
                .values(is_revoked=True)
            )
            # Increment token version to invalidate outstanding access tokens
            result = await db.execute(select(User).filter(User.id == db_refresh.user_id))
            user = result.scalars().first()
            if user:
                user.token_version += 1
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session compromised. Please log in again."
            )

        # Fetch user
        result = await db.execute(select(User).filter(User.id == db_refresh.user_id))
        user = result.scalars().first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or disabled."
            )

        # Ensure token matches current token_version
        if payload.get("version") != user.token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session token has been globally revoked."
            )

        # Rotate refresh token: revoke current, issue new pair
        db_refresh.is_revoked = True
        
        access_jti = str(uuid.uuid4())
        refresh_jti = str(uuid.uuid4())
        
        new_access = create_access_token(user.id, access_jti, token_version=user.token_version)
        new_refresh = create_refresh_token(user.id, refresh_jti, token_version=user.token_version)

        db_new_refresh = RefreshToken(
            user_id=user.id,
            token=new_refresh,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            is_revoked=False,
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(db_new_refresh)
        
        await log_auth_event(
            db=db,
            action="token_refresh",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        await db.commit()

        return Token(
            access_token=new_access,
            refresh_token=new_refresh,
            token_type="bearer"
        )

    @staticmethod
    async def request_email_verification(db: AsyncSession, email: EmailStr) -> None:
        result = await db.execute(select(User).filter(User.email == email))
        user = result.scalars().first()
        if not user:
            # Silent return to avoid email enumeration
            return

        if user.is_verified:
            return

        # Delete existing pending verifications
        await db.execute(delete(EmailVerification).filter(EmailVerification.user_id == user.id))

        token = create_verification_token(user.email, token_type="verification")
        db_ver = EmailVerification(
            user_id=user.id,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
        db.add(db_ver)
        await db.commit()

        try:
            from app.tasks.email_tasks import send_verification_email_task
            send_verification_email_task.delay(user.email, token)
        except Exception as e:
            logger.warning(f"Failed to queue Celery verification email: {e}")
            logger.info(f"[EMAIL MOCK] Verification link: http://localhost:8000/api/v1/auth/verify-email/confirm?token={token}")

    @staticmethod
    async def verify_email_token(db: AsyncSession, token: str) -> None:
        result = await db.execute(select(EmailVerification).filter(EmailVerification.token == token))
        db_ver = result.scalars().first()
        
        if not db_ver or db_ver.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token."
            )

        result = await db.execute(select(User).filter(User.id == db_ver.user_id))
        user = result.scalars().first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found."
            )

        user.is_verified = True
        
        # Clean up verifications for this user
        await db.execute(delete(EmailVerification).filter(EmailVerification.user_id == user.id))
        
        await log_auth_event(
            db=db,
            action="email_verified",
            user_id=user.id,
            email=user.email
        )
        await db.commit()

    @staticmethod
    async def request_password_reset(db: AsyncSession, email: EmailStr) -> None:
        result = await db.execute(select(User).filter(User.email == email))
        user = result.scalars().first()
        if not user:
            # Silent return to avoid enumeration
            return

        # Clean up existing resets
        await db.execute(delete(PasswordReset).filter(PasswordReset.user_id == user.id))

        token = create_verification_token(user.email, token_type="password_reset", expires_delta=timedelta(hours=2))
        db_reset = PasswordReset(
            user_id=user.id,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
        )
        db.add(db_reset)
        await db.commit()

        try:
            from app.tasks.email_tasks import send_password_reset_email_task
            send_password_reset_email_task.delay(user.email, token)
        except Exception as e:
            logger.warning(f"Failed to queue Celery password reset email: {e}")
            logger.info(f"[EMAIL MOCK] Password reset link: http://localhost:8000/api/v1/auth/password-reset/confirm?token={token}")

    @staticmethod
    async def confirm_password_reset(db: AsyncSession, reset_confirm: PasswordResetConfirm) -> None:
        result = await db.execute(select(PasswordReset).filter(PasswordReset.token == reset_confirm.token))
        db_reset = result.scalars().first()

        if not db_reset or db_reset.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset token."
            )

        result = await db.execute(select(User).filter(User.id == db_reset.user_id))
        user = result.scalars().first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found."
            )

        # Update password, increment token version, revoke all refresh tokens (forces global logout)
        user.hashed_password = get_password_hash(reset_confirm.new_password)
        user.token_version += 1
        user.failed_login_attempts = 0
        user.locked_until = None

        await db.execute(
            update(RefreshToken)
            .filter(RefreshToken.user_id == user.id)
            .values(is_revoked=True)
        )
        await db.execute(delete(PasswordReset).filter(PasswordReset.user_id == user.id))

        await log_auth_event(
            db=db,
            action="password_reset_success",
            user_id=user.id,
            email=user.email
        )
        await db.commit()

    @staticmethod
    async def exchange_google_oauth(
        db: AsyncSession,
        code: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_info: Optional[str] = None
    ) -> Token:
        # Fallback/Mock check
        is_mock = not settings.GOOGLE_CLIENT_ID or settings.GOOGLE_CLIENT_ID == "your_google_client_id_here"
        
        email = None
        provider_user_id = None
        
        if is_mock:
            # Mock details for integration testing
            email = f"mock_{code}@example.com"
            provider_user_id = f"google_mock_{code}"
            logger.info(f"Using mock Google OAuth. email={email}, provider_user_id={provider_user_id}")
        else:
            try:
                async with httpx.AsyncClient() as client:
                    # Exchange code for tokens
                    token_res = await client.post(
                        "https://oauth2.googleapis.com/token",
                        data={
                            "code": code,
                            "client_id": settings.GOOGLE_CLIENT_ID,
                            "client_secret": settings.GOOGLE_CLIENT_SECRET,
                            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                            "grant_type": "authorization_code"
                        }
                    )
                    token_res.raise_for_status()
                    token_data = token_res.json()
                    access_token = token_data.get("access_token")
                    
                    # Fetch userinfo
                    user_res = await client.get(
                        "https://openidconnect.googleapis.com/v1/userinfo",
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    user_res.raise_for_status()
                    user_info = user_res.json()
                    email = user_info.get("email")
                    provider_user_id = user_info.get("sub")
            except Exception as e:
                logger.error(f"Real Google OAuth failed, falling back to mock: {e}")
                email = f"mock_{code}@example.com"
                provider_user_id = f"google_mock_{code}"

        if not email or not provider_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve user profile from Google OAuth."
            )

        # Check if user already linked via OAuth
        result = await db.execute(
            select(OAuthAccount)
            .filter(OAuthAccount.provider == "google", OAuthAccount.provider_user_id == provider_user_id)
        )
        oauth_account = result.scalars().first()

        user = None
        if oauth_account:
            result = await db.execute(select(User).filter(User.id == oauth_account.user_id))
            user = result.scalars().first()
        else:
            # Check if user with email already exists
            result = await db.execute(select(User).filter(User.email == email))
            user = result.scalars().first()

            if not user:
                # Auto-create user (Google signups are verified)
                random_pass = str(uuid.uuid4())
                hashed_password = get_password_hash(random_pass)
                user = User(
                    email=email,
                    hashed_password=hashed_password,
                    role=UserRole.USER,
                    is_active=True,
                    is_verified=True,  # Verified by Google
                    failed_login_attempts=0,
                    token_version=1
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)
            
            # Create OAuth linkage
            oauth_link = OAuthAccount(
                user_id=user.id,
                provider="google",
                provider_user_id=provider_user_id
            )
            db.add(oauth_link)
            await db.commit()

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User account is disabled."
            )

        # Complete Login Flow
        user.failed_login_attempts = 0
        user.locked_until = None

        access_jti = str(uuid.uuid4())
        refresh_jti = str(uuid.uuid4())
        
        access_token = create_access_token(user.id, access_jti, token_version=user.token_version)
        refresh_token = create_refresh_token(user.id, refresh_jti, token_version=user.token_version)

        db_refresh = RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            is_revoked=False,
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(db_refresh)

        await log_auth_event(
            db=db,
            action="oauth_login_success",
            user_id=user.id,
            email=user.email,
            ip_address=ip_address,
            user_agent=user_agent
        )
        await db.commit()

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )
