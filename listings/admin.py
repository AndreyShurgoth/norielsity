from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    ChatMessage,
    ChatThread,
    Favorite,
    Listing,
    ListingImage,
    ListingReport,
    Message,
    Notification,
    Profile,
)


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 1


class ListingReportAdminForm(forms.ModelForm):
    class Meta:
        model = ListingReport
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("moderation_status")
        reason = (cleaned_data.get("moderation_reason") or "").strip()
        if status == ListingReport.MODERATION_REJECTED and not reason:
            self.add_error(
                "moderation_reason",
                "Вкажіть причину відхилення скарги.",
            )
        return cleaned_data


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "owner",
        "price_per_month",
        "rooms",
        "floor",
        "heating",
        "pets",
        "status",
        "views_count",
        "is_active",
        "created_at",
    )
    list_filter = ("status", "is_active", "rooms", "heating", "pets")
    search_fields = ("title", "address", "contact_name", "contact_phone", "contact_email")
    ordering = ("-created_at",)
    inlines = [ListingImageInline]


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "listing", "created_at")
    search_fields = ("user__username", "listing__title")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "recipient", "listing", "created_at", "is_read")
    list_filter = ("is_read", "created_at")
    search_fields = ("sender__username", "recipient__username", "listing__title", "text")


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ("listing", "landlord", "tenant", "updated_at")
    search_fields = ("listing__title", "landlord__username", "tenant__username")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("thread", "sender", "recipient", "created_at", "is_read")
    list_filter = ("is_read", "created_at")
    search_fields = ("thread__listing__title", "sender__username", "recipient__username", "text")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "full_name", "phone")


@admin.register(ListingReport)
class ListingReportAdmin(admin.ModelAdmin):
    form = ListingReportAdminForm
    list_display = (
        "id",
        "listing_link",
        "reporter",
        "reason",
        "moderation_status",
        "created_at",
    )
    list_filter = ("reason", "moderation_status", "created_at")
    search_fields = (
        "listing__title",
        "reporter__username",
        "description",
    )
    autocomplete_fields = ("listing", "reporter")
    readonly_fields = ("created_at", "reviewed_at", "reviewed_by")

    @admin.display(description="Listing", ordering="listing__title")
    def listing_link(self, obj):
        url = reverse("admin:listings_listing_change", args=[obj.listing_id])
        return format_html('<a href="{}">{}</a>', url, obj.listing.title)

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change:
            previous_status = (
                ListingReport.objects.filter(pk=obj.pk)
                .values_list("moderation_status", flat=True)
                .first()
            )

        if obj.moderation_status != ListingReport.MODERATION_PENDING:
            obj.reviewed_at = timezone.now()
            obj.reviewed_by = request.user
        else:
            obj.reviewed_at = None
            obj.reviewed_by = None

        super().save_model(request, obj, form, change)

        if previous_status == obj.moderation_status:
            return

        if obj.moderation_status == ListingReport.MODERATION_IN_REVIEW:
            Notification.objects.create(
                recipient=obj.reporter,
                related_report=obj,
                notification_type=Notification.TYPE_REPORT_RESULT,
                title="Скарга на розгляді",
                message=(
                    f"Вашу скаргу щодо оголошення '{obj.listing.title}' прийнято в роботу."
                ),
            )
            return

        if obj.moderation_status == ListingReport.MODERATION_REJECTED:
            Notification.objects.create(
                recipient=obj.reporter,
                related_report=obj,
                notification_type=Notification.TYPE_REPORT_RESULT,
                title="Скаргу відхилено",
                message=(
                    f"Скаргу щодо оголошення '{obj.listing.title}' відхилено.\n"
                    f"Причина: {obj.moderation_reason.strip()}"
                ),
            )
            return

        if obj.moderation_status == ListingReport.MODERATION_APPROVED:
            listing = obj.listing
            if listing.status != Listing.STATUS_BLOCKED:
                listing.status = Listing.STATUS_BLOCKED
                listing.save(update_fields=["status"])

            Notification.objects.create(
                recipient=obj.reporter,
                related_report=obj,
                notification_type=Notification.TYPE_REPORT_RESULT,
                title="Скаргу підтверджено",
                message=(
                    f"Скаргу щодо оголошення '{listing.title}' підтверджено. "
                    "Оголошення заблоковано."
                ),
            )

            if listing.owner_id:
                owner_message = (
                    f"Ваше оголошення '{listing.title}' заблоковано за результатами розгляду скарги."
                )
                moderation_reason = (obj.moderation_reason or "").strip()
                if moderation_reason:
                    owner_message += f"\nПричина: {moderation_reason}"

                Notification.objects.create(
                    recipient=listing.owner,
                    related_report=obj,
                    notification_type=Notification.TYPE_REPORT_RESULT,
                    title="Оголошення заблоковано",
                    message=owner_message,
                )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "notification_type",
        "recipient",
        "is_active",
        "created_at",
    )
    list_filter = ("notification_type", "is_active", "created_at")
    search_fields = ("title", "message", "recipient__username")
    autocomplete_fields = ("recipient", "related_report")
    readonly_fields = ("created_at",)
