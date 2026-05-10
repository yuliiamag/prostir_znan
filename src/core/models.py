from django.db import models
import random
import string
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User

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
    google_event_id = models.CharField(max_length=255, blank=True, null=True)
    is_synced_with_google = models.BooleanField(default=False)
    reminder_email_sent = models.BooleanField(default=False)

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

class Homework(models.Model):
    STATUS_CHOICES = [
        ("assigned", "Призначено"),
        ("submitted", "Здано"),
        ("checked", "Перевірено"),
        ("late", "Прострочено"),
    ]

    lesson = models.ForeignKey(
        "CalendarEvent",
        on_delete=models.SET_NULL,
        related_name="homeworks",
        null=True,
        blank=True
    )

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_homeworks"
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_homeworks"
    )

    title = models.CharField(max_length=200)
    topic = models.CharField(max_length=200, blank=True)
    description = models.TextField()

    deadline = models.DateTimeField(null=True, blank=True)

    allow_text_answer = models.BooleanField(default=True)
    allow_file_answer = models.BooleanField(default=True)
    allow_late_submission = models.BooleanField(default=True)
    reminder_email_sent = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="assigned"
    )

    teacher_comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    checked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} — {self.student}"


class HomeworkMaterial(models.Model):
    homework = models.ForeignKey(
        Homework,
        on_delete=models.CASCADE,
        related_name="materials"
    )

    file = models.FileField(upload_to="homework_materials/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Матеріал до: {self.homework.title}"


class HomeworkSubmission(models.Model):
    homework = models.OneToOneField(
        Homework,
        on_delete=models.CASCADE,
        related_name="submission"
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="homework_submissions"
    )

    answer_text = models.TextField(blank=True)

    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    teacher_comment = models.TextField(blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Відповідь на: {self.homework.title}"


class HomeworkSubmissionFile(models.Model):
    submission = models.ForeignKey(
        HomeworkSubmission,
        on_delete=models.CASCADE,
        related_name="files"
    )

    file = models.FileField(upload_to="homework_answers/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Файл відповіді: {self.submission.homework.title}"


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ("lesson_created", "Створено урок"),
        ("homework_created", "Створено домашнє завдання"),
        ("homework_submitted", "Домашнє завдання здано"),
        ("homework_checked", "Домашнє завдання перевірено"),
        ("message", "Нове повідомлення"),
        ("lesson_rescheduled", "Урок перенесено"),
        ("lesson_cancelled", "Урок скасовано"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=30,
        choices=NOTIFICATION_TYPES
    )

    link = models.CharField(max_length=255, blank=True, null=True)

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class Conversation(models.Model):
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="teacher_conversations"
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="student_conversations"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("teacher", "student")


class ChatMessage(models.Model):

    MESSAGE_TYPES = [
        ("text", "Текст"),
        ("lesson_reschedule_request", "Запит на перенесення"),
        ("lesson_cancelled", "Урок скасовано"),
        ("lesson_reschedule_accepted", "Перенесення прийнято"),
        ("lesson_reschedule_declined", "Перенесення відхилено"),
        ("lesson_reschedule_counter", "Запропоновано інший час"),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    message_type = models.CharField(
        max_length=50,
        choices=MESSAGE_TYPES,
        default="text"
    )

    lesson = models.ForeignKey(
        CalendarEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_messages"
    )

    change_request = models.ForeignKey(
        "LessonChangeRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_messages"
    )

    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_chat_messages"
    )

    text = models.TextField()

    file = models.FileField(
        upload_to="chat_files/",
        blank=True,
        null=True
    )

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.text[:40]


class LessonChangeRequest(models.Model):
    REQUEST_TYPES = [
        ("reschedule", "Перенесення"),
        ("cancel", "Скасування"),
    ]

    STATUSES = [
        ("pending", "Очікує відповіді"),
        ("accepted", "Прийнято"),
        ("declined", "Відхилено"),
        ("countered", "Запропоновано інший час"),
        ("cancelled", "Скасовано"),
    ]

    lesson = models.ForeignKey(
        CalendarEvent,
        on_delete=models.CASCADE,
        related_name="change_requests"
    )

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="lesson_requests"
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lesson_change_requests"
    )

    request_type = models.CharField(max_length=20, choices=REQUEST_TYPES)
    status = models.CharField(max_length=20, choices=STATUSES, default="pending")

    reason = models.CharField(max_length=255)
    comment = models.TextField(blank=True)

    old_start_time = models.DateTimeField()
    old_end_time = models.DateTimeField(null=True, blank=True)

    proposed_start_time = models.DateTimeField(null=True, blank=True)
    proposed_end_time = models.DateTimeField(null=True, blank=True)

    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responded_lesson_change_requests"
    )

    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_request_type_display()} — {self.lesson.title}"

