from django.urls import path
from .views import (
    InscriptionView,
    VerifyAccountView,
    ResendVerificationCodeView,
    LoginView,
    TokenRefreshView,
    UserListView,
    CreatePriviligeView,
    UserRetrieveUpdateDestroyView,
    UserRetrieveUpdateDestroyView,
    LogoutView,
    UserActivityListView,
    ExportUserActivityView,PasswordResetRequestView,PasswordResetConfirmView,
)

urlpatterns = [
    path("user/register/", InscriptionView.as_view(), name="register"),
    path("admin/create-privilege/", CreatePriviligeView.as_view(), name="create-privilege"),
    path("user/login/", LoginView.as_view(), name="login"),
    path("user/verify/", VerifyAccountView.as_view(), name="verify-account"),
    path("user/resend-code/", ResendVerificationCodeView.as_view(), name="resend-code"),
    path("user/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("admin/list/", UserListView.as_view(), name="user-list"),
    path("me/", UserRetrieveUpdateDestroyView.as_view(), name="user-me"),
    path(
        "admin/users/<int:pk>/",
        UserRetrieveUpdateDestroyView.as_view(),
        name="admin-user-management",
    ),
    path("user/logout/", LogoutView.as_view(), name="logout"),
    path(
        "admin/users/activities/", UserActivityListView.as_view(), name="user-activities"
    ),
    path(
        "admin/users/activities/export/", ExportUserActivityView.as_view(), name="user-activities"
    ),
    path('password/reset/', PasswordResetRequestView.as_view(), name='password-reset'),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
]
