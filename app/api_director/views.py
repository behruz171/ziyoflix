from datetime import datetime
from django.db.models import Count, Sum, Q
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response

from app import models
from . import serializers as s


class IsDirectorOrAdmin(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        role = getattr(request.user, 'role', 'user')
        return role in ['director', 'admin'] or request.user.is_superuser


# Moderation: Course
class CourseModerationViewSet(viewsets.ModelViewSet):
    queryset = models.Course.objects.all().order_by('-created_at')
    serializer_class = s.CourseModerationSerializer
    permission_classes = [IsDirectorOrAdmin]
    lookup_field = 'slug'

    def get_queryset(self):
        qs = super().get_queryset() #type: ignore
        is_active = self.request.query_params.get('is_active')
        status_val = self.request.query_params.get('status')
        reason = self.request.query_params.get('reason')
        if is_active in ['true', 'false']:
            qs = qs.filter(is_active=(is_active == 'true'))
        if status_val in ['moderation', 'rejected', 'approved']:
            qs = qs.filter(status=status_val)
        if reason:
            qs = qs.filter(reason__icontains=reason)
        return qs

    @action(detail=True, methods=['patch'], url_path='toggle')
    def toggle_active(self, request, slug=None):
        obj = self.get_object()
        serializer = s.ToggleActiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj.is_active = serializer.validated_data['is_active']
        obj.save(update_fields=['is_active'])
        return Response({'id': obj.id, 'is_active': obj.is_active})

    @action(detail=True, methods=['patch'], url_path='set-status')
    def set_status(self, request, slug=None):
        obj = self.get_object()
        serializer = s.SetStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        status_val = serializer.validated_data['status']
        obj.status = status_val
        obj.is_active = (status_val == 'approved')
        obj.save(update_fields=['status', 'is_active'])
        return Response({'id': obj.id, 'status': obj.status, 'is_active': obj.is_active})


# Moderation: CourseType
class CourseTypeModerationViewSet(viewsets.ModelViewSet):
    queryset = models.CourseType.objects.all()
    serializer_class = s.CourseTypeModerationSerializer
    permission_classes = [IsDirectorOrAdmin]
    lookup_field = 'slug'

    def get_queryset(self):
        qs = self.queryset
        slug = self.request.query_params.get('slug')
        course_id = self.request.query_params.get('course_id')
        if slug:
            qs = qs.filter(slug=slug)
        if course_id:
            qs = qs.filter(course_id=course_id)

        is_active = self.request.query_params.get('is_active')
        status_val = self.request.query_params.get('status')
        reason = self.request.query_params.get('reason')

        if is_active in ['true', 'false']:
            qs = qs.filter(is_active=(is_active == 'true'))
        if status_val in ['moderation', 'rejected', 'approved']:
            qs = qs.filter(status=status_val)
        if reason:
            qs = qs.filter(reason__icontains=reason)

        return qs

    @action(detail=True, methods=['patch'], url_path='toggle')
    def toggle_active(self, request, slug=None):
        obj = self.get_object()
        serializer = s.ToggleActiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj.is_active = serializer.validated_data['is_active']
        obj.save(update_fields=['is_active'])
        return Response({'id': obj.id, 'is_active': obj.is_active})
    
    @action(detail=True, methods=['patch'], url_path='set-status')
    def set_status(self, request, slug=None):
        obj = self.get_object()
        serializer = s.SetStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        status_val = serializer.validated_data['status']
        obj.status = status_val
        obj.is_active = (status_val == 'approved')
        obj.save(update_fields=['status', 'is_active'])
        course_videos = models.CourseVideo.objects.filter(course_id=obj.course_id)
        for course_video in course_videos:
            course_video.status = status_val
            course_video.is_active = (status_val == 'approved')
            course_video.save(update_fields=['status', 'is_active'])
        return Response({'id': obj.id, 'status': obj.status, 'is_active': obj.is_active})


# Moderation: CourseVideo
class CourseVideoModerationViewSet(viewsets.ModelViewSet):
    queryset = models.CourseVideo.objects.select_related('course').all().order_by('course_id', 'order')
    serializer_class = s.CourseVideoModerationSerializer
    permission_classes = [IsDirectorOrAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        is_active = self.request.query_params.get('is_active')
        status_val = self.request.query_params.get('status')
        course_id = self.request.query_params.get('course_id')
        reason = self.request.query_params.get('reason')
        if is_active in ['true', 'false']:
            qs = qs.filter(is_active=(is_active == 'true'))
        if status_val in ['moderation', 'rejected', 'approved']:
            qs = qs.filter(status=status_val)
        if course_id:
            qs = qs.filter(course_id=course_id)
        if reason:
            qs = qs.filter(reason__icontains=reason)
        return qs

    @action(detail=True, methods=['patch'], url_path='toggle')
    def toggle_active(self, request, pk=None):
        obj = self.get_object()
        serializer = s.ToggleActiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj.is_active = serializer.validated_data['is_active']
        obj.save(update_fields=['is_active'])
        return Response({'id': obj.id, 'is_active': obj.is_active})

    @action(detail=True, methods=['patch'], url_path='set-status')
    def set_status(self, request, pk=None):
        obj = self.get_object()
        serializer = s.SetStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        status_val = serializer.validated_data['status']
        obj.status = status_val
        obj.is_active = (status_val == 'approved')
        obj.save(update_fields=['status', 'is_active'])
        return Response({'id': obj.id, 'status': obj.status, 'is_active': obj.is_active})


# Channels management
class ChannelAdminViewSet(viewsets.ModelViewSet):
    queryset = models.Channel.objects.all().order_by('-created_at')
    serializer_class = s.ChannelStatsSerializer
    permission_classes = [IsDirectorOrAdmin]
    lookup_field = 'slug'

    @action(detail=True, methods=['patch'], url_path='verify')
    def verify(self, request, slug=None):
        channel = self.get_object()
        serializer = s.ToggleVerifiedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        channel.verified = serializer.validated_data['verified']
        channel.save(update_fields=['verified'])
        return Response({'id': channel.id, 'verified': channel.verified})


# CourseCategory management
class CourseCategoryAdminViewSet(viewsets.ModelViewSet):
    queryset = models.CourseCategory.objects.all().order_by('name')
    serializer_class = s.CourseCategorySerializer
    permission_classes = [IsDirectorOrAdmin]
    lookup_field = 'slug'


# Movie Category management
class CategoryAdminViewSet(viewsets.ModelViewSet):
    queryset = models.Category.objects.all().order_by('name')
    serializer_class = s.CategorySerializer
    permission_classes = [IsDirectorOrAdmin]
    lookup_field = 'slug'

    @action(detail=True, methods=['get'], url_path='movies')
    def list_movies(self, request, slug=None):
        category = self.get_object()
        qs = models.Movie.objects.filter(categories=category).order_by('-created_at')
        data = s.MovieSerializer(qs, many=True).data
        return Response({'category': category.slug, 'count': len(data), 'results': data})

    @action(detail=True, methods=['post'], url_path='movies/add')
    def add_movie(self, request, slug=None):
        category = self.get_object()
        movie_slug = request.data.get('movie_slug')
        movie_id = request.data.get('movie_id')
        movie = None
        if movie_slug:
            movie = models.Movie.objects.filter(slug=movie_slug).first()
        elif movie_id:
            movie = models.Movie.objects.filter(id=movie_id).first()
        if not movie:
            return Response({'error': 'movie not found'}, status=status.HTTP_404_NOT_FOUND)
        movie.categories.add(category)
        return Response({'ok': True, 'category': category.slug, 'movie': movie.slug})

    @action(detail=True, methods=['delete'], url_path='movies/remove')
    def remove_movie(self, request, slug=None):
        category = self.get_object()
        movie_slug = request.query_params.get('movie_slug') or request.data.get('movie_slug')
        movie_id = request.query_params.get('movie_id') or request.data.get('movie_id')
        movie = None
        if movie_slug:
            movie = models.Movie.objects.filter(slug=movie_slug).first()
        elif movie_id:
            movie = models.Movie.objects.filter(id=movie_id).first()
        if not movie:
            return Response({'error': 'movie not found'}, status=status.HTTP_404_NOT_FOUND)
        movie.categories.remove(category)
        return Response({'ok': True, 'category': category.slug, 'movie': movie.slug})


# Banner management (reuse public serializer)
class BannerAdminViewSet(viewsets.ModelViewSet):
    queryset = models.Banner.objects.all().order_by('position', 'order')
    serializer_class = s.BannerSerializer
    permission_classes = [IsDirectorOrAdmin]


# Promo codes CRUD
class PromoCodeViewSet(viewsets.ModelViewSet):
    queryset = models.PromoCode.objects.all().order_by('-created_at')
    serializer_class = s.PromoCodeSerializer
    permission_classes = [IsDirectorOrAdmin]


# Users by role
class RoleUsersViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.User.objects.all().order_by('-date_joined')
    serializer_class = s.SimpleUserSerializer
    permission_classes = [IsDirectorOrAdmin]

    def get_queryset(self):
        role = self.kwargs.get('role')
        qs = super().get_queryset()
        if role in ['user', 'admin', 'teacher', 'director']:
            qs = qs.filter(role=role)
        return qs


# Transactions listing
class WalletTransactionAdminViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.WalletTransaction.objects.select_related('wallet', 'course', 'course_type').all()
    serializer_class = s.WalletTxSerializer
    permission_classes = [IsDirectorOrAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        tx_type = self.request.query_params.get('transaction_type')
        date_from = self.request.query_params.get('from')
        date_to = self.request.query_params.get('to')
        if tx_type:
            qs = qs.filter(transaction_type=tx_type)
        if date_from:
            try:
                start = datetime.fromisoformat(date_from)
                qs = qs.filter(created_at__gte=start)
            except Exception:
                pass
        if date_to:
            try:
                end = datetime.fromisoformat(date_to)
                qs = qs.filter(created_at__lte=end)
            except Exception:
                pass
        return qs.order_by('-created_at')


# Reports overview
class ReportsOverviewViewSet(viewsets.ViewSet):
    permission_classes = [IsDirectorOrAdmin]

    def list(self, request):
        users_by_role = models.User.objects.values('role').annotate(count=Count('id'))
        courses_total = models.Course.objects.count()
        courses_active = models.Course.objects.filter(is_active=True).count()
        videos_total = models.CourseVideo.objects.count()
        videos_active = models.CourseVideo.objects.filter(is_active=True).count()
        channels_total = models.Channel.objects.count()
        channels_verified = models.Channel.objects.filter(verified=True).count()

        tx = models.WalletTransaction.objects
        income = tx.filter(amount__gt=0).aggregate(total=Sum('amount'))['total'] or 0
        expense = tx.filter(amount__lt=0).aggregate(total=Sum('amount'))['total'] or 0
        tx_count = tx.count()
        tx_by_type = list(tx.values('transaction_type').annotate(count=Count('id')).order_by('transaction_type'))
        last_tx = tx.order_by('-created_at').values('id', 'transaction_type', 'amount', 'created_at').first()

        data = {
            'users_by_role': list(users_by_role),
            'courses': {'total': courses_total, 'active': courses_active},
            'videos': {'total': videos_total, 'active': videos_active},
            'channels': {'total': channels_total, 'verified': channels_verified},
            'wallet': {
                'total_income': str(income),
                'total_expense': str(expense),
                'transactions_count': tx_count,
                'by_type': tx_by_type,
                'last_transaction': last_tx,
            }
        }
        return Response(data)



# Movies management (CRUD only)
class MovieAdminViewSet(viewsets.ModelViewSet):
    queryset = models.Movie.objects.all().order_by('-created_at')
    serializer_class = s.MovieSerializer
    permission_classes = [IsDirectorOrAdmin]
    lookup_field = 'slug'

