from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import JoinTeacherByCodeForm, TeacherProfileEditForm
from .models import TeacherProfile, StudentTeacherLink, CalendarEvent, StudentProfile,Homework, HomeworkMaterial,HomeworkSubmission,HomeworkSubmissionFile
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
import calendar
from datetime import date, datetime, timedelta
import locale
import random
import string
from django.contrib.auth import get_user_model
from django.http import JsonResponse

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
    today = now.date()

    today_lessons = CalendarEvent.objects.filter(
        teacher=user,
        start_time__date=today,
        event_type="lesson"
    ).select_related("student").order_by("start_time")

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
            "homework": lesson.description or "",
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

                if is_edit:
                    lesson.title = form_data["topic"]
                    lesson.event_type = "lesson"
                    lesson.description = form_data["homework"] or ""
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
                        description=form_data["homework"] or "",
                        start_time=start_dt,
                        end_time=end_dt,
                        teacher=request.user,
                        student=selected_student.user,
                    )

                    # messages.success(request, "Урок успішно створено.")
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

    return render(request, "core/lesson_detail.html", {
        "lesson": lesson,
        "is_teacher": is_teacher,
        "is_student": is_student,
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

            if not comment:
                messages.error(request, "Напиши коментар перед перевіркою.")
                return redirect("homework_detail", pk=homework.pk)

            submission.teacher_comment = comment
            submission.checked_at = timezone.now()
            submission.save()

            homework.teacher_comment = comment
            homework.checked_at = timezone.now()

            if result == "checked":
                homework.status = "checked"

            homework.save()

            messages.success(request, "Результат перевірки збережено.")
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
        messages.success(request, "Домашнє завдання видалено.")
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