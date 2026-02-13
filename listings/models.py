from django.conf import settings
from django.db import models


class Listing(models.Model):
    HEATING_INDIVIDUAL = "individual"
    HEATING_CENTRAL = "central"
    HEATING_BUILDING = "building"
    HEATING_OTHER = "other"

    PETS_ALLOWED = "allowed"
    PETS_CATS = "cats_only"
    PETS_NOT_ALLOWED = "not_allowed"
    PETS_NEGOTIABLE = "negotiable"

    HEATING_CHOICES = [
        (HEATING_INDIVIDUAL, "Індивідуальне"),
        (HEATING_CENTRAL, "Централізоване"),
        (HEATING_BUILDING, "Будинкове"),
        (HEATING_OTHER, "Інше"),
    ]
    PETS_CHOICES = [
        (PETS_ALLOWED, "Можна з тваринами"),
        (PETS_CATS, "Можна з котами"),
        (PETS_NOT_ALLOWED, "Не можна"),
        (PETS_NEGOTIABLE, "По домовленості"),
    ]
    ROOMS_1 = "1"
    ROOMS_2 = "2"
    ROOMS_3 = "3"
    ROOMS_4_PLUS = "4+"
    ROOMS_CHOICES = [
        (ROOMS_1, "1"),
        (ROOMS_2, "2"),
        (ROOMS_3, "3"),
        (ROOMS_4_PLUS, "4+"),
    ]
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_ARCHIVED = "archived"
    STATUS_BLOCKED = "blocked"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Чернетка"),
        (STATUS_PUBLISHED, "Опубліковано"),
        (STATUS_ARCHIVED, "Архів"),
        (STATUS_BLOCKED, "Заблоковано"),
    ]
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="listings",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=120)
    address = models.CharField(max_length=255)
    price_per_month = models.DecimalField(max_digits=10, decimal_places=2)
    floor = models.PositiveSmallIntegerField(null=True, blank=True)
    total_floors = models.PositiveSmallIntegerField(null=True, blank=True)
    heating = models.CharField(max_length=20, choices=HEATING_CHOICES, blank=True)
    pets = models.CharField(max_length=20, choices=PETS_CHOICES, blank=True)
    rooms = models.CharField(max_length=2, choices=ROOMS_CHOICES)
    area_sqm = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to="listing_photos/", blank=True)
    contact_name = models.CharField(max_length=120)
    contact_phone = models.CharField(max_length=50, blank=True)
    contact_email = models.EmailField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PUBLISHED
    )
    views_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.title} - {self.price_per_month}"


class ListingImage(models.Model):
    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="listing_photos/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self) -> str:
        return f"Image for {self.listing_id}"


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    avatar = models.ImageField(
        upload_to="profile_avatars/",
        default="profile_avatars/defolticon.png",
        blank=True,
    )
    last_seen_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.user.username


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "listing")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.listing_id}"


class Message(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_messages",
    )
    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name="messages"
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.sender_id} -> {self.recipient_id} ({self.listing_id})"


class ChatThread(models.Model):
    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name="chat_threads"
    )
    landlord = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="landlord_threads",
    )
    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tenant_threads"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        unique_together = ("listing", "landlord", "tenant")

    def __str__(self) -> str:
        return f"Thread {self.id} ({self.listing_id})"


class ChatMessage(models.Model):
    thread = models.ForeignKey(
        ChatThread, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_sent"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_received"
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"ChatMessage {self.id} in {self.thread_id}"


class ListingReport(models.Model):
    REASON_FRAUD = "fraud"
    REASON_INAPPROPRIATE = "inappropriate"
    REASON_SPAM = "spam"
    REASON_FALSE_INFO = "false_info"
    REASON_OTHER = "other"
    MODERATION_PENDING = "pending"
    MODERATION_IN_REVIEW = "in_review"
    MODERATION_APPROVED = "approved"
    MODERATION_REJECTED = "rejected"

    REASON_CHOICES = [
        (REASON_FRAUD, "Шахрайські дії"),
        (REASON_INAPPROPRIATE, "Неприпустимий контент"),
        (REASON_SPAM, "Спам або дубльоване оголошення"),
        (REASON_FALSE_INFO, "Неправдива інформація"),
        (REASON_OTHER, "Інше"),
    ]
    MODERATION_STATUS_CHOICES = [
        (MODERATION_PENDING, "Нова"),
        (MODERATION_IN_REVIEW, "На розгляді"),
        (MODERATION_APPROVED, "Підтверджено"),
        (MODERATION_REJECTED, "Відхилено"),
    ]

    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name="reports"
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listing_reports"
    )
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    description = models.TextField()
    moderation_status = models.CharField(
        max_length=20,
        choices=MODERATION_STATUS_CHOICES,
        default=MODERATION_PENDING,
    )
    moderation_reason = models.TextField(
        blank=True,
        help_text="Причина рішення модератора (обов'язково для відхилення).",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_listing_reports",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Report {self.id}: listing {self.listing_id} by user {self.reporter_id}"


class Notification(models.Model):
    TYPE_SITE_UPDATE = "site_update"
    TYPE_MAINTENANCE = "maintenance"
    TYPE_REPORT_RESULT = "report_result"
    TYPE_OTHER = "other"

    TYPE_CHOICES = [
        (TYPE_SITE_UPDATE, "Оновлення сайту"),
        (TYPE_MAINTENANCE, "Технічні роботи"),
        (TYPE_REPORT_RESULT, "Результат скарги"),
        (TYPE_OTHER, "Інше"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
        help_text="Якщо порожньо, сповіщення бачать усі користувачі.",
    )
    related_report = models.ForeignKey(
        ListingReport,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    notification_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default=TYPE_OTHER
    )
    title = models.CharField(max_length=150)
    message = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        target = self.recipient.username if self.recipient_id else "all users"
        return f"Notification {self.id} to {target}"

