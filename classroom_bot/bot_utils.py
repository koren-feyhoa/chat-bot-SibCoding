import datetime
import os
import logging
from googleapiclient.discovery import build
from bot import get_calendar_service

def _has_overlap(start1, end1, start2, end2):
    return start1 < end2 and end1 > start2

def is_time_available(start_datetime: datetime.datetime, end_datetime: datetime.datetime) -> bool:
    service = get_calendar_service()
    calendar_id = os.getenv('GOOGLE_CALENDAR_ID')
    time_min = (start_datetime - datetime.timedelta(days=1)).isoformat()
    time_max = (end_datetime + datetime.timedelta(days=1)).isoformat()
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    logging.info(f"[is_time_available] Found {len(events)} events in Google Calendar for {time_min} - {time_max}")
    print(f"[is_time_available] Found {len(events)} events in Google Calendar for {time_min} - {time_max}")
    for event in events:
        ev_start = None
        ev_end = None
        try:
            if 'dateTime' in event['start']:
                ev_start = datetime.datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
            elif 'date' in event['start']:
                ev_start = datetime.datetime.fromisoformat(event['start']['date'] + 'T00:00:00+07:00')
            if 'dateTime' in event['end']:
                ev_end = datetime.datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
            elif 'date' in event['end']:
                ev_end = datetime.datetime.fromisoformat(event['end']['date'] + 'T00:00:00+07:00') - datetime.timedelta(seconds=1)
        except Exception as e:
            logging.warning(f"Не удалось разобрать событие календаря: {event} ({e})")
            continue
        ev_start_utc = ev_start.astimezone(datetime.timezone.utc) if ev_start else None
        ev_end_utc = ev_end.astimezone(datetime.timezone.utc) if ev_end else None
        req_start_utc = start_datetime.astimezone(datetime.timezone.utc)
        req_end_utc = end_datetime.astimezone(datetime.timezone.utc)
        logging.info(f"[is_time_available] Сравнение событий: Event: {event.get('summary', '')}, ev_start_utc: {ev_start_utc}, ev_end_utc: {ev_end_utc}, req_start_utc: {req_start_utc}, req_end_utc: {req_end_utc}")
        print(f"[is_time_available] Сравнение событий: Event: {event.get('summary', '')}, ev_start_utc: {ev_start_utc}, ev_end_utc: {ev_end_utc}, req_start_utc: {req_start_utc}, req_end_utc: {req_end_utc}")
        if ev_start_utc and ev_end_utc and _has_overlap(ev_start_utc, ev_end_utc, req_start_utc, req_end_utc):
            logging.info(f"[is_time_available] Overlap found: {ev_start_utc} - {ev_end_utc} overlaps with {req_start_utc} - {req_end_utc}")
            print(f"[is_time_available] Overlap found: {ev_start_utc} - {ev_end_utc} overlaps with {req_start_utc} - {req_end_utc}")
            return False
    return True

def format_booked_times(events):
    events_by_day = {}
    for event in events:
        try:
            start = datetime.datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
            end = datetime.datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
        except Exception:
            continue
        start = start.astimezone(datetime.timezone(datetime.timedelta(hours=7)))
        end = end.astimezone(datetime.timezone(datetime.timedelta(hours=7)))
        day_str = start.strftime('%d.%m.%Y')
        if day_str not in events_by_day:
            events_by_day[day_str] = []
        events_by_day[day_str].append((start, end))
    result = ['📅 Уже забронировали']
    for day in sorted(events_by_day.keys(), key=lambda d: datetime.datetime.strptime(d, '%d.%m.%Y')):
        result.append(f"\n📆 {day}:")
        for start, end in sorted(events_by_day[day]):
            result.append(f"⏰ {start.strftime('%H:%M')}-{end.strftime('%H:%M')}")
    print(f"[format_booked_times] Слоты по дням: {events_by_day}")
    return '\n'.join(result)
