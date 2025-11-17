from rest_framework import serializers
from app import models
from app.api import serializers as public_serializers
from app.api.wallet_serializers import WalletTransactionSerializer


class ToggleActiveSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class ToggleVerifiedSerializer(serializers.Serializer):
    verified = serializers.BooleanField()


class SetStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['moderation', 'rejected', 'approved'])


class ChannelStatsSerializer(public_serializers.ChannelCardSerializer):
    class Meta(public_serializers.ChannelCardSerializer.Meta):
        fields = public_serializers.ChannelCardSerializer.Meta.fields + ()


class PromoCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PromoCode
        fields = (
            'id', 'code', 'discount_type', 'value', 'max_uses', 'uses',
            'valid_from', 'valid_to', 'is_active',
            'created_at'
        )
        read_only_fields = ('id', 'uses', 'created_at')


class SimpleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'role', 'avatar')
        read_only_fields = fields


# For re-export convenience in views
CategorySerializer = public_serializers.CategorySerializer
MovieSerializer = public_serializers.MovieSerializer
CourseSerializer = public_serializers.CourseSerializer
CourseTypeSerializer = public_serializers.CourseTypeSerializer
CourseVideoSerializer = public_serializers.CourseVideoSerializer
BannerSerializer = public_serializers.BannerSerializer
WalletTxSerializer = WalletTransactionSerializer
CourseCategorySerializer = public_serializers.CourseCategorySerializer


class MovieFileAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MovieFile
        fields = [
            'id', 'title', 'file_url', 'upload_file', 'quality', 'language', 'is_trailer',
            'duration', 'hls_playlist_url', 'hls_segment_path', 'season', 'episode', 'created_at'
        ]
        read_only_fields = ('id', 'created_at')


class CourseModerationSerializer(public_serializers.CourseSerializer):
    class Meta(public_serializers.CourseSerializer.Meta):
        model = models.Course
        fields = public_serializers.CourseSerializer.Meta.fields + ('is_active', 'status', 'reason')


class CourseTypeModerationSerializer(public_serializers.CourseTypeSerializer):
    class Meta(public_serializers.CourseTypeSerializer.Meta):
        model = models.CourseType
        fields = public_serializers.CourseTypeSerializer.Meta.fields + ('status', 'reason')


class CourseVideoModerationSerializer(public_serializers.CourseVideoSerializer):
    class Meta(public_serializers.CourseVideoSerializer.Meta):
        model = models.CourseVideo
        fields = public_serializers.CourseVideoSerializer.Meta.fields + ('status', 'reason')
