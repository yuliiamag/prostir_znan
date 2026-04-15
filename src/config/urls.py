from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("core.urls")),
    path(
            "accounts/email-confirmed/",
            TemplateView.as_view(template_name="account/email_confirmed.html"),
            name="email_confirmed",
        ),

]