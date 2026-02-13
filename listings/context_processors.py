from .models import ChatMessage, Favorite


def favorites_count(request):
    if request.user.is_authenticated:
        return {
            "favorites_count": Favorite.objects.filter(user=request.user).count(),
            "unread_messages_count": ChatMessage.objects.filter(
                recipient=request.user, is_read=False
            ).count(),
        }
    return {"favorites_count": 0, "unread_messages_count": 0}
