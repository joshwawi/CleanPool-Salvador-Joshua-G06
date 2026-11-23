from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from .forms import PricingTierForm, ServiceForm
from .models import PricingTier, Service

provider_only = role_required(User.ROLE_PROVIDER)


def _own_service(request, pk):
    """Providers can only touch their own services (404 for anyone else's)."""
    return get_object_or_404(Service, pk=pk, provider=request.user)


# ---------- Provider: services ----------
@provider_only
def service_list(request):
    services = Service.objects.filter(provider=request.user).prefetch_related("tiers")
    return render(request, "pools/service_list.html", {"services": services})


@provider_only
def service_create(request):
    form = ServiceForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            service = form.save(commit=False)
            service.provider = request.user
            service.save()
            messages.success(request, "Service created. Add pricing tiers to offer volume discounts.")
            return redirect("pools:service_detail", pk=service.pk)
        messages.error(request, "Please correct the errors below.")
    return render(request, "pools/service_form.html", {"form": form, "heading": "New service"})


@provider_only
def service_detail(request, pk):
    service = _own_service(request, pk)
    ctx = {"service": service, "tiers": service.tiers.all(), "tier_form": PricingTierForm(service=service)}
    return render(request, "pools/service_detail.html", ctx)


@provider_only
def service_edit(request, pk):
    service = _own_service(request, pk)
    form = ServiceForm(request.POST or None, instance=service)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Service updated.")
            return redirect("pools:service_detail", pk=service.pk)
        messages.error(request, "Please correct the errors below.")
    return render(request, "pools/service_form.html", {"form": form, "heading": "Edit service"})


@provider_only
def service_delete(request, pk):
    service = _own_service(request, pk)
    if request.method == "POST":
        service.delete()
        messages.success(request, "Service deleted.")
        return redirect("pools:service_list")
    return render(request, "pools/confirm_delete.html", {"obj": service, "what": "service", "back": "pools:service_detail"})


# ---------- Provider: pricing tiers ----------
@require_POST
@provider_only
def tier_add(request, pk):
    service = _own_service(request, pk)
    form = PricingTierForm(request.POST, service=service)
    if form.is_valid():
        tier = form.save(commit=False)
        tier.service = service
        tier.save()
        messages.success(request, "Pricing tier added.")
    else:
        for errs in form.errors.values():
            for e in errs:
                messages.error(request, e)
    return redirect("pools:service_detail", pk=service.pk)


@require_POST
@provider_only
def tier_delete(request, pk):
    tier = get_object_or_404(PricingTier, pk=pk, service__provider=request.user)
    service_pk = tier.service_id
    tier.delete()
    messages.success(request, "Pricing tier removed.")
    return redirect("pools:service_detail", pk=service_pk)
