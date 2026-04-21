from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import JoinTeacherByCodeForm, TeacherProfileEditForm
from .models import TeacherProfile, StudentTeacherLink
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
import calendar
from datetime import date
import locale
from .models import CalendarEvent

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
