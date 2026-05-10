from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import JoinTeacherByCodeForm, TeacherProfileEditForm
from .models import TeacherProfile, StudentTeacherLink, CalendarEvent, StudentProfile,Homework, HomeworkMaterial,HomeworkSubmission,HomeworkSubmissionFile,Notification,Conversation, ChatMessage,LessonChangeRequest
from django.db.models import Q, Max
from django.utils import timezone
import calendar
from datetime import date, datetime, timedelta
import locale
import random
import string
from django.contrib.auth import get_user_model
from django.http import JsonResponse
import os
from django.conf import settings
from google_auth_oauthlib.flow import Flow
from .google_calendar import credentials_to_dict, sync_lesson_to_google_calendar
from django.db.models import Count
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth, TruncYear
from django.views.decorators.http import require_POST

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
def home(request):
    if not request.user.is_authenticated:
        return redirect("landing")
    return render(request, "core/home.html")


@login_required
def dashboard(request):
    return render(request, "core/dashboard.html")


@login_required
def teachers(request):
    return render(request, "core/teachers.html")


@login_required
def dashboard_view(request):
    user = request.user

    if hasattr(user, "teacher_profile"):
        return redirect("teacher_dashboard")

    if hasattr(user, "student_profile"):
        return redirect("student_dashboard")

    messages.error(request, "Профіль користувача не знайдено.")
    return redirect("home")


@login_required
def teacher_dashboard(request):
    user = request.user

    if not hasattr(user, "teacher_profile"):
        messages.error(request, "Ця сторінка доступна тільки для вчителя.")
        return redirect("dashboard")

    teacher_profile = user.teacher_profile

    student_links = teacher_profile.student_links.select_related("student__user")

    now = timezone.now()
    today = now.date()

    today_lessons = CalendarEvent.objects.filter(
        teacher=user,
        start_time__date=today,
        event_type="lesson"
    ).select_related("student").order_by("start_time")

    unchecked_homeworks = HomeworkSubmission.objects.filter(
        homework__teacher=request.user,
        checked_at__isnull=True
    ).select_related(
        "homework",
        "student"
    ).order_by("-submitted_at")[:3]

    current_date = f"{DAYS[now.weekday()]}, {now.day} {MONTHS[now.month]} {now.year}"

    now = timezone.now()

    next_lesson = CalendarEvent.objects.filter(
        teacher=user,
        start_time__gte=now,
    ).order_by("start_time").first()

    today = now.date()

    today_lessons = CalendarEvent.objects.filter(
        teacher=user,
        start_time__date=today,
    ).order_by("start_time")
    completed_lessons_count = today_lessons.filter(start_time__lt=now).count()

    return render(
        request,
        "core/teacher_dashboard.html",
        {
            "teacher_profile": teacher_profile,
            "student_links": student_links,
            "current_date": current_date,
            "next_lesson": next_lesson,
            "today_lessons": today_lessons,
            "now": now,
            "completed_lessons_count": completed_lessons_count,
            "unchecked_homeworks": unchecked_homeworks,
        },
    )


@login_required
def student_dashboard_view(request):
    student_profile = StudentProfile.objects.filter(user=request.user).first()

    if not student_profile:
        return redirect("dashboard")

    if request.method == "POST":
        form = JoinTeacherByCodeForm(request.POST, student_profile=student_profile)
        if form.is_valid():
            form.save()
            return redirect("student_dashboard")
    else:
        form = JoinTeacherByCodeForm(student_profile=student_profile)

    now = timezone.now()
    today = timezone.localdate()

    teacher_links = StudentTeacherLink.objects.filter(
        student=student_profile
    ).select_related("teacher__user")

    homework_tasks = Homework.objects.filter(
        student=request.user,
        submission__isnull=True  # ← головне
    ).order_by("-created_at")[:3]

    next_lesson = CalendarEvent.objects.filter(
        student=request.user,
        start_time__gte=now,
        event_type="lesson",
        is_cancelled=False,
    ).order_by("start_time").first()

    today_lessons = CalendarEvent.objects.filter(
        student=request.user,
        start_time__date=today,
        event_type="lesson",
        is_cancelled=False,
    ).order_by("start_time")

    completed_lessons_count = today_lessons.filter(
        start_time__lt=now
    ).count()

    context = {
        "student_profile": student_profile,
        "teacher_links": teacher_links,
        "form": form,
        "now": now,
        "next_lesson": next_lesson,
        "today_lessons": today_lessons,
        "completed_lessons_count": completed_lessons_count,

        "homework_tasks": [],
        "completed_tasks_count": 0,
        "total_tasks_count": 0,
        "homework_tasks": homework_tasks,
    }

    return render(request, "core/student_dashboard.html", context)

@login_required
def student_profile(request):
    student_profile = StudentProfile.objects.filter(user=request.user).first()

    if not student_profile:
        messages.error(request, "Профіль учня не знайдено.")
        return redirect("student_dashboard")

    is_edit = request.GET.get("edit") == "1"

    if request.method == "POST":
        request.user.first_name = request.POST.get("first_name", "")
        request.user.last_name = request.POST.get("last_name", "")
        request.user.email = request.POST.get("email", "")
        request.user.save()

        student_profile.phone = request.POST.get("phone", "")
        student_profile.save()

        return redirect("student_profile")

    teachers_count = StudentTeacherLink.objects.filter(
        student=student_profile
    ).count()

    today = timezone.localdate()

    today_lessons_count = CalendarEvent.objects.filter(
        student=request.user,
        start_time__date=today,
        event_type="lesson",
        is_cancelled=False,
    ).count()

    lessons_count = CalendarEvent.objects.filter(
        student=request.user,
        event_type="lesson",
        is_cancelled=False,
    ).count()

    context = {
        "student_profile": student_profile,
        "is_edit": is_edit,
        "teachers_count": teachers_count,
        "today_lessons_count": today_lessons_count,
        "lessons_count": lessons_count,
        "completed_tasks_count": 0,
    }

    return render(request, "core/student_profile.html", context)

@login_required
def calendar_view(request):
    today = date.today()

    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    cal = calendar.Calendar(firstweekday=0)
    raw_month_days = cal.monthdayscalendar(year, month)

    events = CalendarEvent.objects.filter(
        Q(teacher=request.user) | Q(student=request.user),
        start_time__year=year,
        start_time__month=month
    ).order_by("start_time")

    events_by_day = {}
    for event in events:
        day = event.start_time.day
        events_by_day.setdefault(day, []).append(event)

    homeworks = Homework.objects.filter(
        Q(teacher=request.user) | Q(student=request.user),
        deadline__year=year,
        deadline__month=month
    ).order_by("deadline")

    homeworks_by_day = {}
    for hw in homeworks:
        if hw.deadline:
            day = hw.deadline.day
            homeworks_by_day.setdefault(day, []).append(hw)

    month_days = []
    for week in raw_month_days:
        week_data = []
        for day in week:
            week_data.append({
                "day": day,
                "events": events_by_day.get(day, []) if day != 0 else [],
                "homeworks": homeworks_by_day.get(day, []) if day != 0 else [],
                "is_today": (
                    day == today.day and
                    month == today.month and
                    year == today.year
                )
            })
        month_days.append(week_data)

    prev_month = month - 1
    prev_year = year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1

    next_month = month + 1
    next_year = year
    if next_month == 13:
        next_month = 1
        next_year += 1

    month_name = {
        1: "Січень", 2: "Лютий", 3: "Березень", 4: "Квітень",
        5: "Травень", 6: "Червень", 7: "Липень", 8: "Серпень",
        9: "Вересень", 10: "Жовтень", 11: "Листопад", 12: "Грудень"
    }[month]

    weeks_count = len(month_days)

    return render(request, "core/calendar.html", {
        "year": year,
        "month": month,
        "month_name": month_name,
        "month_days": month_days,
        "prev_month": prev_month,
        "prev_year": prev_year,
        "next_month": next_month,
        "next_year": next_year,
        "weeks_count": weeks_count,
    })

DAYS = {
    0: "Понеділок",
    1: "Вівторок",
    2: "Середа",
    3: "Четвер",
    4: "П’ятниця",
    5: "Субота",
    6: "Неділя",
}

MONTHS = {
    1: "січня", 2: "лютого", 3: "березня",
    4: "квітня", 5: "травня", 6: "червня",
    7: "липня", 8: "серпня", 9: "вересня",
    10: "жовтня", 11: "листопада", 12: "грудня",
}

@login_required
def teacher_profile(request):
    user = request.user

    if not hasattr(user, "teacher_profile"):
        messages.error(request, "Ця сторінка доступна тільки для вчителя.")
        return redirect("dashboard")

    teacher_profile = user.teacher_profile
    student_links = teacher_profile.student_links.select_related("student__user")

    lessons_count = CalendarEvent.objects.filter(
        teacher=request.user,
        start_time__lt=timezone.now()
    ).count()

    is_edit = request.GET.get("edit") == "1"

    if request.method == "POST":
        user.first_name = request.POST.get("first_name", "").strip()
        user.last_name = request.POST.get("last_name", "").strip()
        user.email = request.POST.get("email", "").strip()

        teacher_profile.phone = request.POST.get("phone", "").strip()
        teacher_profile.subject = request.POST.get("subject", "").strip()

        user.save()
        teacher_profile.save()

        return redirect("teacher_profile")

    return render(
        request,
        "core/teacher_profile.html",
        {
            "teacher_profile": teacher_profile,
            "students_count": student_links.count(),
            "lessons_count": lessons_count,
            "is_edit": is_edit,
        },
    )
@login_required
def create_lesson(request, lesson_id=None):
    teacher_profile = TeacherProfile.objects.filter(user=request.user).first()

    if not teacher_profile:
        messages.error(request, "Профіль вчителя не знайдено.")
        return redirect("teacher_dashboard")

    lesson = None
    is_edit = False

    if lesson_id is not None:
        lesson = get_object_or_404(
            CalendarEvent,
            id=lesson_id,
            teacher=request.user
        )
        is_edit = True

    student_profiles = StudentProfile.objects.filter(
        teacher_links__teacher=teacher_profile
    ).select_related("user").distinct().order_by("user__first_name", "user__last_name")

    durations = [30, 45, 60, 90, 120]

    weekdays = [
        {"value": "mon", "label": "Пн"},
        {"value": "tue", "label": "Вт"},
        {"value": "wed", "label": "Ср"},
        {"value": "thu", "label": "Чт"},
        {"value": "fri", "label": "Пт"},
        {"value": "sat", "label": "Сб"},
        {"value": "sun", "label": "Нд"},
    ]

    delivery_methods = [
        "Текст у платформі",
        "Фото",
        "Файл",
        "Посилання",
        "Усно на уроці",
    ]

    if is_edit:
        duration_minutes = 30

        if lesson.end_time:
            duration_minutes = int(
                (lesson.end_time - lesson.start_time).total_seconds() / 60
            )

        form_data = {
            "student_id": str(lesson.student.id) if lesson.student else "",
            "topic": lesson.title or "",
            "lesson_date": lesson.start_time.date().isoformat(),
            "lesson_time": lesson.start_time.time().strftime("%H:%M"),
            "duration": str(duration_minutes) if duration_minutes in durations else "custom",
            "custom_duration": str(duration_minutes) if duration_minutes not in durations else "",
            "repeat_days": [],
            "description": lesson.description or "",
            "meeting_link": lesson.meeting_link or "",
            "homework_deadline": "",
            "delivery_method": "Текст у платформі",
            "notify_student": "on",
        }
    else:
        form_data = {
            "student_id": "",
            "topic": "",
            "lesson_date": "",
            "lesson_time": "",
            "duration": "30",
            "custom_duration": "",
            "repeat_days": [],
            "description": "",
            "meeting_link": "",
            "homework_deadline": "",
            "delivery_method": "Текст у платформі",
            "notify_student": "on",
        }

    if request.method == "POST":
        form_data["student_id"] = request.POST.get("student_id", "")
        form_data["topic"] = request.POST.get("topic", "").strip()
        form_data["lesson_date"] = request.POST.get("lesson_date", "")
        form_data["lesson_time"] = request.POST.get("lesson_time", "")
        form_data["duration"] = request.POST.get("duration", "30")
        form_data["custom_duration"] = request.POST.get("custom_duration", "").strip()
        form_data["repeat_days"] = request.POST.getlist("repeat_days")
        form_data["description"] = request.POST.get("description", "").strip()
        form_data["meeting_link"] = request.POST.get("meeting_link", "").strip()
        form_data["homework_deadline"] = request.POST.get("homework_deadline", "")
        form_data["delivery_method"] = request.POST.get(
            "delivery_method",
            "Текст у платформі"
        )
        form_data["notify_student"] = request.POST.get("notify_student", "")

        errors = []

        if not form_data["student_id"]:
            errors.append("Оберіть учня.")

        if not form_data["topic"]:
            errors.append("Вкажіть тему уроку.")

        if not form_data["lesson_date"]:
            errors.append("Оберіть дату уроку.")

        if not form_data["lesson_time"]:
            errors.append("Оберіть час початку.")

        if form_data["duration"] == "custom" and not form_data["custom_duration"]:
            errors.append("Вкажіть власну тривалість уроку.")

        selected_student = None

        if form_data["student_id"]:
            selected_student = student_profiles.filter(
                id=form_data["student_id"]
            ).first()

            if not selected_student:
                errors.append("Обраного учня не знайдено.")


        if errors:
            for error in errors:
                messages.error(request, error)

        else:
            try:
                duration_minutes = (
                    int(form_data["custom_duration"])
                    if form_data["duration"] == "custom"
                    else int(form_data["duration"])
                )

                start_dt = datetime.strptime(
                    f'{form_data["lesson_date"]} {form_data["lesson_time"]}',
                    "%Y-%m-%d %H:%M"
                )
                end_dt = start_dt + timedelta(minutes=duration_minutes)
                start_dt = timezone.make_aware(start_dt)
                end_dt = timezone.make_aware(end_dt)
                if is_edit:
                    lesson.title = form_data["topic"]
                    lesson.event_type = "lesson"
                    lesson.description = form_data["description"] or ""
                    lesson.meeting_link = form_data["meeting_link"] or ""
                    lesson.start_time = start_dt
                    lesson.end_time = end_dt
                    lesson.teacher = request.user
                    lesson.student = selected_student.user
                    lesson.save()

                    # messages.success(request, "Урок успішно оновлено.")
                    return redirect("lesson_detail", lesson_id=lesson.id)

                else:
                    lesson = CalendarEvent.objects.create(
                        title=form_data["topic"],
                        event_type="lesson",
                        description=form_data["description"] or "",
                        meeting_link=form_data["meeting_link"] or "",
                        start_time=start_dt,
                        end_time=end_dt,
                        teacher=request.user,
                        student=selected_student.user,
                    )
                    if request.session.get("google_credentials"):
                        sync_lesson_to_google_calendar(request, lesson)

                   # if form_data["notify_student"] == "on":
                        Notification.objects.create(
                            user=selected_student.user,
                            title="Новий урок",
                            message=f"Вам призначено новий урок: {lesson.title}",
                            notification_type="lesson_created",
                            link=f"/lesson/{lesson.id}/"
                        )

                    weekday_map = {
                        "mon": 0,
                        "tue": 1,
                        "wed": 2,
                        "thu": 3,
                        "fri": 4,
                        "sat": 5,
                        "sun": 6,
                    }

                    repeat_days = form_data["repeat_days"]

                    if repeat_days:
                        for day_code in repeat_days:
                            target_weekday = weekday_map.get(day_code)

                            if target_weekday is None:
                                continue

                            days_ahead = (target_weekday - start_dt.weekday()) % 7

                            if days_ahead == 0:
                                days_ahead = 7

                            first_repeat_start = start_dt + timedelta(days=days_ahead)

                            for i in range(8):
                                repeat_start = first_repeat_start + timedelta(days=7 * i)
                                repeat_end = repeat_start + timedelta(minutes=duration_minutes)

                                repeat_lesson = CalendarEvent.objects.create(
                                    title=form_data["topic"],
                                    event_type="lesson",
                                    description=form_data["description"] or "",
                                    meeting_link=form_data["meeting_link"] or "",
                                    start_time=repeat_start,
                                    end_time=repeat_end,
                                    teacher=request.user,
                                    student=selected_student.user,
                                )

                                if request.session.get("google_credentials"):
                                    sync_lesson_to_google_calendar(request, repeat_lesson)

                    return redirect("lesson_detail", lesson_id=lesson.id)

            except ValueError:
                messages.error(request, "Перевірте правильність дати, часу або тривалості.")


    context = {
        "students": student_profiles,
        "durations": durations,
        "weekdays": weekdays,
        "delivery_methods": delivery_methods,
        "form_data": form_data,
        "selected_student": None,
        "duration_text": "30 хв",
        "repeat_days_labels": [],
        "lesson": lesson,
        "is_edit": is_edit,
    }

    return render(request, "core/create_lesson.html", context)

@login_required
def lessons_view(request):
    today = date.today()

    if hasattr(request.user, "teacher_profile"):
        lessons = CalendarEvent.objects.filter(
            teacher=request.user,
            event_type="lesson"
        ).order_by("start_time")

        role = "teacher"

    elif hasattr(request.user, "student_profile"):
        lessons = CalendarEvent.objects.filter(
            student=request.user,
            event_type="lesson"
        ).order_by("start_time")

        role = "student"

    else:
        lessons = CalendarEvent.objects.none()
        role = None

    today_lessons = []
    future_lessons = []
    past_lessons = []

    for lesson in lessons:
        lesson_date = lesson.start_time.date()

        if lesson_date == today:
            today_lessons.append(lesson)
        elif lesson_date > today:
            future_lessons.append(lesson)
        else:
            past_lessons.append(lesson)

    context = {
        "role": role,
        "today": today,
        "today_lessons": today_lessons,
        "future_lessons": future_lessons,
        "past_lessons": past_lessons,
        "total_lessons": lessons.count(),
        "planned_lessons": len(today_lessons) + len(future_lessons),
        "past_count": len(past_lessons),
    }

    return render(request, "core/lessons.html", context)

@login_required
def calendar_day(request, year, month, day):
    selected_date = date(year, month, day)

    events = CalendarEvent.objects.filter(
        Q(teacher=request.user) | Q(student=request.user),
        start_time__date=selected_date
    ).order_by("start_time")

    homeworks = Homework.objects.filter(
        Q(teacher=request.user) | Q(student=request.user),
        deadline__date=selected_date
    ).order_by("deadline")

    late_homeworks_count = homeworks.filter(status="late").count()
    is_today = selected_date == date.today()

    month_name = MONTHS[selected_date.month]
    weekday_name = DAYS[selected_date.weekday()]

    return render(request, "core/calendar_day.html", {
        "selected_date": selected_date,
        "events": events,
        "homeworks": homeworks,
        "late_homeworks_count": late_homeworks_count,
        "is_today": is_today,
        "month_name": month_name,
        "weekday_name": weekday_name,
    })

@login_required
def generate_teacher_code(request):
    if not hasattr(request.user, "teacher_profile"):
        return JsonResponse({"error": "Доступ заборонено"}, status=403)

    teacher_profile = request.user.teacher_profile

    new_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    teacher_profile.access_code = new_code
    teacher_profile.save()

    return JsonResponse({"code": new_code})
User = get_user_model()

@login_required
def add_student_manual(request):
    if not hasattr(request.user, "teacher_profile"):
        # messages.error(request, "Ця дія доступна тільки для вчителя.")
        return redirect("dashboard")

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()

        try:
            student_user = User.objects.get(email__iexact=email)
            student_profile = StudentProfile.objects.get(user=student_user)

            StudentTeacherLink.objects.get_or_create(
                teacher=request.user.teacher_profile,
                student=student_profile
            )

            messages.success(request, "Учня додано.")
        except User.DoesNotExist:
            messages.error(request, "Учня з такою поштою не знайдено.")
        except StudentProfile.DoesNotExist:
            messages.error(request, "Цей користувач не є учнем.")

    return redirect("teacher_dashboard")

@login_required
def lesson_detail(request, lesson_id):
    lesson = get_object_or_404(CalendarEvent, id=lesson_id)

    is_teacher = lesson.teacher == request.user
    is_student = lesson.student == request.user
    teacher_profile = None
    student_profile = None

    if lesson.teacher:
        teacher_profile = TeacherProfile.objects.filter(user=lesson.teacher).first()

    if lesson.student:
        student_profile = StudentProfile.objects.filter(user=lesson.student).first()

    return render(request, "core/lesson_detail.html", {
        "lesson": lesson,
        "is_teacher": is_teacher,
        "is_student": is_student,
        "teacher_profile": teacher_profile,
        "student_profile": student_profile,
    })


@login_required
def homework(request):
    if TeacherProfile.objects.filter(user=request.user).exists():
        role = "teacher"
        homeworks = Homework.objects.filter(
            teacher=request.user
        ).select_related("student").order_by("-created_at")
    else:
        role = "student"
        homeworks = Homework.objects.filter(
            student=request.user
        ).select_related("teacher").order_by("-created_at")

    homeworks.filter(
        status="assigned",
        deadline__lt=timezone.now()
    ).update(status="late")

    return render(request, "core/homework.html", {
        "role": role,
        "homeworks": homeworks,
        "total_count": homeworks.count(),
        "assigned_count": homeworks.filter(status="assigned").count(),
        "submitted_count": homeworks.filter(status="submitted").count(),
        "checked_count": homeworks.filter(status="checked").count(),
        "late_count": homeworks.filter(status="late").count(),
    })

@login_required
def create_homework(request, pk=None):
    teacher_profile = TeacherProfile.objects.filter(user=request.user).first()

    if not teacher_profile:
        return redirect("dashboard")

    homework = None

    if pk:
        homework = get_object_or_404(
            Homework,
            pk=pk,
            teacher=request.user
        )

    student_links = StudentTeacherLink.objects.filter(
        teacher=teacher_profile
    ).select_related("student__user")

    students = [link.student for link in student_links]

    if request.method == "POST":
        student_id = request.POST.get("student")
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        deadline_date = request.POST.get("deadline_date")
        deadline_time = request.POST.get("deadline_time") or "23:59"

        allow_late = bool(request.POST.get("allow_late"))
        require_file = bool(request.POST.get("require_file"))
        materials = request.FILES.getlist("materials")

        if not student_id or not title or not description:
            if homework:
                return redirect("edit_homework", pk=homework.pk)
            return redirect("create_homework")

        student_profile = StudentProfile.objects.filter(
            id=student_id,
            teacher_links__teacher=teacher_profile
        ).select_related("user").first()

        if not student_profile:
            if homework:
                return redirect("edit_homework", pk=homework.pk)
            return redirect("create_homework")

        deadline = None

        if deadline_date:
            deadline_naive = datetime.strptime(
                f"{deadline_date} {deadline_time}",
                "%Y-%m-%d %H:%M"
            )
            deadline = timezone.make_aware(deadline_naive)

        if homework:
            homework.student = student_profile.user
            homework.title = title
            homework.description = description
            homework.deadline = deadline
            homework.allow_late_submission = allow_late
            homework.allow_file_answer = require_file
            homework.save()
        else:
            homework = Homework.objects.create(
                teacher=request.user,
                student=student_profile.user,
                title=title,
                description=description,
                deadline=deadline,
                status="assigned",
                allow_late_submission=allow_late,
                allow_file_answer=require_file,
            )

            if homework:
                homework.student = student_profile.user
                homework.title = title
                homework.description = description
                homework.deadline = deadline
                homework.allow_late_submission = allow_late
                homework.allow_file_answer = require_file
                homework.save()
            else:
                homework = Homework.objects.create(
                    teacher=request.user,
                    student=student_profile.user,
                    title=title,
                    description=description,
                    deadline=deadline,
                    status="assigned",
                    allow_late_submission=allow_late,
                    allow_file_answer=require_file,
                )

            delete_ids = request.POST.getlist("delete_material_ids")
            Notification.objects.create(
                user=homework.student,
                title="Нове домашнє завдання",
                message=f"Вам призначено нове домашнє завдання: {homework.title}",
                notification_type="homework_created",
                link=f"/homework/{homework.id}/"
            )

        delete_ids = request.POST.getlist("delete_material_ids")


        if delete_ids:
            materials_to_delete = HomeworkMaterial.objects.filter(
                id__in=delete_ids,
                homework=homework
            )

            for material in materials_to_delete:
                material.file.delete(save=False)
                material.delete()

        for file in materials:
            HomeworkMaterial.objects.create(
                homework=homework,
                file=file
            )

        return redirect("homework_detail", pk=homework.pk)
    selected_student_id = ""

    if homework:
        student_profile = StudentProfile.objects.filter(user=homework.student).first()
        if student_profile:
            selected_student_id = student_profile.id

    return render(request, "core/create_homework.html", {
        "students": students,
        "homework": homework,
        "is_edit": bool(homework),
        "selected_student_id": selected_student_id,
    })
@login_required
def homework_detail(request, pk):
    homework = get_object_or_404(Homework, pk=pk)
    if (
            homework.status == "assigned"
            and homework.deadline
            and timezone.now() > homework.deadline
    ):
        homework.status = "late"
        homework.save()

    is_teacher = request.user == homework.teacher
    is_student = request.user == homework.student

    if not is_teacher and not is_student:
        return redirect("dashboard")

    submission = getattr(homework, "submission", None)
    edit_mode = request.GET.get("edit") == "1"
    teacher_profile = TeacherProfile.objects.filter(user=homework.teacher).first()
    student_profile = StudentProfile.objects.filter(user=homework.student).first()

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "submit_homework" and is_student:
            is_deadline_passed = homework.deadline and timezone.now() > homework.deadline

            if is_deadline_passed and not homework.allow_late_submission:
                messages.error(request, "Термін здачі вже минув. Пізня здача заборонена.")
                return redirect("homework_detail", pk=homework.pk)

            submission, created = HomeworkSubmission.objects.get_or_create(
                homework=homework,
                student=request.user
            )

            if homework.allow_text_answer:
                submission.answer_text = request.POST.get("answer_text", "").strip()

            submission.save()

            if homework.allow_file_answer:
                files = request.FILES.getlist("files")
                for file in files:
                    HomeworkSubmissionFile.objects.create(
                        submission=submission,
                        file=file
                    )

            if is_deadline_passed:
                homework.status = "late"
            else:
                homework.status = "submitted"

            homework.checked_at = None
            homework.teacher_comment = ""
            homework.save()

            submission.teacher_comment = ""
            submission.checked_at = None
            submission.save()

            Notification.objects.create(
                user=homework.teacher,
                title="Домашнє завдання здано",
                message=f"{request.user.first_name} {request.user.last_name} здав(ла) завдання: {homework.title}",
                notification_type="homework_submitted",
                link=f"/homework/{homework.id}/"
            )

            messages.success(request, "Домашнє завдання надіслано.")
            return redirect("homework_detail", pk=homework.pk)

        # учень видаляє свій файл
        if action == "delete_submission_file" and is_student and submission:
            file_id = request.POST.get("file_id")
            file_obj = get_object_or_404(
                HomeworkSubmissionFile,
                id=file_id,
                submission=submission
            )
            file_obj.delete()
            return redirect("homework_detail", pk=homework.pk)

        # вчитель перевіряє
        if action == "review_homework" and is_teacher and submission:
            comment = request.POST.get("teacher_comment", "").strip()
            result = request.POST.get("result")

            # if not comment:
            #     messages.error(request, "Напиши коментар перед перевіркою.")
            #     return redirect("homework_detail", pk=homework.pk)

            submission.teacher_comment = comment
            submission.checked_at = timezone.now()
            submission.save()

            homework.teacher_comment = comment
            homework.checked_at = timezone.now()

            if result == "checked":
                homework.status = "checked"

            homework.save()

            Notification.objects.create(
                user=homework.student,
                title="Домашнє завдання перевірено",
                message=f"Ваше домашнє завдання перевірено: {homework.title}",
                notification_type="homework_checked",
                link=f"/homework/{homework.id}/"
            )

            #messages.success(request, "Результат перевірки збережено.")
            return redirect("homework_detail", pk=homework.pk)



    return render(request, "core/homework_detail.html", {
        "homework": homework,
        "submission": submission,
        "is_teacher": is_teacher,
        "is_student": is_student,
        "now": timezone.now(),
        "edit_mode": edit_mode,
        "teacher_profile": teacher_profile,
        "student_profile": student_profile,
    })

@login_required
def delete_homework(request, pk):
    homework = get_object_or_404(Homework, pk=pk)

    if request.user != homework.teacher:
        return redirect("dashboard")

    if request.method == "POST":
        homework.delete()
        #messages.success(request, "Домашнє завдання видалено.")
        return redirect("homework")

    return redirect("homework_detail", pk=homework.pk)

@login_required
def teacher_public_profile(request, teacher_id):
    teacher = get_object_or_404(TeacherProfile, id=teacher_id)

    student_profile = StudentProfile.objects.filter(user=request.user).first()

    if not student_profile:
        return redirect("dashboard")

    is_linked = StudentTeacherLink.objects.filter(
        teacher=teacher,
        student=student_profile
    ).exists()

    if not is_linked:
        return redirect("dashboard")

    upcoming_lessons = CalendarEvent.objects.filter(
        teacher=teacher.user,
        student=student_profile.user,
        start_time__gte=timezone.now(),
        is_cancelled=False
    ).order_by("start_time")[:3]

    homeworks = Homework.objects.filter(
        teacher=teacher.user,
        student=student_profile.user
    ).order_by("-created_at")[:3]

    context = {
        "profile_type": "teacher",
        "teacher": teacher,
        "upcoming_lessons": upcoming_lessons,
        "homeworks": homeworks,
    }

    return render(request, "core/profile_detail.html", context)


@login_required
def student_public_profile(request, student_id):
    student = get_object_or_404(StudentProfile, id=student_id)

    teacher_profile = TeacherProfile.objects.filter(user=request.user).first()

    if not teacher_profile:
        return redirect("dashboard")

    is_linked = StudentTeacherLink.objects.filter(
        teacher=teacher_profile,
        student=student
    ).exists()

    if not is_linked:
        return redirect("dashboard")

    upcoming_lessons = CalendarEvent.objects.filter(
        teacher=teacher_profile.user,
        student=student.user,
        start_time__gte=timezone.now(),
        is_cancelled=False
    ).order_by("start_time")[:3]

    homeworks = Homework.objects.filter(
        teacher=teacher_profile.user,
        student=student.user
    ).order_by("-created_at")[:4]

    context = {
        "profile_type": "student",
        "student": student,
        "teacher": teacher_profile,
        "upcoming_lessons": upcoming_lessons,
        "homeworks": homeworks,
    }

    return render(request, "core/profile_detail.html", context)

def landing(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    return render(request, "landing.html")


@login_required
def google_calendar_auth(request):
    credentials_path = os.path.abspath(
        os.path.join(settings.BASE_DIR, "..", "credentials.json")
    )

    flow = Flow.from_client_secrets_file(
        credentials_path,
        scopes=["https://www.googleapis.com/auth/calendar"],
        autogenerate_code_verifier=True,
    )

    flow.redirect_uri = "http://127.0.0.1:8000/google/callback/"

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    request.session["google_oauth_state"] = state
    request.session["google_code_verifier"] = flow.code_verifier

    return redirect(authorization_url)


@login_required
def google_calendar_callback(request):
    credentials_path = os.path.abspath(
        os.path.join(settings.BASE_DIR, "..", "credentials.json")
    )

    state = request.session.get("google_oauth_state")
    code_verifier = request.session.get("google_code_verifier")

    flow = Flow.from_client_secrets_file(
        credentials_path,
        scopes=["https://www.googleapis.com/auth/calendar"],
        state=state,
        code_verifier=code_verifier,
    )

    flow.redirect_uri = "http://127.0.0.1:8000/google/callback/"

    flow.fetch_token(
        authorization_response=request.build_absolute_uri()
    )

    credentials = flow.credentials
    request.session["google_credentials"] = credentials_to_dict(credentials)

    sync_user_lessons_after_google_connect(request)

    return redirect("dashboard")


def sync_user_lessons_after_google_connect(request):
    if hasattr(request.user, "teacher_profile"):
        lessons = CalendarEvent.objects.filter(
            teacher=request.user,
            event_type="lesson",
            is_cancelled=False,
        )

    elif hasattr(request.user, "student_profile"):
        lessons = CalendarEvent.objects.filter(
            student=request.user,
            event_type="lesson",
            is_cancelled=False,
        )

    else:
        return

    for lesson in lessons:
        sync_lesson_to_google_calendar(request, lesson)

@login_required
def teacher_statistics(request):
    teacher_profile = TeacherProfile.objects.filter(user=request.user).first()

    if not teacher_profile:
        return redirect("dashboard")

    now = timezone.now()
    period = request.GET.get("period", "month")

    if period == "week":
        period_start = now - timedelta(days=7)
        period_label = "Останні 7 днів"
    elif period == "month":
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_label = "Цей місяць"
    elif period == "year":
        period_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        period_label = "Цей рік"
    elif period == "all":
        period_start = None
        period_label = "Весь час"
    else:
        period = "month"
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_label = "Цей місяць"

    lessons = CalendarEvent.objects.filter(
        teacher=request.user,
        event_type="lesson",
        is_cancelled=False
    )

    if period_start:
        period_lessons = lessons.filter(
            start_time__gte=period_start,
            start_time__lte=now
        )
    else:
        period_lessons = lessons.filter(start_time__lte=now)

    completed_lessons = period_lessons.filter(start_time__lt=now)

    total_minutes = 0
    for lesson in completed_lessons:
        if lesson.start_time and lesson.end_time:
            total_minutes += int((lesson.end_time - lesson.start_time).total_seconds() // 60)

    total_hours = round(total_minutes / 60, 1)

    homeworks = Homework.objects.filter(teacher=request.user)

    if period_start:
        period_homeworks = homeworks.filter(created_at__gte=period_start)
    else:
        period_homeworks = homeworks

    hw_total = period_homeworks.count()
    hw_submitted = period_homeworks.filter(status__in=["submitted", "checked"]).count()
    hw_checked = period_homeworks.filter(status="checked").count()
    hw_late = period_homeworks.filter(status="late").count()
    hw_need_check = period_homeworks.filter(status="submitted").count()

    hw_percent = round((hw_submitted / hw_total) * 100) if hw_total else 0

    student_links = StudentTeacherLink.objects.filter(
        teacher=teacher_profile
    ).select_related("student__user")

    students_stats = []

    for link in student_links:
        student_user = link.student.user

        student_lessons = lessons.filter(student=student_user)

        if period_start:
            student_completed_lessons = student_lessons.filter(
                start_time__gte=period_start,
                start_time__lt=now
            )
            student_homeworks = homeworks.filter(
                student=student_user,
                created_at__gte=period_start
            )
        else:
            student_completed_lessons = student_lessons.filter(start_time__lt=now)
            student_homeworks = homeworks.filter(student=student_user)

        student_hw_total = student_homeworks.count()
        student_hw_done = student_homeworks.filter(status__in=["submitted", "checked"]).count()
        student_hw_late = student_homeworks.filter(status="late").count()

        homework_percent = round((student_hw_done / student_hw_total) * 100) if student_hw_total else 0

        last_lesson = student_lessons.filter(start_time__lt=now).order_by("-start_time").first()

        if homework_percent >= 85:
            status = "Відмінно"
            status_class = "green"
        elif homework_percent >= 60:
            status = "Добре"
            status_class = "amber"
        else:
            status = "Потребує уваги"
            status_class = "red"

        students_stats.append({
            "student": student_user,
            "lessons_count": student_completed_lessons.count(),
            "homework_percent": homework_percent,
            "homework_late": student_hw_late,
            "last_lesson": last_lesson,
            "status": status,
            "status_class": status_class,
        })

    chart_labels = []
    chart_values = []

    if period == "week":
        chart_labels = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
        chart_values = [0, 0, 0, 0, 0, 0, 0]

        for lesson in completed_lessons:
            day_index = lesson.start_time.weekday()
            chart_values[day_index] += 1

    elif period == "month":
        chart_labels = ["Тиж 1", "Тиж 2", "Тиж 3", "Тиж 4"]
        chart_values = [0, 0, 0, 0]

        for lesson in completed_lessons:
            day = lesson.start_time.day

            if day <= 7:
                chart_values[0] += 1
            elif day <= 14:
                chart_values[1] += 1
            elif day <= 21:
                chart_values[2] += 1
            else:
                chart_values[3] += 1

    elif period == "year":
        chart_labels = ["Січ", "Лют", "Бер", "Кві", "Тра", "Чер", "Лип", "Сер", "Вер", "Жов", "Лис", "Гру"]
        chart_values = [0] * 12

        for lesson in completed_lessons:
            month_index = lesson.start_time.month - 1
            chart_values[month_index] += 1

    else:
        chart_labels = ["2024", "2025", "2026"]
        chart_values = [0, 0, 0]

        for lesson in completed_lessons:
            year = lesson.start_time.year

            if year == 2024:
                chart_values[0] += 1
            elif year == 2025:
                chart_values[1] += 1
            elif year == 2026:
                chart_values[2] += 1

    max_chart_value = max(chart_values) if chart_values and max(chart_values) > 0 else 1

    chart_data = []

    for index, label in enumerate(chart_labels):
        value = chart_values[index]
        height = round((value / max_chart_value) * 100) if max_chart_value else 0

        chart_data.append({
            "label": label,
            "value": value,
            "height": height,
        })

    context = {
        "period": period,
        "period_label": period_label,

        "month_lessons_count": completed_lessons.count(),
        "total_hours": total_hours,
        "hw_total": hw_total,
        "hw_submitted": hw_submitted,
        "hw_checked": hw_checked,
        "hw_late": hw_late,
        "hw_need_check": hw_need_check,
        "hw_percent": hw_percent,
        "students_count": student_links.count(),
        "students_stats": students_stats,
        "chart_data": chart_data,
    }

    return render(request, "core/teacher_statistics.html", context)
@login_required
def student_statistics(request):
    student = request.user
    now = timezone.now()
    period = request.GET.get("period", "month")

    if period == "week":
        period_start = now - timedelta(days=7)
        period_label = "Останні 7 днів"
    elif period == "month":
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_label = "Цей місяць"
    elif period == "year":
        period_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        period_label = "Цей рік"
    elif period == "all":
        period_start = None
        period_label = "Весь час"
    else:
        period = "month"
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_label = "Цей місяць"

    lessons = CalendarEvent.objects.filter(
        student=student,
        event_type="lesson",
        is_cancelled=False
    )

    if period_start:
        period_lessons = lessons.filter(
            start_time__gte=period_start,
            start_time__lte=now
        )
    else:
        period_lessons = lessons.filter(start_time__lte=now)

    completed_lessons = period_lessons.filter(start_time__lt=now)

    homeworks = Homework.objects.filter(student=student)

    if period_start:
        period_homeworks = homeworks.filter(created_at__gte=period_start)
    else:
        period_homeworks = homeworks

    total_homeworks = period_homeworks.count()
    submitted_homeworks = period_homeworks.filter(status="submitted").count()
    checked_homeworks = period_homeworks.filter(status="checked").count()
    late_homeworks = period_homeworks.filter(status="late").count()
    assigned_homeworks = period_homeworks.filter(status="assigned").count()

    completed_homeworks = submitted_homeworks + checked_homeworks

    completion_percent = round((completed_homeworks / total_homeworks) * 100) if total_homeworks else 0
    checked_percent = round((checked_homeworks / total_homeworks) * 100) if total_homeworks else 0
    late_percent = round((late_homeworks / total_homeworks) * 100) if total_homeworks else 0

    chart_labels = []
    chart_values = []

    if period == "week":
        chart_labels = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
        chart_values = [0, 0, 0, 0, 0, 0, 0]

        for lesson in completed_lessons:
            day_index = lesson.start_time.weekday()
            chart_values[day_index] += 1

    elif period == "month":
        chart_labels = ["Тиж 1", "Тиж 2", "Тиж 3", "Тиж 4"]
        chart_values = [0, 0, 0, 0]

        for lesson in completed_lessons:
            day = lesson.start_time.day

            if day <= 7:
                chart_values[0] += 1
            elif day <= 14:
                chart_values[1] += 1
            elif day <= 21:
                chart_values[2] += 1
            else:
                chart_values[3] += 1

    elif period == "year":
        chart_labels = ["Січ", "Лют", "Бер", "Кві", "Тра", "Чер", "Лип", "Сер", "Вер", "Жов", "Лис", "Гру"]
        chart_values = [0] * 12

        for lesson in completed_lessons:
            month_index = lesson.start_time.month - 1
            chart_values[month_index] += 1

    else:
        years = completed_lessons.dates("start_time", "year")
        chart_labels = [str(year.year) for year in years]
        chart_values = []

        for year in years:
            chart_values.append(
                completed_lessons.filter(start_time__year=year.year).count()
            )

    max_chart_value = max(chart_values) if chart_values and max(chart_values) > 0 else 1

    chart_data = []

    for index, label in enumerate(chart_labels):
        value = chart_values[index]
        height = round((value / max_chart_value) * 100) if max_chart_value else 0

        chart_data.append({
            "label": label,
            "value": value,
            "height": height,
        })

    recent_homeworks = homeworks.order_by("-created_at")[:5]


    context = {
        "period": period,
        "period_label": period_label,

        "total_lessons": completed_lessons.count(),
        "total_homeworks": total_homeworks,

        "submitted_homeworks": submitted_homeworks,
        "completed_homeworks": completed_homeworks,
        "checked_homeworks": checked_homeworks,
        "late_homeworks": late_homeworks,
        "assigned_homeworks": assigned_homeworks,

        "completion_percent": completion_percent,
        "checked_percent": checked_percent,
        "late_percent": late_percent,

        "recent_homeworks": recent_homeworks,
        "chart_data": chart_data,
    }

    return render(request, "core/student_statistics.html", context)
@login_required
def notifications_view(request):
    notifications = Notification.objects.filter(
        user=request.user
    ).order_by("-created_at")

    today = timezone.localdate()
    yesterday = today - timedelta(days=1)

    context = {
        "notifications": notifications,
        "total_count": notifications.count(),
        "unread_count": notifications.filter(is_read=False).count(),
        "today": today,
        "yesterday": yesterday,
    }

    return render(request, "core/notifications.html", context)


@login_required
@require_POST
def mark_notification_read(request, pk):
    Notification.objects.filter(
        id=pk,
        user=request.user
    ).update(is_read=True)

    return JsonResponse({"status": "ok"})

@login_required
def mark_all_notifications_read(request):
    Notification.objects.filter(
        user=request.user,
        is_read=False
    ).update(is_read=True)

    return JsonResponse({"status": "ok"})
@login_required
def unread_notifications_api(request):
    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by("-created_at")[:5]

    data = []

    for n in notifications:
        data.append({
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "link": n.link or "",
            "type": n.notification_type,
        })

    return JsonResponse({
        "notifications": data
    })


@login_required
def chat_view(request, conversation_id=None):
    user = request.user


    if hasattr(user, "teacher_profile"):
        student_links = StudentTeacherLink.objects.filter(
            teacher=user.teacher_profile
        ).select_related("student__user")

        for link in student_links:
            Conversation.objects.get_or_create(
                teacher=user,
                student=link.student.user
            )

        conversations = Conversation.objects.filter(teacher=user)

    else:
        links = StudentTeacherLink.objects.filter(
            student=user.student_profile
        ).select_related("teacher__user")

        for link in links:
            Conversation.objects.get_or_create(
                teacher=link.teacher.user,
                student=user
            )

        conversations = Conversation.objects.filter(student=user)

    conversations = conversations.order_by("-updated_at")

    active_conversation = None

    if conversation_id:
        active_conversation = get_object_or_404(
            conversations,
            id=conversation_id
        )
    elif conversations.exists():
        active_conversation = conversations.first()

    messages = []
    if active_conversation:
        Notification.objects.filter(
            user=request.user,
            link=f"/messages/{active_conversation.id}/",
            is_read=False
        ).update(is_read=True)

    if active_conversation:
        messages = active_conversation.messages.select_related(
            "sender",
            "change_request",
            "lesson"
        )

        active_conversation.messages.exclude(sender=user).update(is_read=True)

    context = {
        "conversations": conversations,
        "active_conversation": active_conversation,
        "messages": messages,
    }

    return render(request, "core/chat.html", context)


@login_required
def send_chat_message(request, conversation_id):
    if request.method != "POST":
        return JsonResponse({"error": "Метод не дозволений"}, status=405)

    conversation = get_object_or_404(
        Conversation.objects.filter(
            Q(teacher=request.user) | Q(student=request.user)
        ),
        id=conversation_id
    )

    text = request.POST.get("text", "").strip()
    file = request.FILES.get("file")

    if not text and not file:
        return JsonResponse({"error": "Порожнє повідомлення"}, status=400)

    message = ChatMessage.objects.create(
        conversation=conversation,
        sender=request.user,
        text=text,
        file=file
    )
    conversation.updated_at = message.created_at
    conversation.save(update_fields=["updated_at"])

    receiver = (
        conversation.student
        if request.user == conversation.teacher
        else conversation.teacher
    )

    Notification.objects.create(
        user=receiver,
        title="Нове повідомлення",
        message=f"{request.user.first_name} написав(ла) тобі",
        notification_type="message",
        link=f"/messages/{conversation.id}/"
    )

    return JsonResponse({
        "id": message.id,
        "conversation_id": conversation.id,
        "text": message.text,
        "time": message.created_at.strftime("%H:%M"),
        "file_url": message.file.url if message.file else "",
        "file_name": message.file.name.split("/")[-1] if message.file else "",
    })
@login_required
def unread_notifications(request):
    notifications_count = request.user.notifications.filter(
        is_read=False
    ).exclude(notification_type="message").count()

    messages_count = request.user.notifications.filter(
        is_read=False,
        notification_type="message"
    ).count()

    return JsonResponse({
        "notifications_count": notifications_count,
        "messages_count": messages_count,
    })

def get_lesson_receiver(lesson, user):
    if lesson.teacher == user:
        return lesson.student

    if lesson.student == user:
        return lesson.teacher

    return None


def get_or_create_lesson_conversation(lesson):
    conversation, created = Conversation.objects.get_or_create(
        teacher=lesson.teacher,
        student=lesson.student
    )
    return conversation

@login_required
def request_lesson_reschedule(request, lesson_id):
    lesson = get_object_or_404(CalendarEvent, id=lesson_id)

    if request.user != lesson.teacher and request.user != lesson.student:
        return redirect("dashboard")

    receiver = get_lesson_receiver(lesson, request.user)

    if not receiver:
        messages.error(request, "Не вдалося знайти учасника уроку.")
        return redirect("lesson_detail", lesson_id=lesson.id)

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        comment = request.POST.get("comment", "").strip()
        new_date = request.POST.get("new_date", "").strip()
        new_time = request.POST.get("new_time", "").strip()

        if not reason or not new_date or not new_time:
            messages.error(request, "Заповни причину, дату і час.")
            return redirect("lesson_detail", lesson_id=lesson.id)

        proposed_start = datetime.strptime(
            f"{new_date} {new_time}",
            "%Y-%m-%d %H:%M"
        )
        proposed_start = timezone.make_aware(proposed_start)

        if lesson.end_time:
            duration = lesson.end_time - lesson.start_time
        else:
            duration = timedelta(minutes=60)

        proposed_end = proposed_start + duration

        conversation = get_or_create_lesson_conversation(lesson)

        change_request = LessonChangeRequest.objects.create(
            lesson=lesson,
            conversation=conversation,
            requested_by=request.user,
            request_type="reschedule",
            status="pending",
            reason=reason,
            comment=comment,
            old_start_time=lesson.start_time,
            old_end_time=lesson.end_time,
            proposed_start_time=proposed_start,
            proposed_end_time=proposed_end,
        )

        text = (
            f" Запит на перенесення уроку\n\n"
            f"Урок: {lesson.title}\n"
            f"Було: {lesson.start_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"Запропоновано: {proposed_start.strftime('%d.%m.%Y %H:%M')}\n"
            f"Причина: {reason}"
        )

        if comment:
            text += f"\nКоментар: {comment}"

        message = ChatMessage.objects.create(
            conversation=conversation,
            sender=request.user,
            text=text,
            message_type="lesson_reschedule_request",
            lesson=lesson,
            change_request=change_request
        )

        conversation.updated_at = message.created_at
        conversation.save(update_fields=["updated_at"])

        Notification.objects.create(
            user=receiver,
            title="Запит на перенесення уроку",
            message=f"{request.user.first_name} просить перенести урок",
            notification_type="message",
            link=f"/messages/{conversation.id}/"
        )

        messages.success(request, "Запит на перенесення надіслано у чат.")
        return redirect("chat_detail", conversation_id=conversation.id)

    return redirect("lesson_detail", lesson_id=lesson.id)

@login_required
def cancel_lesson_request(request, lesson_id):
    lesson = get_object_or_404(CalendarEvent, id=lesson_id)

    if request.user != lesson.teacher and request.user != lesson.student:
        return redirect("dashboard")

    receiver = get_lesson_receiver(lesson, request.user)

    if not receiver:
        messages.error(request, "Не вдалося знайти учасника уроку.")
        return redirect("lesson_detail", lesson_id=lesson.id)

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        comment = request.POST.get("comment", "").strip()

        if not reason:
            messages.error(request, "Вкажи причину скасування.")
            return redirect("lesson_detail", lesson_id=lesson.id)

        conversation = get_or_create_lesson_conversation(lesson)

        lesson.is_cancelled = True
        lesson.save(update_fields=["is_cancelled"])

        change_request = LessonChangeRequest.objects.create(
            lesson=lesson,
            conversation=conversation,
            requested_by=request.user,
            request_type="cancel",
            status="cancelled",
            reason=reason,
            comment=comment,
            old_start_time=lesson.start_time,
            old_end_time=lesson.end_time,
        )

        text = (
            f" Урок скасовано\n\n"
            f"Урок: {lesson.title}\n"
            f"Дата: {lesson.start_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"Причина: {reason}"
        )

        if comment:
            text += f"\nКоментар: {comment}"

        message = ChatMessage.objects.create(
            conversation=conversation,
            sender=request.user,
            text=text,
            message_type="lesson_cancelled",
            lesson=lesson,
            change_request=change_request
        )

        conversation.updated_at = message.created_at
        conversation.save(update_fields=["updated_at"])

        Notification.objects.create(
            user=receiver,
            title="Урок скасовано",
            message=f"{request.user.first_name} скасував(ла) урок",
            notification_type="message",
            link=f"/messages/{conversation.id}/"
        )

        messages.success(request, "Урок скасовано, повідомлення надіслано у чат.")
        return redirect("chat_detail", conversation_id=conversation.id)

    return redirect("lesson_detail", lesson_id=lesson.id)

@login_required
def accept_reschedule_request(request, request_id):
    change_request = get_object_or_404(LessonChangeRequest, id=request_id)
    lesson = change_request.lesson
    conversation = change_request.conversation

    if request.user not in [lesson.teacher, lesson.student]:
        return redirect("dashboard")

    if request.user == change_request.requested_by:
        messages.error(request, "Ти не можеш прийняти власний запит.")
        return redirect("chat", conversation_id=conversation.id)

    if change_request.status != "pending":
        messages.error(request, "Цей запит вже неактивний.")
        return redirect("chat", conversation_id=conversation.id)

    lesson.start_time = change_request.proposed_start_time
    lesson.end_time = change_request.proposed_end_time
    lesson.is_cancelled = False
    lesson.save(update_fields=["start_time", "end_time", "is_cancelled"])

    change_request.status = "accepted"
    change_request.responded_by = request.user
    change_request.responded_at = timezone.now()
    change_request.save()

    receiver = change_request.requested_by

    text = (
        f" Перенесення уроку підтверджено\n\n"
        f"Урок: {lesson.title}\n"
        f"Новий час: {lesson.start_time.strftime('%d.%m.%Y %H:%M')}"
    )

    message = ChatMessage.objects.create(
        conversation=conversation,
        sender=request.user,
        text=text,
        message_type="lesson_reschedule_accepted",
        lesson=lesson,
        change_request=change_request
    )

    conversation.updated_at = message.created_at
    conversation.save(update_fields=["updated_at"])

    Notification.objects.create(
        user=receiver,
        title="Перенесення підтверджено",
        message=f"{request.user.first_name} підтвердив(ла) новий час уроку",
        notification_type="message",
        link=f"/messages/{conversation.id}/"
    )

    messages.success(request, "Урок перенесено.")
    return redirect("chat_detail", conversation_id=conversation.id)

@login_required
def decline_reschedule_request(request, request_id):
    change_request = get_object_or_404(LessonChangeRequest, id=request_id)
    lesson = change_request.lesson
    conversation = change_request.conversation

    if request.user not in [lesson.teacher, lesson.student]:
        return redirect("dashboard")

    if request.user == change_request.requested_by:
        messages.error(request, "Ти не можеш відхилити власний запит.")
        return redirect("chat", conversation_id=conversation.id)

    if request.method == "POST":
        comment = request.POST.get("comment", "").strip()

        change_request.status = "declined"
        change_request.responded_by = request.user
        change_request.responded_at = timezone.now()
        change_request.save()

        receiver = change_request.requested_by

        text = f"Запит на перенесення уроку відхилено\n\nУрок: {lesson.title}"

        if comment:
            text += f"\nКоментар: {comment}"

        message = ChatMessage.objects.create(
            conversation=conversation,
            sender=request.user,
            text=text,
            message_type="lesson_reschedule_declined",
            lesson=lesson,
            change_request=change_request
        )

        conversation.updated_at = message.created_at
        conversation.save(update_fields=["updated_at"])

        Notification.objects.create(
            user=receiver,
            title="Перенесення відхилено",
            message=f"{request.user.first_name} відхилив(ла) перенесення уроку",
            notification_type="message",
            link=f"/messages/{conversation.id}/"
        )

        messages.success(request, "Запит відхилено.")
        return redirect("chat_detail", conversation_id=conversation.id)

    return redirect("chat_detail", conversation_id=conversation.id)

@login_required
def counter_reschedule_request(request, request_id):
    old_request = get_object_or_404(LessonChangeRequest, id=request_id)
    lesson = old_request.lesson
    conversation = old_request.conversation

    if request.user not in [lesson.teacher, lesson.student]:
        return redirect("dashboard")

    if request.user == old_request.requested_by:
        messages.error(request, "Ти не можеш відповісти на власний запит.")
        return redirect("chat", conversation_id=conversation.id)

    if request.method == "POST":
        new_date = request.POST.get("new_date", "").strip()
        new_time = request.POST.get("new_time", "").strip()
        comment = request.POST.get("comment", "").strip()

        if not new_date or not new_time:
            messages.error(request, "Вкажи нову дату і час.")
            return redirect("chat", conversation_id=conversation.id)

        proposed_start = datetime.strptime(
            f"{new_date} {new_time}",
            "%Y-%m-%d %H:%M"
        )
        proposed_start = timezone.make_aware(proposed_start)

        if lesson.end_time:
            duration = lesson.end_time - lesson.start_time
        else:
            duration = timedelta(minutes=60)

        proposed_end = proposed_start + duration

        old_request.status = "countered"
        old_request.responded_by = request.user
        old_request.responded_at = timezone.now()
        old_request.save()

        new_request = LessonChangeRequest.objects.create(
            lesson=lesson,
            conversation=conversation,
            requested_by=request.user,
            request_type="reschedule",
            status="pending",
            reason="Запропоновано інший час",
            comment=comment,
            old_start_time=lesson.start_time,
            old_end_time=lesson.end_time,
            proposed_start_time=proposed_start,
            proposed_end_time=proposed_end,
        )

        receiver = old_request.requested_by

        text = (
            f" Запропоновано інший час для уроку\n\n"
            f"Урок: {lesson.title}\n"
            f"Новий час: {proposed_start.strftime('%d.%m.%Y %H:%M')}"
        )

        if comment:
            text += f"\nКоментар: {comment}"

        message = ChatMessage.objects.create(
            conversation=conversation,
            sender=request.user,
            text=text,
            message_type="lesson_reschedule_counter",
            lesson=lesson,
            change_request=new_request
        )

        conversation.updated_at = message.created_at
        conversation.save(update_fields=["updated_at"])

        Notification.objects.create(
            user=receiver,
            title="Запропоновано інший час",
            message=f"{request.user.first_name} запропонував(ла) інший час уроку",
            notification_type="message",
            link=f"/messages/{conversation.id}/"
        )

        messages.success(request, "Новий час надіслано у чат.")
        return redirect("chat_detail", conversation_id=conversation.id)

    return redirect("chat_detail", conversation_id=conversation.id)@login_required
def counter_reschedule_request(request, request_id):
    old_request = get_object_or_404(LessonChangeRequest, id=request_id)
    lesson = old_request.lesson
    conversation = old_request.conversation

    if request.user not in [lesson.teacher, lesson.student]:
        return redirect("dashboard")

    if request.user == old_request.requested_by:
        messages.error(request, "Ти не можеш відповісти на власний запит.")
        return redirect("chat", conversation_id=conversation.id)

    if request.method == "POST":
        new_date = request.POST.get("new_date", "").strip()
        new_time = request.POST.get("new_time", "").strip()
        comment = request.POST.get("comment", "").strip()

        if not new_date or not new_time:
            messages.error(request, "Вкажи нову дату і час.")
            return redirect("chat", conversation_id=conversation.id)

        proposed_start = datetime.strptime(
            f"{new_date} {new_time}",
            "%Y-%m-%d %H:%M"
        )
        proposed_start = timezone.make_aware(proposed_start)

        if lesson.end_time:
            duration = lesson.end_time - lesson.start_time
        else:
            duration = timedelta(minutes=60)

        proposed_end = proposed_start + duration

        old_request.status = "countered"
        old_request.responded_by = request.user
        old_request.responded_at = timezone.now()
        old_request.save()

        new_request = LessonChangeRequest.objects.create(
            lesson=lesson,
            conversation=conversation,
            requested_by=request.user,
            request_type="reschedule",
            status="pending",
            reason="Запропоновано інший час",
            comment=comment,
            old_start_time=lesson.start_time,
            old_end_time=lesson.end_time,
            proposed_start_time=proposed_start,
            proposed_end_time=proposed_end,
        )

        receiver = old_request.requested_by

        text = (
            f" Запропоновано інший час для уроку\n\n"
            f"Урок: {lesson.title}\n"
            f"Новий час: {proposed_start.strftime('%d.%m.%Y %H:%M')}"
        )

        if comment:
            text += f"\nКоментар: {comment}"

        message = ChatMessage.objects.create(
            conversation=conversation,
            sender=request.user,
            text=text,
            message_type="lesson_reschedule_counter",
            lesson=lesson,
            change_request=new_request
        )

        conversation.updated_at = message.created_at
        conversation.save(update_fields=["updated_at"])

        Notification.objects.create(
            user=receiver,
            title="Запропоновано інший час",
            message=f"{request.user.first_name} запропонував(ла) інший час уроку",
            notification_type="message",
            link=f"/messages/{conversation.id}/"
        )

        messages.success(request, "Новий час надіслано у чат.")
        return redirect("chat_detail", conversation_id=conversation.id)

    return redirect("chat_detail", conversation_id=conversation.id)