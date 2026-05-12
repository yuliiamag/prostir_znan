from datetime import timedelta
from .models import GoogleCalendarToken
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def credentials_to_dict(credentials):
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }


def get_google_calendar_service(request):
    credentials_data = request.session.get("google_credentials")

    if not credentials_data:
        return None

    credentials = Credentials(**credentials_data)
    return build("calendar", "v3", credentials=credentials)


def sync_lesson_to_google_calendar(request, lesson):
    service = get_google_calendar_service(request)

    if service is None:
        return None

    end_time = lesson.end_time or lesson.start_time + timedelta(minutes=60)

    event_body = {
        "summary": lesson.title,
        "description": lesson.description or "",
        "start": {
            "dateTime": lesson.start_time.isoformat(),
            "timeZone": "Europe/Kyiv",
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "Europe/Kyiv",
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 30},
                {"method": "email", "minutes": 60},
            ],
        },
    }

    if lesson.meeting_link:
        event_body["location"] = lesson.meeting_link

    created_event = service.events().insert(
        calendarId="primary",
        body=event_body,
    ).execute()

    lesson.google_event_id = created_event.get("id")
    lesson.is_synced_with_google = True
    lesson.save(update_fields=["google_event_id", "is_synced_with_google"])

    return created_event

def sync_lesson_to_google_calendar_for_user(user, lesson):
    google_token = GoogleCalendarToken.objects.filter(user=user).first()

    if not google_token:
        print(f"Google Calendar не підключено для користувача {user.id}")
        return None

    credentials = Credentials(**google_token.get_credentials_dict())
    service = build("calendar", "v3", credentials=credentials)

    end_time = lesson.end_time or lesson.start_time + timedelta(minutes=60)

    event_body = {
        "summary": lesson.title,
        "description": lesson.description or "",
        "start": {
            "dateTime": lesson.start_time.isoformat(),
            "timeZone": "Europe/Kyiv",
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "Europe/Kyiv",
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 30},
                {"method": "email", "minutes": 60},
            ],
        },
    }

    if lesson.meeting_link:
        event_body["location"] = lesson.meeting_link

    created_event = service.events().insert(
        calendarId="primary",
        body=event_body,
    ).execute()

    return created_event


def sync_lesson_to_google_calendar_for_participants(lesson):
    users = []

    if lesson.teacher:
        users.append(lesson.teacher)

    if lesson.student:
        users.append(lesson.student)

    for user in users:
        try:
            sync_lesson_to_google_calendar_for_user(user, lesson)
        except Exception as e:
            print(f"GOOGLE SYNC ERROR FOR USER {user.id}:", e)