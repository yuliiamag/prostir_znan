from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import JoinTeacherByCodeForm, TeacherProfileEditForm
from .models import TeacherProfile, StudentTeacherLink
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
import calendar
from datetime import date, datetime, timedelta
import locale
from .models import CalendarEvent, StudentProfile

def home(request):
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
    current_date = f"{DAYS[now.weekday()]}, {now.day} {MONTHS[now.month]} {now.year}"

    return render(
        request,
        "core/teacher_dashboard.html",
        {
            "teacher_profile": teacher_profile,
            "student_links": student_links,
            "current_date": current_date,
        },
    )


@login_required
def student_dashboard_view(request):
    user = request.user

    if not hasattr(user, "student_profile"):
        messages.error(request, "Ця сторінка доступна тільки для учня.")
        return redirect("dashboard")

    student_profile = user.student_profile

    if request.method == "POST":
        form = JoinTeacherByCodeForm(request.POST, student_profile=student_profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Вчителя успішно додано.")
            return redirect("student_dashboard")
    else:
        form = JoinTeacherByCodeForm(student_profile=student_profile)

    teacher_links = student_profile.teacher_links.select_related("teacher__user")

    return render(
        request,
        "core/student_dashboard.html",
        {
            "form": form,
            "teacher_links": teacher_links,
        },
    )


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

    month_days = []
    for week in raw_month_days:
        week_data = []
        for day in week:
            week_data.append({
                "day": day,
                "events": events_by_day.get(day, []) if day != 0 else [],
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
def create_lesson(request):
    teacher_profile = TeacherProfile.objects.filter(user=request.user).first()

    if not teacher_profile:
        messages.error(request, "Профіль вчителя не знайдено.")
        return redirect("teacher_dashboard")

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

    form_data = {
        "student_id": "",
        "topic": "",
        "lesson_date": "",
        "lesson_time": "",
        "duration": "30",
        "custom_duration": "",
        "repeat_days": [],
        "homework": "",
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
        form_data["homework"] = request.POST.get("homework", "").strip()
        form_data["homework_deadline"] = request.POST.get("homework_deadline", "")
        form_data["delivery_method"] = request.POST.get("delivery_method", "Текст у платформі")
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

        selected_student = student_profiles.filter(id=form_data["student_id"]).first()

        if not selected_student and form_data["student_id"]:
            errors.append("Обраного учня не знайдено.")

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
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

            CalendarEvent.objects.create(
                title=form_data["topic"],
                event_type="lesson",
                description=form_data["homework"] or "",
                start_time=start_dt,
                end_time=end_dt,
                teacher=request.user,
                student=selected_student.user,
            )

            messages.success(request, "Урок успішно створено.")
            return redirect("teacher_dashboard")

    context = {
        "students": student_profiles,
        "durations": durations,
        "weekdays": weekdays,
        "delivery_methods": delivery_methods,
        "form_data": form_data,
        "selected_student": None,
        "duration_text": "30 хв",
        "repeat_days_labels": [],
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
def calendar_day_view(request, year, month, day):
    selected_date = date(year, month, day)

    events = CalendarEvent.objects.filter(
        Q(teacher=request.user) | Q(student=request.user),
        start_time__date=selected_date
    ).order_by("start_time")

    return render(request, "core/calendar_day.html", {
        "selected_date": selected_date,
        "events": events,
    })