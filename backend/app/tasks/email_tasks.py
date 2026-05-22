import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from celery import shared_task
from loguru import logger
from app.core.config import settings

def send_email(to_email: str, subject: str, html_content: str) -> None:
    """
    SMTP helper that sends emails or falls back to logger/console output if not configured.
    """
    if not settings.SMTP_HOST or not settings.SMTP_USER or settings.SMTP_HOST == "your_smtp_host_here":
        logger.info(f"=== [EMAIL SERVICE MOCK] ===")
        logger.info(f"To: {to_email}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Content:\n{html_content}")
        logger.info(f"=============================")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = to_email

        part = MIMEText(html_content, "html")
        msg.attach(part)

        logger.info(f"Connecting to SMTP server {settings.SMTP_HOST}:{settings.SMTP_PORT}...")
        
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        if settings.SMTP_TLS:
            server.starttls()
            
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            
        server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())
        server.quit()
        logger.info(f"Successfully sent email to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email} via SMTP: {e}. Falling back to console logging.")
        logger.info(f"=== [EMAIL SERVICE FALLBACK MOCK] ===")
        logger.info(f"To: {to_email}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Content:\n{html_content}")
        logger.info(f"=====================================")

@shared_task(name="app.tasks.email_tasks.send_verification_email_task")
def send_verification_email_task(email: str, token: str) -> None:
    """
    Celery background task to send verification emails.
    """
    # Using localhost API url for local development link click
    verification_link = f"http://localhost:8000/api/v1/auth/verify-email/confirm?token={token}"
    subject = "Verify your Email - AI Exam Learning Platform"
    
    html_content = f"""
    <html>
        <body>
            <h2>Welcome to AI Exam Learning Platform!</h2>
            <p>Thank you for registering. Please click the link below to verify your email address and activate your account:</p>
            <p><a href="{verification_link}">{verification_link}</a></p>
            <br/>
            <p>If you did not request this email, please ignore it.</p>
        </body>
    </html>
    """
    send_email(email, subject, html_content)

@shared_task(name="app.tasks.email_tasks.send_password_reset_email_task")
def send_password_reset_email_task(email: str, token: str) -> None:
    """
    Celery background task to send password reset emails.
    """
    reset_link = f"http://localhost:3000/auth/reset-password?token={token}"
    subject = "Reset your Password - AI Exam Learning Platform"
    
    html_content = f"""
    <html>
        <body>
            <h2>Reset your Password</h2>
            <p>We received a request to reset your password. Please click the link below to configure new credentials:</p>
            <p><a href="{reset_link}">{reset_link}</a></p>
            <br/>
            <p>Note: This link will expire in 2 hours.</p>
            <p>If you did not request this change, please ignore this email.</p>
        </body>
    </html>
    """
    send_email(email, subject, html_content)
