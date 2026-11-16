from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import role_required
from .forms import LoginForm, ProfileForm, RegistrationForm
from .models import User

ROLE_HOME = {
    User.ROLE_CLIENT: "accounts:client_dashboard",
    User.ROLE_PROVIDER: "accounts:provider_dashboard",
    User.ROLE_ADMIN: "accounts:admin_dashboard",
}


def register_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Account created successfully! You can now log in.")
            return redirect("accounts:login")
        messages.error(request, "Please correct the errors below.")
    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        password = form.cleaned_data["password"]
        target = User.objects.filter(email__iexact=email).first()

        if target and target.is_locked:  # BR-03
            mins = int((target.locked_until - timezone.now()).total_seconds() // 60) + 1
            messages.error(request, f"Account locked due to too many failed attempts. Try again in {mins} minute(s).")
        elif target and target.is_suspended:  # BR-04
            messages.error(request, "Your account has been suspended. Please contact an administrator.")
        else:
            user = authenticate(request, username=email, password=password)
            if user is not None:
                user.failed_login_count = 0
                user.locked_until = None
                user.save(update_fields=["failed_login_count", "locked_until"])
                login(request, user)
                messages.success(request, f"Welcome back, {user.full_name}!")
                next_url = request.GET.get("next", "")
                if next_url.startswith("/") and not next_url.startswith("//"):
                    return redirect(next_url)
                return redirect("accounts:dashboard")
            if target:
                target.failed_login_count += 1
                if target.failed_login_count >= settings.MAX_FAILED_LOGINS:
                    target.locked_until = timezone.now() + timedelta(minutes=settings.LOCKOUT_MINUTES)
                    target.failed_login_count = 0
                target.save(update_fields=["failed_login_count", "locked_until"])
            messages.error(request, "Invalid email or password.")
    return render(request, "accounts/login.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("accounts:login")


@login_required
def dashboard_redirect(request):
    """Send each user to the dashboard for their role."""
    return redirect(ROLE_HOME[request.user.role])


@role_required(User.ROLE_CLIENT)
def client_dashboard(request):
    return render(request, "accounts/dashboard_client.html")


@role_required(User.ROLE_PROVIDER)
def provider_dashboard(request):
    return render(request, "accounts/dashboard_provider.html")


@role_required(User.ROLE_ADMIN)
def admin_dashboard(request):
    ctx = {
        "total_users": User.objects.count(),
        "client_count": User.objects.filter(role=User.ROLE_CLIENT).count(),
        "provider_count": User.objects.filter(role=User.ROLE_PROVIDER).count(),
        "recent_users": User.objects.order_by("-created_at")[:10],
    }
    return render(request, "accounts/dashboard_admin.html", ctx)


@login_required
def profile_view(request):
    return render(request, "accounts/profile.html", {"profile_user": request.user})


@login_required
def profile_edit(request):
    # Always the logged-in user's own record; no user id in the URL.
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("accounts:profile")
        messages.error(request, "Please correct the errors below.")
    return render(request, "accounts/profile_edit.html", {"form": form})
