from django.urls import path, include

urlpatterns = [
    path('api/v1/', include('src.users.api.v1.urls')),
]