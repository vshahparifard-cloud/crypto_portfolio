"""Transactional email: enqueue into the outbox, send from the worker (D12).

No route ever waits on SMTP. Templates are inline on purpose — two short mails
do not justify a template directory, and keeping them here means the copy sits
next to the code that decides when to send it.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

import aiosmtplib
from jinja2 import Template
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import EmailOutbox
from app.domain.enums import EmailPurpose

log = logging.getLogger(__name__)

RETRY_SCHEDULE = (timedelta(seconds=30), timedelta(minutes=5), timedelta(minutes=30))

_LAYOUT = Template(
    """
<div dir="rtl" style="font-family:Tahoma,Arial,sans-serif;background:#f1f3f5;padding:28px">
  <div style="max-width:520px;margin:0 auto;background:#fff;border:1px solid #dce2e9;
              border-radius:12px;padding:26px;color:#10151c;line-height:1.9">
    <div style="font-weight:700;font-size:16px;margin-bottom:14px">کوین‌پالس</div>
    <div style="font-size:14px">{{ body }}</div>
    <a href="{{ url }}" style="display:inline-block;margin-top:18px;background:#2b50e0;color:#fff;
       text-decoration:none;border-radius:8px;padding:10px 18px;font-size:14px">{{ cta }}</a>
    <div style="margin-top:18px;font-size:12px;color:#7a8797">
      این لینک {{ hours }} ساعت اعتبار دارد و یک‌بار مصرف است. اگر شما این درخواست را نداده‌اید،
      این ایمیل را نادیده بگیرید.
    </div>
  </div>
</div>
"""
)

_COPY = {
    EmailPurpose.verify: {
        "subject": "تایید حساب کوین‌پالس",
        "body": "برای فعال شدن حسابتان روی دکمه زیر بزنید.",
        "cta": "تایید ایمیل",
        "path": "/verify",
        "hours": 24,
    },
    EmailPurpose.reset: {
        "subject": "بازیابی رمز کوین‌پالس",
        "body": "برای تعیین رمز جدید روی دکمه زیر بزنید.",
        "cta": "تعیین رمز جدید",
        "path": "/reset-password",
        "hours": 2,
    },
}


def build_link(purpose: EmailPurpose, token: str) -> str:
    copy = _COPY[purpose]
    return f"{settings.public_base_url.rstrip('/')}{copy['path']}?token={token}"


async def enqueue(
    session: AsyncSession, *, user_id, to_email: str, purpose: EmailPurpose, token: str
) -> EmailOutbox:
    copy = _COPY[purpose]
    row = EmailOutbox(
        user_id=user_id,
        to_email=to_email,
        kind=purpose,
        subject=str(copy["subject"]),
        body_html=_LAYOUT.render(
            body=copy["body"], url=build_link(purpose, token), cta=copy["cta"], hours=copy["hours"]
        ),
        next_retry_at=datetime.now(UTC),
    )
    session.add(row)
    return row


async def deliver(row: EmailOutbox) -> None:
    """Raises on failure; the worker owns the retry bookkeeping."""
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = row.to_email
    message["Subject"] = row.subject
    message.set_content("برای دیدن این ایمیل به نمایش HTML نیاز دارید.")
    message.add_alternative(row.body_html, subtype="html")

    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password or None,
        start_tls=settings.smtp_starttls,
    )
    log.info("email sent kind=%s to=%s", row.kind.value, row.to_email)
