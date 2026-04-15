from django.urls import path
from . import views
from .views import (
    dashboard_view,
    student_dashboard_view,
    teacher_dashboard_view,
)
urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("teachers/", views.teachers, name="teachers"),
    path("dashboard/student/", student_dashboard_view, name="student_dashboard"),
    path("dashboard/teacher/", teacher_dashboard_view, name="teacher_dashboard"),
]


