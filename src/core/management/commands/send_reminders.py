from datetime import timedelta

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings

from core.models import CalendarEvent, Homework


class Command(BaseCommand):
    help = "Send email reminders about lessons and unfinished homework"

    def handle(self, *args, **options):
        now = timezone.now()

        # Нагадування про урок за 1 годину
        lesson_from = now
        lesson_to = now + timedelta(hours=1)

        lessons = CalendarEvent.objects.filter(
            event_type="lesson",
            start_time__gte=lesson_from,
            start_time__lte=lesson_to,
            is_cancelled=False,
            reminder_email_sent=False,
            student__isnull=False,
        )

        for lesson in lessons:
            if lesson.student.email:
                send_mail(
                    subject="Нагадування про урок",
                    message=(
                        f"Сьогодні у вас урок: {lesson.title}\n\n"
                        f"Час: {lesson.start_time.strftime('%d.%m.%Y %H:%M')}\n"
                        f"Вчитель: {lesson.teacher.first_name} {lesson.teacher.last_name}\n\n"
                        f"Не забудьте підготуватися до заняття."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[lesson.student.email],
                    fail_silently=False,
                )

                lesson.reminder_email_sent = True
                lesson.save()

        # Нагадування про невиконане ДЗ за 1 день до дедлайну
        homework_from = now
        homework_to = now + timedelta(days=1)

        homeworks = Homework.objects.filter(
            status="assigned",
            deadline__gte=homework_from,
            deadline__lte=homework_to,
            reminder_email_sent=False,
            student__isnull=False,
        )

        for homework in homeworks:
            if homework.student.email:
                send_mail(
                    subject="Нагадування про домашнє завдання",
                    message=(
                        f"У вас є невиконане домашнє завдання: {homework.title}\n\n"
                        f"Дедлайн: {homework.deadline.strftime('%d.%m.%Y %H:%M')}\n"
                        f"Вчитель: {homework.teacher.first_name} {homework.teacher.last_name}\n\n"
                        f"Будь ласка, здайте завдання вчасно."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[homework.student.email],
                    fail_silently=False,
                )

                homework.reminder_email_sent = True
                homework.save()

        self.stdout.write(self.style.SUCCESS("Нагадування на пошту відправлено."))