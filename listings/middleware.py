from django.utils import timezone

from .models import Profile


class LastSeenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            profile, _ = Profile.objects.get_or_create(user=request.user)
            Profile.objects.filter(pk=profile.pk).update(last_seen_at=timezone.now())
        return self.get_response(request)
