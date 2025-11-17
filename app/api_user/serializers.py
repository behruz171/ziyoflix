from rest_framework import serializers
from app import models


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.User
        fields = (
            'id', 'username', 'first_name', 'last_name', 'email', 'role', 'bio', 'avatar'
        )
        read_only_fields = ('id', 'username', 'role',)


class OverviewStatsSerializer(serializers.Serializer):
    videos_watched = serializers.IntegerField()
    seconds_watched = serializers.IntegerField()
    tests_attempts = serializers.IntegerField()
    avg_test_score = serializers.FloatField(allow_null=True)
    assignments_submitted = serializers.IntegerField()
    liked_reels = serializers.IntegerField()
    comments_count = serializers.IntegerField()
    playlists_count = serializers.IntegerField()
    wallet_balance = serializers.DecimalField(max_digits=15, decimal_places=2)


class VideoProgressItemSerializer(serializers.Serializer):
    video_id = serializers.IntegerField()
    video_title = serializers.CharField()
    course_id = serializers.IntegerField()
    course_title = serializers.CharField()
    completed = serializers.BooleanField()
    seconds_watched = serializers.IntegerField()
    updated_at = serializers.DateTimeField()


class PlaylistBriefSerializer(serializers.ModelSerializer):
    movies_count = serializers.IntegerField(read_only=True)
    course_videos_count = serializers.IntegerField(read_only=True)
    reels_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = models.Playlist
        fields = (
            'id', 'title', 'description', 'is_public', 'movies_count', 'course_videos_count', 'reels_count', 'created_at'
        )


class AssignmentSubmissionOutSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    type = serializers.ChoiceField(choices=['video', 'course_type'])
    title = serializers.CharField()
    grade = serializers.IntegerField(allow_null=True)
    submitted_at = serializers.DateTimeField()


# Wallet reuse existing serializers
from app.api.wallet_serializers import WalletSerializer, WalletTransactionSerializer  # noqa
