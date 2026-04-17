from django import forms
from django.contrib.auth import get_user_model

from .models import (
    TeacherProfile,
    StudentProfile,
    StudentTeacherLink,
    generate_unique_access_code,
)

User = get_user_model()


class CustomSignupForm(forms.Form):
    ROLE_CHOICES = (
        ("student", "Я учень"),
        ("teacher", "Я вчитель"),
    )

    first_name = forms.CharField(
        max_length=150,
        label="Ім’я",
        widget=forms.TextInput(attrs={"placeholder": "Ім’я"}),
    )
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        label="Роль",
        widget=forms.Select(),
    )

    def signup(self, request, user):
        user.first_name = self.cleaned_data["first_name"]
        user.save()

        role = self.cleaned_data["role"]

        if role == "teacher":
            TeacherProfile.objects.create(
                user=user,
                access_code=generate_unique_access_code(),
            )
        else:
            StudentProfile.objects.create(user=user)


class JoinTeacherByCodeForm(forms.Form):
    access_code = forms.CharField(
        max_length=20,
        label="Код доступу",
        widget=forms.TextInput(attrs={"placeholder": "Введіть код вчителя"}),
    )

    def __init__(self, *args, **kwargs):
        self.student_profile = kwargs.pop("student_profile")
        super().__init__(*args, **kwargs)

    def clean_access_code(self):
        code = self.cleaned_data["access_code"].strip().upper()

        try:
            teacher = TeacherProfile.objects.get(access_code=code)
        except TeacherProfile.DoesNotExist:
            raise forms.ValidationError("Такого коду доступу не існує.")

        if StudentTeacherLink.objects.filter(
            student=self.student_profile,
            teacher=teacher,
        ).exists():
            raise forms.ValidationError("Цей вчитель уже доданий.")

        self.teacher = teacher
        return code

    def save(self):
        return StudentTeacherLink.objects.create(
            student=self.student_profile,
            teacher=self.teacher,
        )


class TeacherProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        labels = {
            "first_name": "Ім’я",
            "last_name": "Прізвище",
            "email": "Email",
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-input"}),
            "last_name": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
        }