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
    path("teacher/edit/", views.edit_teacher_profile, name="edit_teacher_profile"),
    path("calendar/", views.calendar_view, name="calendar"),

]


