"""
Calendar Sync — proxy per obtenir cites de calendaris externs (iCal / .ics)
==========================================================================
Suporta qualsevol URL que retorni un fitxer .ics vàlid:
- Google Calendar (secret iCal URL)
- Doctoralia (export iCal per professional)
- Calendly, Timify, Doctolib, iCloud, Outlook, etc.

L'Electron client NO pot fer fetch cross-origin ni carregar iCal fàcilment,
per això aquest endpoint fa de proxy: baixa el .ics, el parseja i retorna
JSON amb només les cites d'un rang de dates concret.

Endpoints:
- POST /api/calendar/fetch   Body: {urls:[str], date_from:iso, date_to:iso}
                             Retorna les cites de tots els calendaris fusionades.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone, date, timedelta
import httpx
from icalendar import Calendar

router = APIRouter()

MAX_URLS = 5
MAX_EVENTS_PER_CAL = 500
FETCH_TIMEOUT_SEC = 12


class CalendarFetchRequest(BaseModel):
    urls: List[str] = Field(..., min_length=1, max_length=MAX_URLS)
    date_from: str  # ISO date "YYYY-MM-DD"
    date_to: str    # ISO date "YYYY-MM-DD"


class CalendarEvent(BaseModel):
    source: str          # url index or label ("Google", "Doctoralia", "Calendari 1"...)
    uid: str
    date: str            # "YYYY-MM-DD"
    time: str            # "HH:MM" or "" if all-day
    end_time: str = ""   # "HH:MM"
    summary: str
    description: str = ""
    location: str = ""


class CalendarFetchResponse(BaseModel):
    ok: bool
    events: List[CalendarEvent]
    sources_ok: List[str]
    sources_failed: List[dict]  # {url, error}
    fetched_at: str


def _fmt_time(dt) -> str:
    """Format datetime as HH:MM. Returns '' if it's a date (all-day event)."""
    if isinstance(dt, datetime):
        return dt.strftime("%H:%M")
    return ""


def _fmt_date(dt) -> str:
    """Format as YYYY-MM-DD from datetime or date."""
    if isinstance(dt, datetime):
        return dt.date().isoformat()
    if isinstance(dt, date):
        return dt.isoformat()
    return ""


def _label_from_url(url: str) -> str:
    u = url.lower()
    if "google.com" in u or "calendar.google" in u:
        return "Google Calendar"
    if "doctoralia" in u:
        return "Doctoralia"
    if "calendly" in u:
        return "Calendly"
    if "doctolib" in u:
        return "Doctolib"
    if "icloud" in u:
        return "iCloud"
    if "outlook" in u or "office365" in u:
        return "Outlook"
    if "timify" in u:
        return "Timify"
    return "Calendari extern"


async def _fetch_ics(url: str) -> bytes:
    """Fetch raw .ics content with browser-like User-Agent."""
    # Google Calendar iCal URLs use webcal:// scheme sometimes → convert
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    async with httpx.AsyncClient(
        timeout=FETCH_TIMEOUT_SEC,
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MediCarPlus/2.1",
            "Accept": "text/calendar, */*",
        },
    ) as client:
        r = await client.get(url)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"HTTP {r.status_code}")
        return r.content


def _parse_ics(content: bytes, source_label: str, date_from: date, date_to: date) -> List[CalendarEvent]:
    """Parse .ics content and return events within [date_from, date_to] range."""
    events: List[CalendarEvent] = []
    try:
        cal = Calendar.from_ical(content)
    except Exception as e:
        raise ValueError(f"invalid iCal: {e}")

    count = 0
    for comp in cal.walk("VEVENT"):
        if count >= MAX_EVENTS_PER_CAL:
            break
        try:
            dtstart = comp.get("DTSTART").dt
            dtend = comp.get("DTEND").dt if comp.get("DTEND") else None
            ev_date = _fmt_date(dtstart)
            if not ev_date:
                continue
            # Only include events within range
            try:
                ev_date_obj = date.fromisoformat(ev_date)
            except Exception:
                continue
            if ev_date_obj < date_from or ev_date_obj > date_to:
                continue

            uid = str(comp.get("UID", "")).strip() or f"{source_label}-{ev_date}-{count}"
            summary = str(comp.get("SUMMARY", "")).strip() or "(Sense títol)"
            description = str(comp.get("DESCRIPTION", "")).strip()
            location = str(comp.get("LOCATION", "")).strip()

            events.append(CalendarEvent(
                source=source_label,
                uid=uid,
                date=ev_date,
                time=_fmt_time(dtstart),
                end_time=_fmt_time(dtend) if dtend else "",
                summary=summary[:200],
                description=description[:500],
                location=location[:200],
            ))
            count += 1
        except Exception:
            # Skip malformed events, keep parsing rest
            continue
    return events


@router.post("/calendar/fetch", response_model=CalendarFetchResponse)
async def fetch_calendars(req: CalendarFetchRequest):
    """Fetch and parse multiple external calendars, return merged events for date range."""
    try:
        date_from = date.fromisoformat(req.date_from)
        date_to = date.fromisoformat(req.date_to)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date_from/date_to (format: YYYY-MM-DD)")

    if date_to < date_from:
        raise HTTPException(status_code=400, detail="date_to must be >= date_from")
    # Limit range to 60 days
    if (date_to - date_from).days > 60:
        raise HTTPException(status_code=400, detail="Range must be ≤ 60 days")

    all_events: List[CalendarEvent] = []
    sources_ok: List[str] = []
    sources_failed: List[dict] = []

    for url in req.urls:
        url = url.strip()
        if not url:
            continue
        label = _label_from_url(url)
        try:
            content = await _fetch_ics(url)
            evs = _parse_ics(content, label, date_from, date_to)
            all_events.extend(evs)
            sources_ok.append(label)
        except HTTPException as e:
            sources_failed.append({"url": label, "error": e.detail})
        except Exception as e:
            sources_failed.append({"url": label, "error": str(e)[:200]})

    # Sort by date then time
    all_events.sort(key=lambda e: (e.date, e.time or "00:00"))

    return CalendarFetchResponse(
        ok=len(sources_failed) == 0,
        events=all_events,
        sources_ok=sources_ok,
        sources_failed=sources_failed,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
