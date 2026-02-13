from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

from .models import Listing, ListingReport, Profile


class ListingForm(forms.ModelForm):
    class Meta:
        model = Listing
        fields = [
            "title",
            "address",
            "price_per_month",
            "floor",
            "total_floors",
            "heating",
            "pets",
            "rooms",
            "area_sqm",
            "description",
            "photo",
            "contact_name",
            "contact_phone",
            "contact_email",
            "status",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        status_field = self.fields.get("status")
        if not status_field:
            return

        allowed_choices = [
            choice
            for choice in status_field.choices
            if choice[0] != Listing.STATUS_BLOCKED
        ]

        if self.instance.pk and self.instance.status == Listing.STATUS_BLOCKED:
            allowed_choices.append((Listing.STATUS_BLOCKED, "Заблоковано"))

        status_field.choices = allowed_choices

    def clean(self):
        cleaned_data = super().clean()
        floor = cleaned_data.get("floor")
        total_floors = cleaned_data.get("total_floors")
        if floor and total_floors and floor > total_floors:
            self.add_error(
                "floor",
                "Поверх не може бути більшим за загальну кількість поверхів.",
            )
        return cleaned_data

    def clean_status(self):
        status = self.cleaned_data.get("status")
        if self.instance.pk and self.instance.status == Listing.STATUS_BLOCKED:
            if status != Listing.STATUS_BLOCKED:
                raise forms.ValidationError(
                    "Це оголошення заблоковане модератором і не може бути розблоковане з кабінету."
                )
        return status


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already in use.")
        return email


class LoginForm(AuthenticationForm):
    username = forms.CharField(label=_("Логін"))
    password = forms.CharField(label=_("Пароль"), widget=forms.PasswordInput)

    error_messages = {
        "invalid_login": _(
            "Невірний логін або пароль. Перевірте введені дані та спробуйте ще раз."
        ),
        "inactive": _("Цей акаунт ще не активований через email."),
    }


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)

    class Meta:
        model = Profile
        fields = ["first_name", "last_name", "phone", "avatar"]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if not self.user:
            return

        self.fields["first_name"].initial = self.user.first_name
        self.fields["last_name"].initial = self.user.last_name

        if not self.user.first_name and not self.user.last_name and self.instance.full_name:
            parts = self.instance.full_name.strip().split(" ", 1)
            self.fields["first_name"].initial = parts[0]
            self.fields["last_name"].initial = parts[1] if len(parts) > 1 else ""

    def save(self, commit=True):
        profile = super().save(commit=False)
        first_name = (self.cleaned_data.get("first_name") or "").strip()
        last_name = (self.cleaned_data.get("last_name") or "").strip()

        if self.user:
            self.user.first_name = first_name
            self.user.last_name = last_name
            if commit:
                self.user.save(update_fields=["first_name", "last_name"])

        profile.full_name = f"{first_name} {last_name}".strip()
        if commit:
            profile.save()
        return profile


class ListingReportForm(forms.ModelForm):
    class Meta:
        model = ListingReport
        fields = ["reason", "description"]
        labels = {
            "reason": "Тема скарги",
            "description": "Детальний опис скарги",
        }
        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": "Опишіть детально, що саме сталося або що порушує правила.",
                }
            )
        }
