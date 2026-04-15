from django.contrib import admin


from .models import TeacherProfile, StudentProfile, StudentTeacherLink


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "access_code")


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user",)


@admin.register(StudentTeacherLink)
class StudentTeacherLinkAdmin(admin.ModelAdmin):
    list_display = ("student", "teacher", "created_at")
