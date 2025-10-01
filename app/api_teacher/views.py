from rest_framework.views import APIView
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from datetime import timedelta

from app import models
from app.pagination import CoursePagination
from . import serializers
import shutil
import os
from django.conf import settings
import subprocess
from redis import Redis
import random
from app.pagination import *
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from django.db.models import Count, Sum, F
from datetime import timedelta


class TeacherChannelsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        channels = models.Channel.objects.filter(user=request.user)
        serializer = serializers.ChannelSerializer(channels, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TeacherAnalyticsOverviewAPIView(APIView):
    """High-level summary for the teacher dashboard (their own channels/courses only)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        channels = models.Channel.objects.filter(user=user)
        courses = models.Course.objects.filter(channel__in=channels)
        videos = models.CourseVideo.objects.filter(course__in=courses)

        reels = models.Reel.objects.filter(channel__in=channels)
        video_tests = models.VideoTest.objects.filter(course_video__in=videos)
        video_assigns = models.VideoAssignment.objects.filter(course_video__in=videos)
        ct_tests = models.CourseTypeTest.objects.filter(course_type__course__in=courses)
        ct_assigns = models.CourseTypeAssignment.objects.filter(course_type__course__in=courses)

        total_students = courses.aggregate(s=Sum('students_count'))['s'] or 0
        unique_learners = models.CourseVideoProgress.objects.filter(course_video__in=videos).values('user').distinct().count()
        completed_events = models.CourseVideoProgress.objects.filter(course_video__in=videos, completed=True).count()

        data = {
            'channels_count': channels.count(),
            'courses_count': courses.count(),
            'videos_count': videos.count(),
            'reels_count': reels.count(),
            'students_total': total_students,
            'unique_learners': unique_learners,
            'tests_count': video_tests.count() + ct_tests.count(),
            'assignments_count': video_assigns.count() + ct_assigns.count(),
            'completed_video_events': completed_events,
        }
        return Response(data, status=200)


# =============================
# Teacher: Channel Courses and Videos
# =============================
class TeacherChannelCoursesAPIView(APIView):
    """List courses for a given channel owned by the current teacher."""
    permission_classes = [IsAuthenticated]
    pagination_class = CoursePagination

    def get(self, request, channel_slug):
        channel = get_object_or_404(models.Channel, slug=channel_slug, user=request.user)
        courses = models.Course.objects.filter(channel=channel).order_by('-created_at')
        
        # Pagination
        paginator = self.pagination_class()
        paginated_courses = paginator.paginate_queryset(courses, request)
        
        if paginated_courses is not None:
            serializer = serializers.TeacherCourseSerializer(paginated_courses, many=True)
            paginated_response = paginator.get_paginated_response(serializer.data)
            
            # Channel ma'lumotini qo'shish
            paginated_response.data['channel'] = channel.title
            return paginated_response
        
        # Agar pagination ishlamasa, oddiy response
        data = serializers.TeacherCourseSerializer(courses, many=True).data
        return Response({
            'channel': channel.title,
            'courses': data
        }, status=200)


class TeacherCourseVideosAPIView(APIView):
    """List CourseVideos for a course under the teacher's channel. Optional filter by course_type_slug as a query param or path variant."""
    permission_classes = [IsAuthenticated]

    def get(self, request, channel_slug, course_slug, course_type_slug=None):
        channel = get_object_or_404(models.Channel, slug=channel_slug, user=request.user)
        course = get_object_or_404(models.Course, slug=course_slug, channel=channel)

        qs = models.CourseVideo.objects.filter(course=course).order_by('order', 'created_at')
        if course_type_slug:
            qs = qs.filter(course_type__slug=course_type_slug)
        elif ct := request.query_params.get('course_type_slug'):
            qs = qs.filter(course_type__slug=ct)

        data = serializers.TeacherCourseVideoSerializer(qs, many=True).data
        # Also return available course types for UI filters
        types = models.CourseType.objects.filter(course=course).order_by('id')
        types_data = serializers.CourseTypeBriefSerializer(types, many=True).data
        return Response({
            'channel': channel.title,
            'course': {'id': course.id, 'title': course.title, 'slug': course.slug},
            'course_types': types_data,
            'videos': data,
        }, status=200)


class TeacherAnalyticsCoursesAPIView(APIView):
    """Per-course analytics for the teacher's courses."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        channels = models.Channel.objects.filter(user=user)
        courses = models.Course.objects.filter(channel__in=channels).order_by('-created_at')
        course_list = []
        for c in courses:
            videos = models.CourseVideo.objects.filter(course=c)
            vids_ids = list(videos.values_list('id', flat=True))
            tests_cnt = models.VideoTest.objects.filter(course_video__in=videos).count()
            assigns_cnt = models.VideoAssignment.objects.filter(course_video__in=videos).count()
            ct_tests_cnt = models.CourseTypeTest.objects.filter(course_type__course=c).count()
            ct_assigns_cnt = models.CourseTypeAssignment.objects.filter(course_type__course=c).count()

            unique_learners = models.CourseVideoProgress.objects.filter(course_video__in=videos).values('user').distinct().count()
            completed_events = models.CourseVideoProgress.objects.filter(course_video__in=videos, completed=True).count()

            course_list.append({
                'id': c.id,
                'title': c.title,
                'slug': c.slug,
                'students_count': c.students_count,
                'videos_count': videos.count(),
                'tests_count': tests_cnt + ct_tests_cnt,
                'assignments_count': assigns_cnt + ct_assigns_cnt,
                'unique_learners': unique_learners,
                'completed_video_events': completed_events,
                'created_at': c.created_at,
            })

        return Response({'courses': course_list}, status=200)


class TeacherAnalyticsEngagementAPIView(APIView):
    """Engagement metrics over a time window (default 30 days)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            days = int(request.query_params.get('days', 30))
        except (TypeError, ValueError):
            days = 30
        since = timezone.now() - timedelta(days=max(1, days))

        channels = models.Channel.objects.filter(user=user)
        courses = models.Course.objects.filter(channel__in=channels)
        videos = models.CourseVideo.objects.filter(course__in=courses)

        progress_qs = models.CourseVideoProgress.objects.filter(course_video__in=videos, updated_at__gte=since)
        progress_events = progress_qs.count()
        active_learners = progress_qs.values('user').distinct().count()

        # Video-level tests
        vr_qs = models.TestResult.objects.filter(test__course_video__in=videos, completed_at__gte=since)
        video_test_results = vr_qs.count()
        video_test_passed = vr_qs.filter(score__gte=F('test__pass_score')).count()

        # CourseType-level tests
        ct_vr_qs = models.CourseTypeTestResult.objects.filter(test__course_type__course__in=courses, completed_at__gte=since)
        ct_test_results = ct_vr_qs.count()
        ct_test_passed = ct_vr_qs.filter(score__gte=F('test__pass_score')).count()

        # Assignments
        va_qs = models.AssignmentSubmission.objects.filter(assignment__course_video__in=videos, submitted_at__gte=since)
        ct_va_qs = models.CourseTypeAssignmentSubmission.objects.filter(assignment__course_type__course__in=courses, submitted_at__gte=since)

        data = {
            'window_days': days,
            'progress_events': progress_events,
            'active_learners': active_learners,
            'video_test_pass_rate': round((video_test_passed / video_test_results) * 100.0, 2) if video_test_results else 0.0,
            'ct_test_results': ct_test_results,
            'ct_test_pass_rate': round((ct_test_passed / ct_test_results) * 100.0, 2) if ct_test_results else 0.0,
            'assignment_submissions': va_qs.count() + ct_va_qs.count(),
        }
        return Response(data, status=200)


# =============================
# Teacher: CourseVideo Tests/Assignments/Summary
# =============================
class TeacherVideoTestsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, channel_slug, course_slug, video_id):
        channel = get_object_or_404(models.Channel, slug=channel_slug, user=request.user)
        course = get_object_or_404(models.Course, slug=course_slug, channel=channel)
        video = get_object_or_404(models.CourseVideo, id=video_id, course=course)

        test = models.VideoTest.objects.filter(course_video=video, is_active=True).order_by('-created_at').first()
        if not test:
            return Response({"video": video.id, "video_test": None}, status=200)

        payload = serializers.TeacherVideoTestSerializer(test).data
        return Response({"video": video.id, "video_test": payload}, status=200)


class TeacherVideoAssignmentsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, channel_slug, course_slug, video_id):
        channel = get_object_or_404(models.Channel, slug=channel_slug, user=request.user)
        course = get_object_or_404(models.Course, slug=course_slug, channel=channel)
        video = get_object_or_404(models.CourseVideo, id=video_id, course=course)

        assigns = models.VideoAssignment.objects.filter(course_video=video, is_active=True).order_by('-created_at')
        data = serializers.TeacherVideoAssignmentSerializer(assigns, many=True).data
        return Response({"video": video.id, "assignments": data}, status=200)


class TeacherVideoSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, channel_slug, course_slug, video_id):
        channel = get_object_or_404(models.Channel, slug=channel_slug, user=request.user)
        course = get_object_or_404(models.Course, slug=course_slug, channel=channel)
        video = get_object_or_404(models.CourseVideo, id=video_id, course=course)

        video_brief = serializers.TeacherCourseVideoSerializer(video).data
        test = models.VideoTest.objects.filter(course_video=video, is_active=True).order_by('-created_at').first()
        test_data = serializers.TeacherVideoTestSerializer(test).data if test else None
        assigns = models.VideoAssignment.objects.filter(course_video=video, is_active=True).order_by('-created_at')
        assigns_data = serializers.TeacherVideoAssignmentSerializer(assigns, many=True).data

        return Response({
            "channel": {"slug": channel.slug, "title": channel.title},
            "course": {"slug": course.slug, "title": course.title, "id": course.id},
            "video": video_brief,
            "video_test": test_data,
            "assignments": assigns_data,
        }, status=200)


# =============================
# Teacher: Reels (list and summary)
# =============================
class TeacherChannelReelsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, channel_slug):
        channel = get_object_or_404(models.Channel, slug=channel_slug, user=request.user)
        reels = models.Reel.objects.filter(channel=channel).order_by('-created_at')
        data = serializers.TeacherReelSerializer(reels, many=True).data
        return Response({
            'channel': {'slug': channel.slug, 'title': channel.title},
            'count': len(data),
            'reels': data,
        }, status=200)


class TeacherReelSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, channel_slug, reel_id):
        channel = get_object_or_404(models.Channel, slug=channel_slug, user=request.user)
        reel = get_object_or_404(models.Reel, id=reel_id, channel=channel)
        payload = serializers.TeacherReelSerializer(reel).data
        return Response({
            'channel': {'slug': channel.slug, 'title': channel.title},
            'reel': payload,
        }, status=200)


