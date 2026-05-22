import asyncio
import sys
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.future import select
from sqlalchemy import delete
from loguru import logger

from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.models.user import User, UserRole
from app.models.auth import RefreshToken, EmailVerification, PasswordReset, AuthAuditLog
from app.core.security import verify_password, get_password_hash, decode_token
from app.core.redis import redis_service
from app.services.auth.auth_service import AuthService
from app.schemas.v1.user import UserCreate, LoginRequest, PasswordResetConfirm

# Configure logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:5}</level> | {message}")

async def cleanup_user(db, email: str):
    # Retrieve user
    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalars().first()
    if user:
        # Delete related tables first (cascade deletes are configured, but to be sure)
        await db.execute(delete(RefreshToken).filter(RefreshToken.user_id == user.id))
        await db.execute(delete(EmailVerification).filter(EmailVerification.user_id == user.id))
        await db.execute(delete(PasswordReset).filter(PasswordReset.user_id == user.id))
        await db.execute(delete(AuthAuditLog).filter(AuthAuditLog.user_id == user.id))
        await db.execute(delete(User).filter(User.id == user.id))
        await db.commit()

async def test_auth_pipeline():
    logger.info("Initializing Integration Test Suite for Layer 2 Authentication...")
    
    # Connect to Redis
    await redis_service.connect()

    async with AsyncSessionLocal() as db:
        test_email = "tester_auth@example.com"
        await cleanup_user(db, test_email)

        # ----------------------------------------------------
        # TEST 1: Bcrypt Hashing Verification
        # ----------------------------------------------------
        logger.info("=== TEST 1: Password Hashing ===")
        raw_password = "SecurePassword123!"
        hashed = get_password_hash(raw_password)
        
        assert hashed.startswith("$2b$") or "$2" in hashed, f"Expected standard bcrypt hash format, got: {hashed}"
        assert verify_password(raw_password, hashed) is True, "Password verification failed"
        assert verify_password("wrong_pass", hashed) is False, "Password verification passed wrong credentials"
        logger.success("Bcrypt Hashing Verification Passed!")

        # ----------------------------------------------------
        # TEST 2: Registration & Verification Flow
        # ----------------------------------------------------
        logger.info("=== TEST 2: User Registration & Email Verification ===")
        user_in = UserCreate(
            email=test_email,
            password=raw_password,
            role=UserRole.USER
        )
        
        user = await AuthService.register_user(db, user_in)
        assert user.email == test_email
        assert user.is_verified is False, "New users should be unverified"
        assert user.role == UserRole.USER
        logger.success("User successfully registered as unverified.")

        # Attempt login (should fail due to verification enforcement)
        login_data = LoginRequest(email=test_email, password=raw_password)
        try:
            await AuthService.login_user(db, login_data)
            assert False, "Should have failed login: Email unverified"
        except Exception as e:
            assert hasattr(e, "detail") and "verification is required" in e.detail, f"Expected email verification error, got: {e}"
            logger.success("Login blocked for unverified email.")

        # Verify email using generated token
        result = await db.execute(select(EmailVerification).filter(EmailVerification.user_id == user.id))
        ver_record = result.scalars().first()
        assert ver_record is not None, "EmailVerification record not found in database"
        
        await AuthService.verify_email_token(db, ver_record.token)
        
        # Verify user state
        await db.refresh(user)
        assert user.is_verified is True, "User should be marked verified now"
        logger.success("Email verification token verified successfully.")

        # Login again (should succeed)
        tokens = await AuthService.login_user(db, login_data)
        assert tokens.access_token is not None
        assert tokens.refresh_token is not None
        logger.success("Authenticated successfully after email verification.")

        # ----------------------------------------------------
        # TEST 3: Account Lockouts
        # ----------------------------------------------------
        logger.info("=== TEST 3: Account Lockout Policy ===")
        lockout_email = "lockout_tester@example.com"
        await cleanup_user(db, lockout_email)
        
        # Register and verify lockout tester
        user_lockout = await AuthService.register_user(db, UserCreate(email=lockout_email, password=raw_password))
        user_lockout.is_verified = True
        await db.commit()

        # Fail logins consecutively
        bad_login = LoginRequest(email=lockout_email, password="WrongPassword")
        for i in range(1, 5):
            try:
                await AuthService.login_user(db, bad_login)
                assert False, "Login should fail with wrong credentials"
            except Exception as e:
                # Expect incorrect email or password
                pass
        
        # Check attempts incremented
        await db.refresh(user_lockout)
        assert user_lockout.failed_login_attempts == 4
        assert user_lockout.locked_until is None

        # 5th attempt (should trigger lockout)
        try:
            await AuthService.login_user(db, bad_login)
            assert False, "5th attempt should fail and lock account"
        except Exception:
            pass

        await db.refresh(user_lockout)
        assert user_lockout.failed_login_attempts == 5
        assert user_lockout.locked_until is not None
        logger.success("Account successfully locked after 5 failed login attempts.")

        # Try correct password while locked
        try:
            await AuthService.login_user(db, LoginRequest(email=lockout_email, password=raw_password))
            assert False, "Locked account should block correct passwords"
        except Exception as e:
            assert "locked" in e.detail.lower()
            logger.success("Locked account blocks correct password attempts.")

        # Simulate lockout expiration by resetting lockout time in DB
        user_lockout.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()

        # Login again (should succeed)
        tokens_lockout = await AuthService.login_user(db, LoginRequest(email=lockout_email, password=raw_password))
        assert tokens_lockout.access_token is not None
        
        await db.refresh(user_lockout)
        assert user_lockout.failed_login_attempts == 0
        assert user_lockout.locked_until is None
        logger.success("Account unlocked and failed attempts reset after lockout duration expired.")
        
        await cleanup_user(db, lockout_email)

        # ----------------------------------------------------
        # TEST 4: JWT lifecycle & Refresh Token Rotation
        # ----------------------------------------------------
        logger.info("=== TEST 4: Refresh Token Rotation & Session Tracking ===")
        # Use initial test user's tokens
        old_refresh = tokens.refresh_token
        
        # Rotate refresh token
        rotated_tokens = await AuthService.refresh_jwt_tokens(db, old_refresh)
        assert rotated_tokens.access_token is not None
        assert rotated_tokens.refresh_token is not None
        assert rotated_tokens.refresh_token != old_refresh
        logger.success("Refresh token rotated successfully.")

        # Verify old refresh token is marked revoked
        result = await db.execute(select(RefreshToken).filter(RefreshToken.token == old_refresh))
        old_record = result.scalars().first()
        assert old_record.is_revoked is True
        logger.success("Old refresh token marked revoked in database.")

        # Replay Attack Protection: Attempt refresh using revoked token
        try:
            await AuthService.refresh_jwt_tokens(db, old_refresh)
            assert False, "Replay attack should be blocked!"
        except Exception as e:
            assert "compromised" in e.detail.lower() or "session" in e.detail.lower()
            logger.success("Replay attack blocked!")

        # Verify all sessions for this user were revoked
        result = await db.execute(select(RefreshToken).filter(RefreshToken.user_id == user.id))
        all_tokens = result.scalars().all()
        assert all(t.is_revoked for t in all_tokens), "Expected all sessions to be revoked on replay attack"
        
        await db.refresh(user)
        assert user.token_version == 2, "Expected token version incremented to invalidate access tokens"
        logger.success("Replay protection: All sessions revoked and token version incremented.")

        # Log in again to get fresh tokens for logout testing
        tokens = await AuthService.login_user(db, login_data)

        # ----------------------------------------------------
        # TEST 5: Logout & Blacklisting
        # ----------------------------------------------------
        logger.info("=== TEST 5: Logout & Access Token Blacklisting ===")
        access_payload = decode_token(tokens.access_token)
        jti = access_payload.get("jti")
        
        await AuthService.logout_user(db, tokens.refresh_token, tokens.access_token)
        
        # Verify blacklisted in Redis
        is_blacklisted = await redis_service.is_token_blacklisted(jti)
        assert is_blacklisted is True, "Access token JTI should be blacklisted in Redis"
        
        # Verify refresh token revoked in DB
        result = await db.execute(select(RefreshToken).filter(RefreshToken.token == tokens.refresh_token))
        logged_out_refresh = result.scalars().first()
        assert logged_out_refresh.is_revoked is True
        logger.success("Logout invalidation completed successfully.")

        # ----------------------------------------------------
        # TEST 6: Google OAuth Mocking
        # ----------------------------------------------------
        logger.info("=== TEST 6: Google OAuth Signup & Account Linkage ===")
        oauth_code = f"test_oauth_code_{uuid.uuid4().hex[:6]}"
        oauth_email = f"mock_{oauth_code}@example.com"
        
        # Exchange mock code
        oauth_tokens = await AuthService.exchange_google_oauth(db, oauth_code)
        assert oauth_tokens.access_token is not None
        assert oauth_tokens.refresh_token is not None
        
        # Verify user created and marked verified
        result = await db.execute(select(User).filter(User.email == oauth_email))
        oauth_user = result.scalars().first()
        assert oauth_user is not None
        assert oauth_user.is_verified is True, "Google signup should be pre-verified"
        logger.success("Google OAuth signup completed with pre-verified status.")

        # Re-authenticate using Google OAuth (should log in and link)
        reauth_tokens = await AuthService.exchange_google_oauth(db, oauth_code)
        assert reauth_tokens.access_token is not None
        logger.success("Google OAuth login for existing user completed successfully.")
        
        await cleanup_user(db, oauth_email)
        await cleanup_user(db, test_email)

        # Disconnect Redis
        await redis_service.disconnect()

        logger.success("=======================================")
        logger.success("ALL INTEGRATION TESTS PASSED SUCCESSFULLY!")
        logger.success("=======================================")

if __name__ == "__main__":
    asyncio.run(test_auth_pipeline())
