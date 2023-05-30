from rest_framework import serializers
from src.reviews.models import Review
from django.contrib.auth import get_user_model

User = get_user_model()


class ShowAuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        
        fields = [
            'id',
            'username',
            'email'
        ]


class ReviewsSerializer(serializers.ModelSerializer):
    author = ShowAuthorSerializer(read_only=True)

    class Meta:
        model = Review
        fields = [
            'id',
            'author',
            'text',
            'created_at',
        ]