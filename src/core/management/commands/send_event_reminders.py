from datetime import timedelta

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone

from core.models import CalendarEvent, EventReminder


class Command(BaseCommand):
    help = "Надсилає email-нагадування про події"

    def handle(self, *args, **kwargs):
        now = timezone.now()

        events = CalendarEvent.objects.filter(is_cancelled=False)

        for event in events:
            recipients = []

            if event.teacher and event.teacher.email:
                recipients.append(event.teacher.email)

            if event.student and event.student.email:
                recipients.append(event.student.email)

            if not recipients:
                continue

            # За день до події
            day_before_time = event.start_time - timedelta(days=1)
            if day_before_time <= now <= day_before_time + timedelta(minutes=10):
                reminder, created = EventReminder.objects.get_or_create(
                    event=event,
                    reminder_type='day_before'
                )

                if not reminder.email_sent:
                    send_mail(
                        subject=f"Нагадування: {event.title}",
                        message=(
                            f"Нагадуємо, що подія '{event.title}' "
                            f"відбудеться {event.start_time.strftime('%d.%m.%Y о %H:%M')}."
                        ),
                        from_email=None,
                        recipient_list=recipients,
                        fail_silently=False,
                    )
                    reminder.email_sent = True
                    reminder.save()

            # За годину до події
            hour_before_time = event.start_time - timedelta(hours=1)
            if hour_before_time <= now <= hour_before_time + timedelta(minutes=10):
                reminder, created = EventReminder.objects.get_or_create(
                    event=event,
                    reminder_type='hour_before'
                )

                if not reminder.email_sent:
                    send_mail(
                        subject=f"Нагадування: скоро початок заняття",
                        message=(
                            f"Подія '{event.title}' почнеться "
                            f"{event.start_time.strftime('%d.%m.%Y о %H:%M')}."
                        ),
                        from_email=None,
                        recipient_list=recipients,
                        fail_silently=False,
                    )
                    reminder.email_sent = True
                    reminder.save()