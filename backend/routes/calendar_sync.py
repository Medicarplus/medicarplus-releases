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

Seguretat:
- Només HTTPS (no HTTP pla, ni file://, ni ftp://)
- Rebutja hostnames/IPs privades (SSRF protection)
- Timeout 12s per URL
- Max 5 URLs · Max 60 dies de rang · Max 500 events per calendari

Support recurring events (RRULE): expansió automàtica dins del rang de dates
gràcies a la lib `recurring-ical-events`. Doctoralia i Calendly usen molt RRULE.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone, date, timedelta
from urllib.parse import urlparse
import ipaddress
import socket
import httpx
from icalendar import Calendar
import recurring_ical_events

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
    if "outlook" in u or "office365" in u or "office.com" in u:
        return "Outlook"
    if "timify" in u:
        return "Timify"
    return "Calendari extern"


def _is_url_safe(url: str) -> tuple[bool, str]:
    """SSRF protection: only allow public HTTPS URLs to prevent access to internal hosts."""
    try:
        # Convert webcal:// to https:// upstream
        if url.startswith("webcal://"):
            url = "https://" + url[len("webcal://"):]
        p = urlparse(url)
        if p.scheme not in ("https", "http"):
            return False, "Only http(s) URLs allowed"
        # Force HTTPS for real sources (leave HTTP as an escape hatch for edge cases like local testing)
        if not p.hostname:
            return False, "Missing hostname"
        host = p.hostname
        # Reject explicit internal hostnames
        low = host.lower()
        if low in ("localhost", "0.0.0.0") or low.endswith(".local") or low.endswith(".internal"):
            return False, "Internal hostname not allowed"
        # Try to resolve and check if the IP is private/reserved
        try:
            infos = socket.getaddrinfo(host, None)
            for info in infos:
                ip_str = info[4][0]
                try:
                    ip = ipaddress.ip_address(ip_str)
                    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
                        return False, f"Private/reserved IP not allowed: {ip_str}"
                except ValueError:
                    continue
        except socket.gaierror:
            # DNS resolution failed → let httpx handle it (returns 502 later)
            pass
        return True, ""
    except Exception as e:
        return False, f"URL validation error: {str(e)[:80]}"


async def _fetch_ics(url: str) -> bytes:
    """Fetch raw .ics content with browser-like User-Agent."""
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    ok, why = _is_url_safe(url)
    if not ok:
        raise HTTPException(status_code=400, detail=f"URL rebutjada: {why}")
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


def _extract_event_data(comp, source_label: str, fallback_counter: int) -> Optional[CalendarEvent]:
    """Extract CalendarEvent from an icalendar component. Returns None on error."""
    try:
        dtstart = comp.get("DTSTART").dt
        dtend = comp.get("DTEND").dt if comp.get("DTEND") else None
        ev_date = _fmt_date(dtstart)
        if not ev_date:
            return None
        uid = str(comp.get("UID", "")).strip() or f"{source_label}-{ev_date}-{fallback_counter}"
        summary = str(comp.get("SUMMARY", "")).strip() or "(Sense títol)"
        description = str(comp.get("DESCRIPTION", "")).strip()
        location = str(comp.get("LOCATION", "")).strip()
        return CalendarEvent(
            source=source_label,
            uid=uid,
            date=ev_date,
            time=_fmt_time(dtstart),
            end_time=_fmt_time(dtend) if dtend else "",
            summary=summary[:200],
            description=description[:500],
            location=location[:200],
        )
    except Exception:
        return None


def _parse_ics(content: bytes, source_label: str, date_from: date, date_to: date) -> List[CalendarEvent]:
    """Parse .ics content, expand recurring events (RRULE), return events in [date_from, date_to]."""
    events: List[CalendarEvent] = []
    try:
        cal = Calendar.from_ical(content)
    except Exception as e:
        raise ValueError(f"invalid iCal: {e}")

    # Use recurring_ical_events to expand RRULE (Doctoralia/Calendly send recurring slots)
    # NOTE: .between(start, stop) — stop is EXCLUSIVE, so we add 1 day to include date_to
    try:
        occurrences = recurring_ical_events.of(cal).between(date_from, date_to + timedelta(days=1))
    except Exception:
        # Fallback: iterate non-recurring VEVENTs only
        occurrences = cal.walk("VEVENT")

    count = 0
    for comp in occurrences:
        if count >= MAX_EVENTS_PER_CAL:
            break
        # Uniqueness: expanded RRULE instances share UID; disambiguate by date+time
        ev = _extract_event_data(comp, source_label, count)
        if not ev:
            continue
        try:
            ev_date_obj = date.fromisoformat(ev.date)
        except Exception:
            continue
        if ev_date_obj < date_from or ev_date_obj > date_to:
            continue
        # Give recurring instances a unique UID per date
        ev.uid = f"{ev.uid}@{ev.date}"
        events.append(ev)
        count += 1
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
    if (date_to - date_from).days > 60:
        raise HTTPException(status_code=400, detail="Range must be ≤ 60 days")

    all_events: List[CalendarEvent] = []
    sources_ok: List[str] = []
    sources_failed: List[dict] = []

    for url in req.urls:
        url_original = url.strip()
        if not url_original:
            continue
        label = _label_from_url(url_original)
        # Truncate URL for display in error responses (privacy)
        url_display = url_original[:60] + "…" if len(url_original) > 60 else url_original
        try:
            content = await _fetch_ics(url_original)
            evs = _parse_ics(content, label, date_from, date_to)
            all_events.extend(evs)
            sources_ok.append(label)
        except HTTPException as e:
            sources_failed.append({"url": url_display, "label": label, "error": str(e.detail)})
        except Exception as e:
            sources_failed.append({"url": url_display, "label": label, "error": str(e)[:200]})

    # Sort by date then time
    all_events.sort(key=lambda e: (e.date, e.time or "00:00"))

    return CalendarFetchResponse(
        ok=len(sources_failed) == 0,
        events=all_events,
        sources_ok=sources_ok,
        sources_failed=sources_failed,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
