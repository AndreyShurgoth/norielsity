from django.db.models import Max

from .models import ChatMessage, Favorite


def favorites_count(request):
    if request.user.is_authenticated:
        latest_received_message_id = (
            ChatMessage.objects.filter(recipient=request.user).aggregate(max_id=Max("id"))["max_id"]
            or 0
        )
        return {
            "favorites_count": Favorite.objects.filter(user=request.user).count(),
            "unread_messages_count": ChatMessage.objects.filter(
                recipient=request.user, is_read=False
            ).count(),
            "latest_received_message_id": latest_received_message_id,
        }
    return {
        "favorites_count": 0,
        "unread_messages_count": 0,
        "latest_received_message_id": 0,
    }
