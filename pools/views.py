from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from .forms import MembershipForm, PoolForm, PricingTierForm, ServiceForm
from .models import Pool, PoolMembership, PricingTier, Service

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


# =====================================================================
# Pool booking (core feature)
# =====================================================================
client_only = role_required(User.ROLE_CLIENT)


def _membership(pool, user):
    return pool.memberships.filter(client=user).first()


def _can_view_pool(user, pool):
    if user.role == User.ROLE_ADMIN:
        return True
    if user.role == User.ROLE_PROVIDER:
        return pool.service.provider_id == user.pk
    if user.role == User.ROLE_CLIENT:
        return pool.is_open or pool.memberships.filter(client=user).exists()
    return False


# ---------- Client: browse / my pools ----------
@client_only
def pool_list(request):
    """Open pools on published services that the client can join."""
    pools = Pool.objects.filter(status=Pool.STATUS_OPEN, service__is_published=True).select_related("service")
    q = request.GET.get("q", "").strip()
    if q:
        pools = pools.filter(Q(title__icontains=q) | Q(location__icontains=q) | Q(service__title__icontains=q)
                             | Q(service__service_area__icontains=q))
    joined_ids = set(request.user.pool_memberships.values_list("pool_id", flat=True))
    return render(request, "pools/pool_list.html", {"pools": pools, "q": q, "joined_ids": joined_ids})


@client_only
def my_pools(request):
    memberships = (request.user.pool_memberships.select_related("pool", "pool__service")
                   .order_by("pool__scheduled_date"))
    return render(request, "pools/my_pools.html", {"memberships": memberships})


# ---------- Client: create / read / update / delete a pool ----------
@client_only
def pool_create(request):
    form = PoolForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            with transaction.atomic():
                pool = form.save(commit=False)
                pool.created_by = request.user
                pool.save()
                PoolMembership.objects.create(
                    pool=pool, client=request.user,
                    business_name=form.cleaned_data["business_name"], area_sqm=form.cleaned_data["area_sqm"],
                )
            messages.success(request, "Pool created. Other businesses can now join it.")
            return redirect("pools:pool_detail", pk=pool.pk)
        messages.error(request, "Please correct the errors below.")
    return render(request, "pools/pool_form.html", {"form": form, "heading": "Start a new pool"})


@login_required
def pool_detail(request, pk):
    pool = get_object_or_404(Pool.objects.select_related("service", "created_by"), pk=pk)
    user = request.user
    if not _can_view_pool(user, pool):
        raise PermissionDenied
    mine = _membership(pool, user) if user.role == User.ROLE_CLIENT else None
    can_join = user.role == User.ROLE_CLIENT and mine is None and pool.is_open and not pool.is_full
    ctx = {
        "pool": pool, "mine": mine, "can_join": can_join,
        "join_form": MembershipForm() if can_join else None,
        "members": pool.memberships.select_related("client"),
        "tiers": pool.service.tiers.all(),
        "is_owner": pool.created_by_id == user.pk,
        "can_see_members": user.role != User.ROLE_CLIENT or mine is not None,
        "can_confirm": pool.is_open and pool.participant_count >= Pool.MIN_TO_CONFIRM,
    }
    return render(request, "pools/pool_detail.html", ctx)


@client_only
def pool_edit(request, pk):
    pool = get_object_or_404(Pool, pk=pk, created_by=request.user)
    if not pool.is_open:
        messages.error(request, "Only open pools can be edited.")
        return redirect("pools:pool_detail", pk=pool.pk)
    form = PoolForm(request.POST or None, instance=pool)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Pool updated.")
            return redirect("pools:pool_detail", pk=pool.pk)
        messages.error(request, "Please correct the errors below.")
    return render(request, "pools/pool_form.html", {"form": form, "heading": "Edit pool"})


@require_POST
@client_only
def pool_cancel(request, pk):
    pool = get_object_or_404(Pool, pk=pk, created_by=request.user)
    if not pool.is_open:
        messages.error(request, "Only open pools can be cancelled.")
    else:
        pool.status = Pool.STATUS_CANCELLED
        pool.save(update_fields=["status", "updated_at"])
        messages.success(request, "Pool cancelled.")
    return redirect("pools:pool_detail", pk=pool.pk)


@client_only
def pool_delete(request, pk):
    pool = get_object_or_404(Pool, pk=pk, created_by=request.user)
    if pool.status not in (Pool.STATUS_OPEN, Pool.STATUS_CANCELLED) or pool.participant_count > 1:
        messages.error(request, "This pool cannot be deleted because other businesses joined or it is already confirmed. Cancel it instead.")
        return redirect("pools:pool_detail", pk=pool.pk)
    if request.method == "POST":
        pool.delete()
        messages.success(request, "Pool deleted.")
        return redirect("pools:my_pools")
    return render(request, "pools/confirm_delete.html", {"obj": pool, "what": "pool", "back": "pools:pool_detail"})


# ---------- Client: join / update share / leave ----------
@require_POST
@client_only
def pool_join(request, pk):
    with transaction.atomic():
        pool = get_object_or_404(Pool.objects.select_for_update(), pk=pk)
        if not pool.is_open:
            messages.error(request, "This pool is no longer open.")
        elif pool.memberships.filter(client=request.user).exists():
            messages.error(request, "You already joined this pool.")
        elif pool.is_full:
            messages.error(request, "This pool is full.")
        else:
            form = MembershipForm(request.POST)
            if form.is_valid():
                m = form.save(commit=False)
                m.pool, m.client = pool, request.user
                m.save()
                messages.success(request, f"You joined the pool. Current rate: ₱{pool.rate_per_sqm}/sqm.")
            else:
                for errs in form.errors.values():
                    for e in errs:
                        messages.error(request, e)
    return redirect("pools:pool_detail", pk=pk)


@client_only
def membership_edit(request, pk):
    m = get_object_or_404(PoolMembership.objects.select_related("pool"), pk=pk, client=request.user)
    if not m.pool.is_open:
        messages.error(request, "You can only change your share while the pool is open.")
        return redirect("pools:pool_detail", pk=m.pool_id)
    form = MembershipForm(request.POST or None, instance=m)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Your share was updated.")
            return redirect("pools:pool_detail", pk=m.pool_id)
        messages.error(request, "Please correct the errors below.")
    return render(request, "pools/membership_form.html", {"form": form, "pool": m.pool})


@require_POST
@client_only
def membership_leave(request, pk):
    m = get_object_or_404(PoolMembership.objects.select_related("pool"), pk=pk, client=request.user)
    if m.is_creator:
        messages.error(request, "You created this pool. Cancel or delete it instead of leaving.")
    elif not m.pool.is_open:
        messages.error(request, "You can only leave while the pool is open.")
    else:
        m.delete()
        messages.success(request, "You left the pool.")
        return redirect("pools:my_pools")
    return redirect("pools:pool_detail", pk=m.pool_id)


# ---------- Provider: handle pools on own services ----------
@provider_only
def provider_pools(request):
    pools = Pool.objects.filter(service__provider=request.user).select_related("service")
    status = request.GET.get("status", "")
    if status in dict(Pool.STATUS_CHOICES):
        pools = pools.filter(status=status)
    return render(request, "pools/provider_pools.html",
                  {"pools": pools, "status": status, "status_choices": Pool.STATUS_CHOICES})


@require_POST
@login_required
def pool_action(request, pk, action):
    """Status changes: provider confirm/decline/complete own pools; admin may cancel any pool."""
    pool = get_object_or_404(Pool, pk=pk)
    user = request.user
    if user.role == User.ROLE_PROVIDER and pool.service.provider_id == user.pk:
        allowed = {"confirm", "decline", "complete"}
    elif user.role == User.ROLE_ADMIN:
        allowed = {"cancel"}
    else:
        raise PermissionDenied
    if action not in allowed:
        raise PermissionDenied

    if action == "confirm":
        if not pool.is_open:
            messages.error(request, "Only open pools can be confirmed.")
        elif pool.participant_count < Pool.MIN_TO_CONFIRM:
            messages.error(request, f"A pool needs at least {Pool.MIN_TO_CONFIRM} businesses before it can be confirmed.")
        else:
            pool.status = Pool.STATUS_CONFIRMED
            messages.success(request, "Pool confirmed. Members can no longer change their shares.")
    elif action == "complete":
        if pool.status != Pool.STATUS_CONFIRMED:
            messages.error(request, "Only confirmed pools can be marked completed.")
        else:
            pool.status = Pool.STATUS_COMPLETED
            messages.success(request, "Pool marked as completed.")
    else:  # decline / cancel
        if pool.status not in (Pool.STATUS_OPEN, Pool.STATUS_CONFIRMED):
            messages.error(request, "This pool can no longer be cancelled.")
        else:
            pool.status = Pool.STATUS_CANCELLED
            messages.success(request, "Pool cancelled.")
    pool.save(update_fields=["status", "updated_at"])
    if user.role == User.ROLE_ADMIN:
        return redirect("pools:admin_pools")
    return redirect("pools:pool_detail", pk=pool.pk)


# ---------- Admin: oversight ----------
@role_required(User.ROLE_ADMIN)
def admin_pools(request):
    pools = Pool.objects.select_related("service", "created_by", "service__provider")
    status = request.GET.get("status", "")
    if status in dict(Pool.STATUS_CHOICES):
        pools = pools.filter(status=status)
    return render(request, "pools/admin_pools.html",
                  {"pools": pools, "status": status, "status_choices": Pool.STATUS_CHOICES})
