from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter
from pydantic import BaseModel, Field

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
EXPORTS_DIR = DATA_DIR / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/api/v1/mail-calendar", tags=["mail-calendar"])


class EmailDraftRequest(BaseModel):
    recipient_email: str = Field(default="kunde@beispiel.de", max_length=150)
    subject: str = Field(min_length=2, max_length=200)
    body_text: str = Field(min_length=5, max_length=5000)
    sender_name: str = Field(default="Studio M 360", max_length=100)


class EmailDraftResponse(BaseModel):
    success: bool
    subject: str
    recipient_email: str
    mailto_url: str
    eml_file_path: str
    filename: str
    created_at: str


class CalendarDraftRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    location: str = Field(default="LumOS Video-Meeting / Vor-Ort", max_length=200)
    description: str = Field(default="Besprechung und Abstimmung zum Angebot.", max_length=2000)
    start_time_iso: str = Field(default="2026-08-20T10:00:00Z")
    duration_minutes: int = Field(default=45, ge=15, le=480)
    attendee_email: str = Field(default="kunde@beispiel.de", max_length=150)


class CalendarDraftResponse(BaseModel):
    success: bool
    title: str
    ics_file_path: str
    filename: str
    start_time: str
    created_at: str


def create_eml_file(recipient: str, subject: str, body: str, sender: str, output_path: Path) -> None:
    eml_content = f"""From: {sender} <noreply@lumos.local>
To: {recipient}
Subject: {subject}
Date: {datetime.now(UTC).strftime('%a, %d %b %Y %H:%M:%S +0000')}
Content-Type: text/plain; charset=UTF-8

{body}
"""
    output_path.write_text(eml_content, encoding="utf-8")


def create_ics_file(title: str, location: str, description: str, start_iso: str, duration_min: int, attendee: str, output_path: Path) -> None:
    try:
        dt_start = datetime.fromisoformat(start_iso)
    except ValueError:
        dt_start = datetime.now(UTC)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    str_start = dt_start.strftime("%Y%m%dT%H%M%SZ")

    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Studio M 360//LumOS Lokal Office//DE
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
UID:lumos-evt-{int(datetime.now(UTC).timestamp())}@lumos.local
DTSTAMP:{stamp}
DTSTART:{str_start}
SUMMARY:{title}
LOCATION:{location}
DESCRIPTION:{description.replace('\n', '\\n')}
ATTENDEE;ROLE=REQ-PARTICIPANT:mailto:{attendee}
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR
"""
    output_path.write_text(ics_content, encoding="utf-8")


@router.post("/email/draft", response_model=EmailDraftResponse, name="create_email_draft")
async def create_email_draft(request: EmailDraftRequest) -> EmailDraftResponse:
    filename = f"email_draft_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.eml"
    target_path = EXPORTS_DIR / filename

    create_eml_file(
        recipient=request.recipient_email,
        subject=request.subject,
        body=request.body_text,
        sender=request.sender_name,
        output_path=target_path,
    )

    mailto_url = f"mailto:{quote(request.recipient_email)}?subject={quote(request.subject)}&body={quote(request.body_text)}"

    return EmailDraftResponse(
        success=True,
        subject=request.subject,
        recipient_email=request.recipient_email,
        mailto_url=mailto_url,
        eml_file_path=str(target_path),
        filename=filename,
        created_at=datetime.now(UTC).isoformat(),
    )


@router.post("/calendar/draft", response_model=CalendarDraftResponse, name="create_calendar_draft")
async def create_calendar_draft(request: CalendarDraftRequest) -> CalendarDraftResponse:
    filename = f"meeting_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.ics"
    target_path = EXPORTS_DIR / filename

    create_ics_file(
        title=request.title,
        location=request.location,
        description=request.description,
        start_iso=request.start_time_iso,
        duration_min=request.duration_minutes,
        attendee=request.attendee_email,
        output_path=target_path,
    )

    return CalendarDraftResponse(
        success=True,
        title=request.title,
        ics_file_path=str(target_path),
        filename=filename,
        start_time=request.start_time_iso,
        created_at=datetime.now(UTC).isoformat(),
    )
