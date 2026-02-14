from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import models
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .forms import ListingForm, ListingReportForm, LoginForm, ProfileForm, SignUpForm
from .models import (
    ChatMessage,
    ChatThread,
    Favorite,
    Listing,
    ListingImage,
    Notification,
    Profile,
)


LOGIN_WINDOW_SECONDS = 60
LOGIN_MAX_ATTEMPTS_PER_IP = 5
LOGIN_LOCK_SECONDS = 15 * 60
LOGIN_MAX_FAILURES_BEFORE_LOCK = 10


def _serialize_chat_message(msg, current_user_id: int):
    return {
        "id": msg.id,
        "text": msg.text,
        "created_at": msg.created_at.strftime("%d.%m.%Y %H:%M"),
        "is_me": msg.sender_id == current_user_id,
    }


def _get_client_ip(request) -> str:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _lock_key(ip: str, username: str) -> str:
    return f"auth:lock:{ip}:{username.lower().strip()}"


def _window_key(ip: str) -> str:
    return f"auth:window:{ip}"


def _fail_key(ip: str, username: str) -> str:
    return f"auth:fail:{ip}:{username.lower().strip()}"


def _is_rate_limited(ip: str) -> bool:
    key = _window_key(ip)
    attempts = cache.get(key, 0)
    if attempts >= LOGIN_MAX_ATTEMPTS_PER_IP:
        return True
    cache.set(key, attempts + 1, LOGIN_WINDOW_SECONDS)
    return False


def _is_locked(ip: str, username: str) -> bool:
    return bool(cache.get(_lock_key(ip, username)))


def _register_login_failure(ip: str, username: str) -> None:
    key = _fail_key(ip, username)
    failures = cache.get(key, 0) + 1
    cache.set(key, failures, LOGIN_LOCK_SECONDS)
    if failures >= LOGIN_MAX_FAILURES_BEFORE_LOCK:
        cache.set(_lock_key(ip, username), 1, LOGIN_LOCK_SECONDS)


def _clear_login_protection(ip: str, username: str) -> None:
    cache.delete(_fail_key(ip, username))
    cache.delete(_lock_key(ip, username))

def listing_list(request):
    listings = Listing.objects.filter(
        is_active=True, status=Listing.STATUS_PUBLISHED
    )
    min_price = request.GET.get("min_price")
    max_price = request.GET.get("max_price")
    rooms = request.GET.get("rooms")
    floor = request.GET.get("floor")
    pets = request.GET.get("pets")
    heating = request.GET.get("heating")

    if min_price:
        listings = listings.filter(price_per_month__gte=min_price)
    if max_price:
        listings = listings.filter(price_per_month__lte=max_price)
    if rooms:
        listings = listings.filter(rooms=rooms)
    if floor:
        listings = listings.filter(floor=floor)
    if pets:
        listings = listings.filter(pets=pets)
    if heating:
        listings = listings.filter(heating=heating)

    rooms_labels = dict(Listing.ROOMS_CHOICES)
    pets_labels = dict(Listing.PETS_CHOICES)
    heating_labels = dict(Listing.HEATING_CHOICES)

    params = {
        "min_price": min_price or "",
        "max_price": max_price or "",
        "rooms": rooms or "",
        "floor": floor or "",
        "pets": pets or "",
        "heating": heating or "",
    }

    def build_qs(exclude_key: str) -> str:
        filtered = {k: v for k, v in params.items() if v and k != exclude_key}
        return urlencode(filtered)

    favorite_ids = set()
    if request.user.is_authenticated:
        favorite_ids = set(
            Favorite.objects.filter(user=request.user).values_list("listing_id", flat=True)
        )

    context = {
        "listings": listings,
        "filters": params,
        "rooms_choices": Listing.ROOMS_CHOICES,
        "pets_choices": Listing.PETS_CHOICES,
        "heating_choices": Listing.HEATING_CHOICES,
        "rooms_label": rooms_labels.get(rooms, ""),
        "pets_label": pets_labels.get(pets, ""),
        "heating_label": heating_labels.get(heating, ""),
        "qs_without_min_price": build_qs("min_price"),
        "qs_without_max_price": build_qs("max_price"),
        "qs_without_rooms": build_qs("rooms"),
        "qs_without_floor": build_qs("floor"),
        "qs_without_pets": build_qs("pets"),
        "qs_without_heating": build_qs("heating"),
        "favorite_ids": favorite_ids,
    }
    return render(request, "listings/listing_list.html", context)


def listing_detail(request, pk: int):
    listing = get_object_or_404(Listing, pk=pk, is_active=True)
    Listing.objects.filter(pk=listing.pk).update(views_count=models.F("views_count") + 1)
    listing.refresh_from_db(fields=["views_count"])
    owner_profile, _ = Profile.objects.get_or_create(user=listing.owner)
    is_favorite = False
    thread_messages = []
    thread_id = None
    modal_open = request.GET.get("open_message") == "1"
    if request.user.is_authenticated:
        is_favorite = Favorite.objects.filter(user=request.user, listing=listing).exists()
        if listing.owner_id and listing.owner_id != request.user.id:
            thread = ChatThread.objects.filter(
                listing=listing, landlord=listing.owner, tenant=request.user
            ).first()
            if thread:
                thread_id = thread.id
                thread_messages = list(
                    thread.messages.select_related("sender", "recipient").order_by("created_at")
                )
    return render(
        request,
        "listings/listing_detail.html",
        {
            "listing": listing,
            "owner_profile": owner_profile,
            "is_favorite": is_favorite,
            "thread_messages": thread_messages,
            "thread_id": thread_id,
            "modal_open": modal_open,
            "owner_last_seen": owner_profile.last_seen_at,
        },
    )


@login_required
def report_listing(request, pk: int):
    listing = get_object_or_404(Listing, pk=pk, is_active=True)
    if listing.owner_id == request.user.id:
        messages.error(request, "Не можна скаржитися на власне оголошення.")
        return redirect("listings:listing_detail", pk=pk)

    if request.method == "POST":
        form = ListingReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.listing = listing
            report.reporter = request.user
            report.save()
            messages.success(request, "Скаргу надіслано. Дякуємо за звернення.")
            return redirect("listings:listing_detail", pk=pk)
    else:
        form = ListingReportForm()

    return render(
        request,
        "listings/report_listing.html",
        {"listing": listing, "form": form},
    )


def author_listings(request, user_id: int):
    User = get_user_model()
    author = get_object_or_404(User, pk=user_id)
    listings = Listing.objects.filter(
        owner=author, is_active=True, status=Listing.STATUS_PUBLISHED
    )
    return render(
        request,
        "listings/author_listings.html",
        {"author": author, "listings": listings},
    )


def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.get_or_create(user=user)
            messages.success(request, "Account created. Please sign in.")
            return redirect("login")
    else:
        form = SignUpForm()
    return render(request, "listings/signup.html", {"form": form})

def login_view(request):
    username = (request.POST.get("username") or "").strip()
    ip = _get_client_ip(request)
    next_url = request.POST.get("next") or request.GET.get("next") or ""

    if request.method == "POST":
        if _is_rate_limited(ip):
            form = LoginForm(request=request, data=request.POST)
            form.add_error(
                None,
                "Занадто багато спроб входу з вашої IP-адреси. Спробуйте через хвилину.",
            )
            return render(
                request,
                "registration/login.html",
                {"form": form, "next_url": next_url},
                status=429,
            )

        if username and _is_locked(ip, username):
            form = LoginForm(request=request, data=request.POST)
            form.add_error(
                None,
                "Акаунт тимчасово заблоковано через багато невдалих спроб входу. Спробуйте пізніше.",
            )
            return render(
                request,
                "registration/login.html",
                {"form": form, "next_url": next_url},
                status=429,
            )

        form = LoginForm(request=request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            _clear_login_protection(ip, user.get_username())
            return redirect(next_url or reverse("listings:dashboard_list"))

        if username:
            _register_login_failure(ip, username)
        return render(
            request,
            "registration/login.html",
            {"form": form, "next_url": next_url},
            status=400,
        )

    form = LoginForm(request=request)
    return render(request, "registration/login.html", {"form": form, "next_url": next_url})


@login_required
def dashboard_list(request):
    listings = Listing.objects.filter(owner=request.user)
    total_views = (
        listings.aggregate(total=models.Sum("views_count")).get("total") or 0
    )
    return render(
        request,
        "listings/dashboard_list.html",
        {"listings": listings, "total_views": total_views},
    )


@login_required
def notifications_list(request):
    notifications = Notification.objects.filter(is_active=True).filter(
        Q(recipient=request.user) | Q(recipient__isnull=True)
    )
    return render(
        request,
        "listings/notifications_list.html",
        {"notifications": notifications},
    )


@login_required
def dashboard_create(request):
    if request.method == "POST":
        form = ListingForm(request.POST, request.FILES)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.owner = request.user
            listing.save()
            for image in request.FILES.getlist("gallery"):
                ListingImage.objects.create(listing=listing, image=image)
            return redirect("listings:dashboard_list")
    else:
        form = ListingForm()
    return render(request, "listings/dashboard_form.html", {"form": form, "mode": "create"})


@login_required
def dashboard_update(request, pk: int):
    listing = get_object_or_404(Listing, pk=pk, owner=request.user)
    if request.method == "POST":
        form = ListingForm(request.POST, request.FILES, instance=listing)
        if form.is_valid():
            form.save()
            for image in request.FILES.getlist("gallery"):
                ListingImage.objects.create(listing=listing, image=image)
            return redirect("listings:dashboard_list")
    else:
        form = ListingForm(instance=listing)
    return render(request, "listings/dashboard_form.html", {"form": form, "mode": "update"})


@login_required
def dashboard_delete(request, pk: int):
    listing = get_object_or_404(Listing, pk=pk, owner=request.user)
    if request.method == "POST":
        listing.delete()
        return redirect("listings:dashboard_list")
    return render(
        request, "listings/dashboard_confirm_delete.html", {"listing": listing}
    )


@login_required
def profile_edit(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            return redirect("listings:dashboard_list")
    else:
        form = ProfileForm(instance=profile, user=request.user)
    return render(request, "listings/profile_edit.html", {"form": form})


@login_required
def favorites_list(request):
    favorites = (
        Favorite.objects.filter(user=request.user)
        .select_related("listing")
        .order_by("-created_at")
    )
    return render(request, "listings/favorites_list.html", {"favorites": favorites})


@login_required
def favorite_toggle(request, pk: int):
    listing = get_object_or_404(Listing, pk=pk, status=Listing.STATUS_PUBLISHED)
    fav, created = Favorite.objects.get_or_create(user=request.user, listing=listing)
    if not created:
        fav.delete()
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    return redirect(next_url)


@login_required
def dashboard_image_delete(request, pk: int):
    image = get_object_or_404(ListingImage, pk=pk, listing__owner=request.user)
    if request.method == "POST":
        listing_id = image.listing_id
        image.delete()
        return redirect("listings:dashboard_update", pk=listing_id)
    return redirect("listings:dashboard_update", pk=image.listing_id)


@login_required
def send_message(request, pk: int):
    if request.method != "POST":
        return redirect("listings:listing_detail", pk=pk)

    listing = get_object_or_404(Listing, pk=pk, is_active=True)
    text = (request.POST.get("message_text") or "").strip()

    if not listing.owner_id or listing.owner_id == request.user.id:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
        return redirect("listings:listing_detail", pk=pk)

    thread, _ = ChatThread.objects.get_or_create(
        listing=listing,
        landlord=listing.owner,
        tenant=request.user,
    )

    if text:
        msg = ChatMessage.objects.create(
            thread=thread,
            sender=request.user,
            recipient=listing.owner,
            text=text,
        )
        ChatThread.objects.filter(pk=thread.pk).update(updated_at=models.functions.Now())
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "ok": True,
                    "thread_id": thread.id,
                    "message": _serialize_chat_message(msg, request.user.id),
                }
            )

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": False, "error": "empty_message"}, status=400)

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or ""
    if not next_url:
        return redirect("listings:listing_detail", pk=pk)

    split = urlsplit(next_url)
    query = dict(parse_qsl(split.query))
    query["open_message"] = "1"
    updated = split._replace(query=urlencode(query))
    return redirect(urlunsplit(updated))


@login_required
def messages_list(request):
    active_tab = request.GET.get("tab", "incoming")
    if active_tab not in {"incoming", "outgoing", "unread"}:
        active_tab = "incoming"

    incoming_threads = (
        ChatThread.objects.filter(landlord=request.user)
        .select_related("listing", "landlord", "tenant")
        .order_by("-updated_at")
    )
    outgoing_threads = (
        ChatThread.objects.filter(tenant=request.user)
        .select_related("listing", "landlord", "tenant")
        .order_by("-updated_at")
    )
    unread_threads = (
        ChatThread.objects.filter(messages__recipient=request.user, messages__is_read=False)
        .select_related("listing", "landlord", "tenant")
        .distinct()
        .order_by("-updated_at")
    )
    incoming_user_ids = list(incoming_threads.values_list("tenant_id", flat=True))
    outgoing_user_ids = list(outgoing_threads.values_list("landlord_id", flat=True))
    unread_counterparty_ids = []
    for thread in unread_threads:
        if request.user.id == thread.landlord_id:
            unread_counterparty_ids.append(thread.tenant_id)
        else:
            unread_counterparty_ids.append(thread.landlord_id)
    incoming_seen_map = {
        p.user_id: p.last_seen_at
        for p in Profile.objects.filter(user_id__in=incoming_user_ids)
    }
    outgoing_seen_map = {
        p.user_id: p.last_seen_at
        for p in Profile.objects.filter(user_id__in=outgoing_user_ids)
    }
    unread_seen_map = {
        p.user_id: p.last_seen_at
        for p in Profile.objects.filter(user_id__in=unread_counterparty_ids)
    }
    for thread in incoming_threads:
        thread.tenant_last_seen = incoming_seen_map.get(thread.tenant_id)
    for thread in outgoing_threads:
        thread.landlord_last_seen = outgoing_seen_map.get(thread.landlord_id)
    for thread in unread_threads:
        counterparty_id = thread.tenant_id if request.user.id == thread.landlord_id else thread.landlord_id
        thread.counterparty_last_seen = unread_seen_map.get(counterparty_id)

    if active_tab == "incoming":
        current_threads = incoming_threads
    elif active_tab == "outgoing":
        current_threads = outgoing_threads
    else:
        current_threads = unread_threads

    return render(
        request,
        "listings/messages_list.html",
        {
            "active_tab": active_tab,
            "current_threads": current_threads,
            "incoming_threads": incoming_threads,
            "outgoing_threads": outgoing_threads,
            "unread_threads": unread_threads,
        },
    )


@login_required
def chat_detail(request, thread_id: int):
    thread = get_object_or_404(
        ChatThread.objects.select_related("listing", "landlord", "tenant"), pk=thread_id
    )
    if request.user.id not in (thread.landlord_id, thread.tenant_id):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
        return redirect("listings:messages_list")

    other_user = thread.tenant if request.user.id == thread.landlord_id else thread.landlord
    other_profile, _ = Profile.objects.get_or_create(user=other_user)

    if request.method == "POST":
        text = (request.POST.get("message_text") or "").strip()
        if text:
            recipient = thread.tenant if request.user.id == thread.landlord_id else thread.landlord
            msg = ChatMessage.objects.create(
                thread=thread,
                sender=request.user,
                recipient=recipient,
                text=text,
            )
            ChatThread.objects.filter(pk=thread.pk).update(updated_at=models.functions.Now())
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {"ok": True, "message": _serialize_chat_message(msg, request.user.id)}
                )
            return redirect("listings:chat_detail", thread_id=thread.id)
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "empty_message"}, status=400)

    ChatMessage.objects.filter(
        thread=thread, recipient=request.user, is_read=False
    ).update(is_read=True)
    messages_qs = thread.messages.select_related("sender", "recipient")
    return render(
        request,
        "listings/chat_detail.html",
        {
            "thread": thread,
            "messages": messages_qs,
            "other_user": other_user,
            "other_last_seen": other_profile.last_seen_at,
        },
    )


@login_required
def chat_messages_api(request, thread_id: int):
    thread = get_object_or_404(ChatThread, pk=thread_id)
    if request.user.id not in (thread.landlord_id, thread.tenant_id):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    after_id = int(request.GET.get("after_id", "0") or 0)
    messages_qs = thread.messages.filter(id__gt=after_id).select_related("sender", "recipient")
    messages_data = [_serialize_chat_message(m, request.user.id) for m in messages_qs]

    ChatMessage.objects.filter(
        thread=thread, recipient=request.user, is_read=False, id__gt=after_id
    ).update(is_read=True)

    return JsonResponse({"ok": True, "messages": messages_data})
