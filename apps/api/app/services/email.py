import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


async def send_email(to: str, subject: str, html: str) -> bool:
    if not settings.resend_api_key:
        logger.warning("Resend API key not configured, skipping email to %s", to)
        return False

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                RESEND_API_URL,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.email_from,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
                timeout=10.0,
            )
            if resp.status_code >= 400:
                logger.error("Resend API error %d: %s", resp.status_code, resp.text)
                return False
            return True
    except httpx.HTTPError as e:
        logger.error("Email send failed: %s", e)
        return False


async def send_otp_email(to: str, otp: str) -> bool:
    html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
        <h2>Xác thực email của bạn</h2>
        <p>Mã OTP của bạn là:</p>
        <div style="font-size: 32px; font-weight: bold; letter-spacing: 8px;
                    background: #f4f4f5; padding: 16px 24px; border-radius: 8px;
                    text-align: center; margin: 16px 0;">
            {otp}
        </div>
        <p>Mã này có hiệu lực trong 10 phút.</p>
        <p style="color: #71717a; font-size: 14px;">
            Nếu bạn không yêu cầu mã này, vui lòng bỏ qua email.
        </p>
    </div>
    """
    return await send_email(to, "AI Co-host — Mã xác thực", html)


async def send_reset_password_email(to: str, reset_token: str) -> bool:
    reset_url = f"{settings.frontend_url}/reset-password?token={reset_token}"
    html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
        <h2>Đặt lại mật khẩu</h2>
        <p>Bạn đã yêu cầu đặt lại mật khẩu. Nhấn nút bên dưới:</p>
        <a href="{reset_url}"
           style="display: inline-block; background: #5B47E0; color: white;
                  padding: 12px 24px; border-radius: 8px; text-decoration: none;
                  font-weight: 600; margin: 16px 0;">
            Đặt lại mật khẩu
        </a>
        <p style="color: #71717a; font-size: 14px;">
            Link có hiệu lực trong 1 giờ. Nếu bạn không yêu cầu, vui lòng bỏ qua.
        </p>
    </div>
    """
    return await send_email(to, "AI Co-host — Đặt lại mật khẩu", html)


async def send_invite_email(to: str, shop_name: str, inviter_name: str) -> bool:
    invite_url = f"{settings.frontend_url}/login"
    html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
        <h2>Bạn được mời tham gia {shop_name}</h2>
        <p><strong>{inviter_name}</strong> đã mời bạn tham gia shop
           <strong>{shop_name}</strong> trên AI Co-host.</p>
        <a href="{invite_url}"
           style="display: inline-block; background: #5B47E0; color: white;
                  padding: 12px 24px; border-radius: 8px; text-decoration: none;
                  font-weight: 600; margin: 16px 0;">
            Đăng nhập để tham gia
        </a>
    </div>
    """
    return await send_email(to, f"AI Co-host — Lời mời tham gia {shop_name}", html)
