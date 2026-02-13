from django.urls import path

from . import views

app_name = "listings"

urlpatterns = [
    path("", views.listing_list, name="listing_list"),
    path("listing/<int:pk>/", views.listing_detail, name="listing_detail"),
    path("author/<int:user_id>/", views.author_listings, name="author_listings"),
    path("signup/", views.signup, name="signup"),
    path("cabinet/", views.dashboard_list, name="dashboard_list"),
    path("cabinet/notifications/", views.notifications_list, name="notifications_list"),
    path("cabinet/new/", views.dashboard_create, name="dashboard_create"),
    path("cabinet/<int:pk>/edit/", views.dashboard_update, name="dashboard_update"),
    path("cabinet/<int:pk>/delete/", views.dashboard_delete, name="dashboard_delete"),
    path("cabinet/profile/", views.profile_edit, name="profile_edit"),
    path("cabinet/image/<int:pk>/delete/", views.dashboard_image_delete, name="dashboard_image_delete"),
    path("cabinet/favorites/", views.favorites_list, name="favorites_list"),
    path("cabinet/messages/", views.messages_list, name="messages_list"),
    path("cabinet/messages/<int:thread_id>/", views.chat_detail, name="chat_detail"),
    path("api/chat/<int:thread_id>/messages/", views.chat_messages_api, name="chat_messages_api"),
    path("favorite/<int:pk>/toggle/", views.favorite_toggle, name="favorite_toggle"),
    path("listing/<int:pk>/message/", views.send_message, name="send_message"),
    path("listing/<int:pk>/report/", views.report_listing, name="report_listing"),
]
