from django.db import models
import random
import string
from django.conf import settings
from django.db import models


def generate_access_code(length=6):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def generate_unique_access_code():
    while True:
        code = generate_access_code()
        if not TeacherProfile.objects.filter(access_code=code).exists():
            return code


class TeacherProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_profile",
    )
    access_code = models.CharField(max_length=20, unique=True)
    subject = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"Teacher: {self.user.email}"

class StudentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )

    def __str__(self):
        return f"Student: {self.user.email}"


class StudentTeacherLink(models.Model):
    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="teacher_links",
    )
    teacher = models.ForeignKey(
        TeacherProfile,
        on_delete=models.CASCADE,
        related_name="student_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "teacher")

    def __str__(self):
        return f"{self.student.user.email} -> {self.teacher.user.email}"


class CalendarEvent(models.Model):
    EVENT_TYPES = [
        ('lesson', 'Заняття'),
        ('homework', 'Домашнє завдання'),
        ('deadline', 'Термін виконання'),
    ]

    title = models.CharField(max_length=255)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES, default='lesson')
    description = models.TextField(blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    meeting_link = models.URLField(blank=True)
    is_cancelled = models.BooleanField(default=False)

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='teacher_events',
        null=True,
        blank=True
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student_events',
        null=True,
        blank=True
    )

    def __str__(self):
        return self.title

class EventReminder(models.Model):
    REMINDER_TYPES = [
        ('day_before', 'За день'),
        ('hour_before', 'За годину'),
        ('deadline_day', 'Термін виконання'),
    ]

    event = models.ForeignKey(CalendarEvent, on_delete=models.CASCADE, related_name='reminders')
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPES)
    email_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event.title} - {self.reminder_type}"