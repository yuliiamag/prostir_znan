from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .forms import JoinTeacherByCodeForm
from .models import StudentProfile, TeacherProfile


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
def teacher_dashboard_view(request):
    user = request.user

    if not hasattr(user, "teacher_profile"):
        messages.error(request, "Ця сторінка доступна тільки для вчителя.")
        return redirect("dashboard")

    teacher_profile = user.teacher_profile
    student_links = teacher_profile.student_links.select_related("student__user")

    return render(
        request,
        "core/teacher_dashboard.html",
        {
            "teacher_profile": teacher_profile,
            "student_links": student_links,
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