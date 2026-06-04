"""Async email sending via aiosmtplib (Gmail SMTP with STARTTLS).

Usage:
    await send_otp_email(to="user@example.com", code="123456", purpose="password_reset")
"""

import logging
import secrets
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


def _generate_otp() -> str:
    """Return a cryptographically-safe 6-digit OTP."""
    return str(secrets.randbelow(900_000) + 100_000)


def _build_reset_email(to: str, code: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[PFE2] Password Reset Code: {code}"
    msg["From"] = settings.smtp_from_address
    msg["To"] = to

    text_body = (
        f"Your PFE2 password reset code is: {code}\n\n"
        f"This code expires in {settings.otp_expire_minutes} minutes.\n"
        "If you did not request a password reset, you can ignore this email.\n\n"
        "— PFE2 Intelligence Platform"
    )

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <style>
    body {{
      margin: 0; padding: 0;
      background: #080a0c;
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      color: #e8eaed;
    }}
    .wrapper {{
      max-width: 480px;
      margin: 40px auto;
      background: #0e1114;
      border: 1px solid #2d3339;
      padding: 40px;
    }}
    .logo-mark {{
      display: inline-block;
      width: 40px; height: 40px;
      background: #e8a020;
      margin-bottom: 20px;
    }}
    .headline {{
      font-family: 'Courier New', monospace;
      font-size: 11px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: #5f6368;
      margin-bottom: 8px;
    }}
    .title {{
      font-size: 22px;
      font-weight: 700;
      color: #e8eaed;
      letter-spacing: -0.02em;
      margin-bottom: 28px;
    }}
    .body-text {{
      font-size: 14px;
      color: #9aa0a6;
      line-height: 1.6;
      margin-bottom: 32px;
    }}
    .code-box {{
      background: #141719;
      border: 1px solid #2d3339;
      padding: 20px;
      text-align: center;
      margin: 28px 0;
    }}
    .code-label {{
      font-family: 'Courier New', monospace;
      font-size: 10px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: #5f6368;
      margin-bottom: 12px;
    }}
    .code-value {{
      font-family: 'Courier New', monospace;
      font-size: 38px;
      font-weight: 600;
      color: #e8a020;
      letter-spacing: 0.18em;
    }}
    .expiry {{
      font-family: 'Courier New', monospace;
      font-size: 11px;
      color: #5f6368;
      text-align: center;
      margin-top: 10px;
      letter-spacing: 0.06em;
    }}
    .footer {{
      border-top: 1px solid #1f2428;
      margin-top: 36px;
      padding-top: 20px;
      font-family: 'Courier New', monospace;
      font-size: 10px;
      color: #5f6368;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="logo-mark"></div>
    <div class="headline">Competitive Intelligence Platform</div>
    <div class="title">Password Reset</div>
    <div class="body-text">
      We received a request to reset the password for your account
      associated with <strong style="color:#e8eaed">{to}</strong>.<br/><br/>
      Enter the code below in the reset form. If you didn't request this,
      you can safely ignore this email — your password will not change.
    </div>
    <div class="code-box">
      <div class="code-label">Your confirmation code</div>
      <div class="code-value">{code}</div>
      <div class="expiry">Expires in {settings.otp_expire_minutes} minutes</div>
    </div>
    <div class="footer">
      PFE2 · Admin Intelligence Dashboard · Automated Message
    </div>
  </div>
</body>
</html>"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    return msg


def _build_welcome_email(to: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "[PFE2] Welcome to the Intelligence Platform"
    msg["From"] = settings.smtp_from_address
    msg["To"] = to

    text_body = (
        "Welcome to PFE2 Intelligence Platform!\n\n"
        "Your account has been created successfully. "
        "You can now log in with your email and password.\n\n"
        "— PFE2 Team"
    )

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <style>
    body {{
      margin: 0; padding: 0;
      background: #080a0c;
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      color: #e8eaed;
    }}
    .wrapper {{
      max-width: 480px;
      margin: 40px auto;
      background: #0e1114;
      border: 1px solid #2d3339;
      padding: 40px;
    }}
    .logo-mark {{
      display: inline-block;
      width: 40px; height: 40px;
      background: #e8a020;
      margin-bottom: 20px;
    }}
    .headline {{
      font-family: 'Courier New', monospace;
      font-size: 11px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: #5f6368;
      margin-bottom: 8px;
    }}
    .title {{
      font-size: 22px;
      font-weight: 700;
      color: #e8eaed;
      letter-spacing: -0.02em;
      margin-bottom: 28px;
    }}
    .body-text {{
      font-size: 14px;
      color: #9aa0a6;
      line-height: 1.6;
    }}
    .highlight {{
      color: #e8a020;
      font-weight: 600;
    }}
    .footer {{
      border-top: 1px solid #1f2428;
      margin-top: 36px;
      padding-top: 20px;
      font-family: 'Courier New', monospace;
      font-size: 10px;
      color: #5f6368;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="logo-mark"></div>
    <div class="headline">Competitive Intelligence Platform</div>
    <div class="title">Welcome aboard<span style="color:#e8a020">▋</span></div>
    <div class="body-text">
      Your account for <span class="highlight">{to}</span> has been created
      successfully.<br/><br/>
      You now have access to the PFE2 Intelligence Dashboard. Log in at
      <span class="highlight">http://localhost:3000/login</span> using your
      email and password.
    </div>
    <div class="footer">
      PFE2 · Admin Intelligence Dashboard · Automated Message
    </div>
  </div>
</body>
</html>"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    return msg


async def send_otp_email(to: str, code: str) -> None:
    """Send a password-reset OTP email via Gmail SMTP (STARTTLS on port 587)."""
    if not settings.smtp_enabled:
        logger.info("[email] SMTP disabled — OTP for %s: %s", to, code)
        return

    msg = _build_reset_email(to, code)
    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=True,
        )
        logger.info("[email] OTP sent to %s", to)
    except Exception as exc:
        logger.error("[email] Failed to send OTP to %s: %s", to, exc)
        raise


async def send_welcome_email(to: str) -> None:
    """Send a welcome email after successful registration."""
    if not settings.smtp_enabled:
        logger.info("[email] SMTP disabled — skipping welcome email for %s", to)
        return

    msg = _build_welcome_email(to)
    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=True,
        )
        logger.info("[email] Welcome email sent to %s", to)
    except Exception as exc:
        # Non-fatal — registration succeeded; just log
        logger.warning("[email] Welcome email failed for %s: %s", to, exc)


def generate_otp() -> str:
    """Public alias used by the auth router."""
    return _generate_otp()
