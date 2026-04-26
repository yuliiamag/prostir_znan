from django.urls import path
from . import views
from .views import (
    dashboard_view,
    student_dashboard_view,

)
urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("teachers/", views.teachers, name="teachers"),
    path("dashboard/student/", student_dashboard_view, name="student_dashboard"),
    path("teacher/", views.teacher_dashboard, name="teacher_dashboard"),
    path("calendar/", views.calendar_view, name="calendar"),
    path("teacher/profile/", views.teacher_profile, name="teacher_profile"),
    path("lesson/new/", views.create_lesson, name="create_lesson"),
    path("lessons/", views.lessons_view, name="lessons"),
    path("calendar/<int:year>/<int:month>/<int:day>/", views.calendar_day_view, name="calendar_day"),
    path("teacher/add-student/", views.add_student_manual, name="add_student_manual"),
    path("teacher/generate-code/", views.generate_teacher_code, name="generate_teacher_code"),
    path("lesson/<int:lesson_id>/", views.lesson_detail, name="lesson_detail"),
    path("lesson/<int:lesson_id>/edit/", views.create_lesson, name="edit_lesson"),
    path("student/profile/", views.student_profile, name="student_profile"),
]


