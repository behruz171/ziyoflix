from rest_framework.views import APIView
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Count, Avg, Sum, Q, Max
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
from django.db.models.functions import TruncDate, TruncWeek
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


# =============================
# Teacher: Tests list and stats
# =============================
class TeacherTestsListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request, channel_slug):
        channel = get_object_or_404(models.Channel, slug=channel_slug, user=request.user)

        # Optional filters
        course_slug = request.query_params.get('course')
        include_questions = request.query_params.get('include') == 'questions'

        courses = models.Course.objects.filter(channel=channel)
        if course_slug:
            courses = courses.filter(slug=course_slug)
        course_ids = list(courses.values_list('id', flat=True))

        # Collect tests for these courses
        video_tests = models.VideoTest.objects.filter(course_video__course_id__in=course_ids).select_related('course_video__course', 'created_by')
        ct_tests = models.CourseTypeTest.objects.filter(course_type__course_id__in=course_ids).select_related('course_type__course', 'created_by')

        items = []
        # Video tests
        for t in video_tests:
            course = t.course_video.course
            results = t.results.all()
            total_attempts = results.count()
            unique_students = results.values('user').distinct().count()
            passed = results.filter(score__gte=t.pass_score).count()
            pass_rate = round((passed / total_attempts) * 100.0, 2) if total_attempts else 0.0
            avg_score = results.aggregate(a=Avg('score'))['a']

            item = {
                'id': t.id,
                'title': t.title,
                'description': t.description,
                'type': 'video',
                'course': {'id': course.id, 'title': course.title, 'slug': course.slug},
                'questions_count': t.questions.count(),
                'time_limit': t.time_limit_minutes,
                'attempts_count': total_attempts,
                'pass_rate': pass_rate,
                'avg_score': float(avg_score) if avg_score is not None else None,
                'max_score': 100,
                'passing_score': t.pass_score,
                'created_at': t.created_at,
                'updated_at': None,
                'is_active': t.is_active,
                'difficulty': course.level if hasattr(course, 'level') else None,
                'tags': [],
                'creator': t.created_by or request.user,
            }
            if include_questions:
                item['questions'] = t.questions.prefetch_related('options').all()
            items.append(item)

        # CourseType tests
        for t in ct_tests:
            course = t.course_type.course
            results = t.results.all()
            total_attempts = results.count()
            passed = results.filter(score__gte=t.pass_score).count()
            pass_rate = round((passed / total_attempts) * 100.0, 2) if total_attempts else 0.0
            avg_score = results.aggregate(a=Avg('score'))['a']

            item = {
                'id': t.id,
                'title': t.title,
                'description': t.description,
                'type': 'course_type',
                'course': {'id': course.id, 'title': course.title, 'slug': course.slug},
                'questions_count': t.questions.count(),
                'time_limit': t.time_limit_minutes,
                'attempts_count': total_attempts,
                'pass_rate': pass_rate,
                'avg_score': float(avg_score) if avg_score is not None else None,
                'max_score': 100,
                'passing_score': t.pass_score,
                'created_at': t.created_at,
                'updated_at': None,
                'is_active': t.is_active,
                'difficulty': course.level if hasattr(course, 'level') else None,
                'tags': [],
                'creator': t.created_by or request.user,
            }
            if include_questions:
                item['questions'] = t.questions.prefetch_related('options').all()
            items.append(item)

        # Sort by created_at desc
        items.sort(key=lambda x: x['created_at'], reverse=True)

        # Pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(items, request)
        ser = serializers.TeacherTestListItemSerializer(page, many=True)

        # Build filters
        course_filters = []
        for c in models.Course.objects.filter(channel=channel):
            vt_cnt = models.VideoTest.objects.filter(course_video__course=c).count()
            ct_cnt = models.CourseTypeTest.objects.filter(course_type__course=c).count()
            course_filters.append({'id': c.id, 'title': c.title, 'slug': c.slug, 'tests_count': vt_cnt + ct_cnt})
        available_types = [
            {'type': 'video', 'label': 'Video Testlar', 'count': video_tests.count()},
            {'type': 'course_type', 'label': 'Oylik Testlar', 'count': ct_tests.count()},
        ]
        diff_counts = (
            models.Course.objects.filter(id__in=course_ids)
            .values('level').annotate(count=Count('id'))
        )
        diff_map = {'beginner': "Boshlang'ich", 'intermediate': "O'rta", 'advanced': 'Murakkab'}
        difficulty_levels = [
            {'level': d['level'], 'label': diff_map.get(d['level'], d['level']), 'count': d['count']}
            for d in diff_counts if d['level']
        ]

        resp = paginator.get_paginated_response(ser.data)
        resp.data['filters'] = {
            'available_courses': course_filters,
            'available_types': available_types,
            'difficulty_levels': difficulty_levels,
        }
        return resp


# =============================
# Teacher: Assignments list, stats, submissions
# =============================
class TeacherAssignmentsListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request, channel_slug):
        channel = get_object_or_404(models.Channel, slug=channel_slug, user=request.user)

        course_slug = request.query_params.get('course')
        qs = models.VideoAssignment.objects.filter(course_video__course__channel=channel)
        if course_slug:
            qs = qs.filter(course_video__course__slug=course_slug)

        items = []
        for a in qs.select_related('course_video__course', 'created_by'):
            course = a.course_video.course
            subs = a.submissions.all()
            submissions_count = subs.count()
            graded_count = subs.filter(grade__isnull=False).count()
            pending_count = submissions_count - graded_count
            avg_score = subs.aggregate(a=Avg('grade'))['a']
            attachment = None
            f = getattr(a, 'file', None)
            if f:
                try:
                    attachment = {'name': getattr(f, 'name', ''), 'file': f.url if hasattr(f, 'url') else '', 'size': f.size if hasattr(f, 'size') else None}
                except Exception:
                    attachment = {'name': getattr(f, 'name', ''), 'file': '', 'size': None}

            items.append({
                'id': a.id,
                'title': a.title,
                'description': a.description,
                'course': {'id': course.id, 'title': course.title, 'slug': course.slug},
                'due_date': a.due_at,
                'created_at': a.created_at,
                'is_active': a.is_active,
                'max_score': a.max_points,
                'submissions_count': submissions_count,
                'graded_count': graded_count,
                'pending_count': pending_count,
                'avg_score': float(avg_score) if avg_score is not None else None,
                'difficulty': getattr(course, 'level', None),
                'creator': a.created_by or request.user,
                'attachment': attachment,
            })

        # Pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(items, request)
        ser = serializers.TeacherAssignmentListItemSerializer(page, many=True)

        # Filters
        available_courses = []
        course_qs = models.Course.objects.filter(channel=channel)
        for c in course_qs:
            cnt = models.VideoAssignment.objects.filter(course_video__course=c).count()
            available_courses.append({'id': c.id, 'title': c.title, 'slug': c.slug, 'assignments_count': cnt})
        diff_counts = course_qs.values('level').annotate(count=Count('id'))
        diff_map = {'beginner': "Boshlang'ich", 'intermediate': "O'rta", 'advanced': 'Murakkab'}
        difficulty_levels = [
            {'level': d['level'], 'label': diff_map.get(d['level'], d['level']), 'count': d['count']}
            for d in diff_counts if d['level']
        ]
        # Status options counts
        now = timezone.now()
        active_cnt = qs.filter(is_active=True).count()
        overdue_cnt = qs.filter(is_active=True, due_at__lt=now).count()
        completed_cnt = qs.filter(is_active=False).count()
        status_options = [
            {'status': 'active', 'label': 'Faol', 'count': active_cnt},
            {'status': 'overdue', 'label': "Muddati o'tgan", 'count': overdue_cnt},
            {'status': 'completed', 'label': 'Tugagan', 'count': completed_cnt},
        ]

        resp = paginator.get_paginated_response(ser.data)
        resp.data['filters'] = {
            'available_courses': available_courses,
            # No assignment types in our model; omit available_types
            'difficulty_levels': difficulty_levels,
            'status_options': status_options,
        }
        return resp


class TeacherAssignmentsStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, channel_slug):
        channel = get_object_or_404(models.Channel, slug=channel_slug, user=request.user)
        assignments = models.VideoAssignment.objects.filter(course_video__course__channel=channel)
        submissions = models.AssignmentSubmission.objects.filter(assignment__in=assignments)

        total_assignments = assignments.count()
        total_submissions = submissions.count()
        total_students = submissions.values('student').distinct().count()
        avg_score = float(submissions.aggregate(a=Avg('grade'))['a'] or 0)

        now = timezone.now()
        overview = {
            'total_assignments': total_assignments,
            'total_submissions': total_submissions,
            'total_students': total_students,
            'avg_score': avg_score,
            'active_assignments': assignments.filter(is_active=True).count(),
            'overdue_assignments': assignments.filter(is_active=True, due_at__lt=now).count(),
            'completed_assignments': assignments.filter(is_active=False).count(),
            'pending_grading': submissions.filter(grade__isnull=True).count(),
        }

        # Difficulty breakdown by course level
        courses = models.Course.objects.filter(channel=channel)
        diff_map = {'beginner': "Boshlang'ich", 'intermediate': "O'rta", 'advanced': 'Murakkab'}
        difficulty_breakdown = {}
        for level, label in diff_map.items():
            level_courses = courses.filter(level=level)
            level_assign = assignments.filter(course_video__course__in=level_courses)
            level_subs = submissions.filter(assignment__in=level_assign)
            difficulty_breakdown[level] = {
                'count': level_assign.count(),
                'submissions': level_subs.count(),
                'avg_score': float(level_subs.aggregate(a=Avg('grade'))['a'] or 0),
            }

        # Course performance
        course_performance = []
        for c in courses:
            c_assign = assignments.filter(course_video__course=c)
            c_subs = submissions.filter(assignment__in=c_assign)
            course_performance.append({
                'course_id': c.id,
                'course_title': c.title,
                'assignments_count': c_assign.count(),
                'total_submissions': c_subs.count(),
                'avg_score': float(c_subs.aggregate(a=Avg('grade'))['a'] or 0),
                'students_count': models.WalletTransaction.objects.filter(course=c, transaction_type='course_purchase').values('wallet__user').distinct().count(),
            })

        # Recent activity
        recent = []
        for s in submissions.order_by('-submitted_at')[:10]:
            recent.append({
                'assignment_id': s.assignment_id,
                'assignment_title': s.assignment.title,
                'action': 'submission_received',
                'student_name': s.student.get_full_name() or s.student.username,
                'timestamp': s.submitted_at,
            })
        for s in submissions.filter(grade__isnull=False).order_by('-submitted_at')[:10]:
            recent.append({
                'assignment_id': s.assignment_id,
                'assignment_title': s.assignment.title,
                'action': 'graded',
                'student_name': s.student.get_full_name() or s.student.username,
                'score': s.grade,
                'timestamp': s.submitted_at,
            })
        for a in assignments.order_by('-created_at')[:5]:
            recent.append({
                'assignment_id': a.id,
                'assignment_title': a.title,
                'action': 'assignment_created',
                'timestamp': a.created_at,
            })

        # Time series
        daily_submissions = (
            submissions.annotate(date=TruncDate('submitted_at')).values('date')
            .annotate(submissions=Count('id'), graded=Count('id', filter=Q(grade__isnull=False)))
            .order_by('date')
        )
        weekly_performance = (
            assignments.annotate(week=TruncWeek('created_at')).values('week')
            .annotate(assignments_created=Count('id')).order_by('week')
        )

        # Top performing (by avg score and submissions)
        top_performing = []
        for a in assignments:
            a_subs = submissions.filter(assignment=a)
            if not a_subs.exists():
                continue
            top_performing.append({
                'assignment_id': a.id,
                'title': a.title,
                'avg_score': float(a_subs.aggregate(a=Avg('grade'))['a'] or 0),
                'submissions_count': a_subs.count(),
            })
        top_performing.sort(key=lambda x: (x['avg_score'], x['submissions_count']), reverse=True)
        top_performing = top_performing[:5]

        # Struggling areas (lowest avg score)
        struggling = []
        for a in assignments:
            a_subs = submissions.filter(assignment=a, grade__isnull=False)
            if not a_subs.exists():
                continue
            struggling.append({
                'assignment_id': a.id,
                'title': a.title,
                'avg_score': float(a_subs.aggregate(a=Avg('grade'))['a'] or 0),
            })
        struggling.sort(key=lambda x: x['avg_score'])
        struggling = struggling[:5]

        # Grading workload
        pending_assignments = []
        overdue_grading = []
        for a in assignments:
            a_subs = submissions.filter(assignment=a)
            pend = a_subs.filter(grade__isnull=True).count()
            if pend:
                pending_assignments.append({
                    'assignment_id': a.id,
                    'title': a.title,
                    'pending_count': pend,
                    'due_date': a.due_at,
                })
            if a.due_at and a.due_at < now:
                overdue_count = a_subs.filter(grade__isnull=True).count()
                if overdue_count:
                    overdue_grading.append({
                        'assignment_id': a.id,
                        'title': a.title,
                        'overdue_count': overdue_count,
                    })

        payload = {
            'overview': overview,
            'difficulty_breakdown': difficulty_breakdown,
            'course_performance': course_performance,
            'recent_activity': recent,
            'time_series': {
                'daily_submissions': list(daily_submissions),
                'weekly_performance': list(weekly_performance),
            },
            'top_performing_assignments': top_performing,
            'struggling_areas': struggling,
            'grading_workload': {
                'pending_assignments': pending_assignments,
                'overdue_grading': overdue_grading,
            }
        }
        return Response(payload, status=200)


class TeacherAssignmentSubmissionsListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request, channel_slug, assignment_id):
        channel = get_object_or_404(models.Channel, slug=channel_slug, user=request.user)
        assignment = get_object_or_404(models.VideoAssignment, id=assignment_id, course_video__course__channel=channel)
        subs = models.AssignmentSubmission.objects.filter(assignment=assignment).select_related('student')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(subs, request)
        ser = serializers.TeacherAssignmentSubmissionOutSerializer(page, many=True)
        resp = paginator.get_paginated_response(ser.data)

        stats = {
            'total_submissions': subs.count(),
            'graded_submissions': subs.filter(grade__isnull=False).count(),
            'pending_submissions': subs.filter(grade__isnull=True).count(),
            'late_submissions': subs.filter(assignment__due_at__isnull=False, submitted_at__gt=F('assignment__due_at')).count(),
            'avg_score': float(subs.aggregate(a=Avg('grade'))['a'] or 0),
            'per_student': [
                {
                    'student': {
                        'id': s['student'],
                        'full_name': (models.User.objects.get(id=s['student']).get_full_name() or models.User.objects.get(id=s['student']).username),
                        'username': models.User.objects.get(id=s['student']).username,
                    },
                    'submissions_count': s['cnt'],
                    'best_score': s['best'] if s['best'] is not None else None,
                    'latest_submission': s['latest']
                }
                for s in subs.values('student').annotate(cnt=Count('id'), best=Max('grade'), latest=Max('submitted_at'))
            ]
        }

        resp.data['assignment'] = {
            'id': assignment.id,
            'title': assignment.title,
            'max_score': assignment.max_points,
            'passing_score': None,
            'due_date': assignment.due_at,
        }
        resp.data['summary'] = stats
        return resp


class TeacherTestsStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, channel_slug):
        channel = get_object_or_404(models.Channel, slug=channel_slug, user=request.user)
        courses = models.Course.objects.filter(channel=channel)
        videos = models.CourseVideo.objects.filter(course__in=courses)

        # Collections
        vt = models.VideoTest.objects.filter(course_video__in=videos)
        ctt = models.CourseTypeTest.objects.filter(course_type__course__in=courses)

        vt_results = models.TestResult.objects.filter(test__in=vt)
        ctt_results = models.CourseTypeTestResult.objects.filter(test__in=ctt)

        total_tests = vt.count() + ctt.count()
        total_attempts = vt_results.count() + ctt_results.count()
        total_students = (
            vt_results.values('user').distinct().count() +
            ctt_results.values('user').distinct().count()
        )

        def agg_pass_rate(qs, pass_score_field):
            total = qs.count()
            if not total:
                return 0.0
            # approximate using join filter
            passed = qs.filter(score__gte=F(pass_score_field)).count()
            return round((passed / total) * 100.0, 2)

        avg_pass_rate = 0.0
        if total_tests:
            avg_pass_rate = round(
                (
                    agg_pass_rate(vt_results, 'test__pass_score') +
                    agg_pass_rate(ctt_results, 'test__pass_score')
                ) / 2.0, 2
            )

        # average completion time not tracked -> 0
        overview = {
            'total_tests': total_tests,
            'total_attempts': total_attempts,
            'total_students': total_students,
            'avg_pass_rate': avg_pass_rate,
            'avg_completion_time': 0,
            'active_tests': vt.filter(is_active=True).count() + ctt.filter(is_active=True).count(),
            'inactive_tests': vt.filter(is_active=False).count() + ctt.filter(is_active=False).count(),
        }

        test_types = {
            'video_tests': {
                'count': vt.count(),
                'attempts': vt_results.count(),
                'pass_rate': agg_pass_rate(vt_results, 'test__pass_score'),
                'avg_score': float(vt_results.aggregate(a=Avg('score'))['a'] or 0),
            },
            'course_type_tests': {
                'count': ctt.count(),
                'attempts': ctt_results.count(),
                'pass_rate': agg_pass_rate(ctt_results, 'test__pass_score'),
                'avg_score': float(ctt_results.aggregate(a=Avg('score'))['a'] or 0),
            }
        }

        # Difficulty breakdown by course level
        diff_map = {'beginner': "Boshlang'ich", 'intermediate': "O'rta", 'advanced': 'Murakkab'}
        diff_breakdown = {}
        for level, label in diff_map.items():
            level_courses = courses.filter(level=level)
            level_videos = models.CourseVideo.objects.filter(course__in=level_courses)
            level_vt = models.VideoTest.objects.filter(course_video__in=level_videos)
            level_ctt = models.CourseTypeTest.objects.filter(course_type__course__in=level_courses)
            level_results = models.TestResult.objects.filter(test__in=level_vt)
            level_ctt_results = models.CourseTypeTestResult.objects.filter(test__in=level_ctt)
            diff_breakdown[level] = {
                'count': level_vt.count() + level_ctt.count(),
                'attempts': level_results.count() + level_ctt_results.count(),
                'pass_rate': round((
                    agg_pass_rate(level_results, 'test__pass_score') +
                    agg_pass_rate(level_ctt_results, 'test__pass_score')
                ) / 2.0, 2) if (level_vt.exists() or level_ctt.exists()) else 0.0,
                'avg_score': float((level_results.aggregate(a=Avg('score'))['a'] or 0) + (level_ctt_results.aggregate(a=Avg('score'))['a'] or 0)) / 2.0,
            }

        # Course performance
        course_performance = []
        for c in courses:
            c_videos = models.CourseVideo.objects.filter(course=c)
            c_vt = models.VideoTest.objects.filter(course_video__in=c_videos)
            c_ctt = models.CourseTypeTest.objects.filter(course_type__course=c)
            c_vt_res = models.TestResult.objects.filter(test__in=c_vt)
            c_ctt_res = models.CourseTypeTestResult.objects.filter(test__in=c_ctt)
            attempts = c_vt_res.count() + c_ctt_res.count()
            pr = round((
                agg_pass_rate(c_vt_res, 'test__pass_score') +
                agg_pass_rate(c_ctt_res, 'test__pass_score')
            ) / 2.0, 2) if (c_vt.exists() or c_ctt.exists()) else 0.0
            avg_score = float((c_vt_res.aggregate(a=Avg('score'))['a'] or 0) + (c_ctt_res.aggregate(a=Avg('score'))['a'] or 0)) / 2.0
            course_performance.append({
                'course_id': c.id,
                'course_title': c.title,
                'tests_count': c_vt.count() + c_ctt.count(),
                'total_attempts': attempts,
                'pass_rate': pr,
                'avg_score': avg_score,
                'students_count': models.WalletTransaction.objects.filter(course=c, transaction_type='course_purchase').values('wallet__user').distinct().count(),
            })

        # Recent activity: last 15 events (results completed + new tests)
        recent = []
        for r in vt_results.order_by('-completed_at')[:10]:
            if r.completed_at:
                recent.append({
                    'test_id': r.test_id,
                    'test_title': r.test.title,
                    'action': 'attempt_completed',
                    'student_name': r.user.get_full_name() or r.user.username,
                    'score': r.score,
                    'timestamp': r.completed_at,
                })
        for t in vt.order_by('-created_at')[:5]:
            recent.append({
                'test_id': t.id,
                'test_title': t.title,
                'action': 'test_created',
                'timestamp': t.created_at,
            })

        # Time series
        daily_attempts = (
            vt_results.annotate(date=TruncDate('completed_at')).values('date')
            .annotate(attempts=Count('id'), completions=Count('id'), pass_count=Count('id', filter=Q(score__gte=F('test__pass_score'))))
            .order_by('date')
        )
        weekly_perf = (
            vt.annotate(week=TruncWeek('created_at')).values('week').annotate(tests_created=Count('id')).order_by('week')
        )

        payload = {
            'overview': overview,
            'test_types': test_types,
            'difficulty_breakdown': diff_breakdown,
            'course_performance': course_performance,
            'recent_activity': recent,
            'time_series': {
                'daily_attempts': list(daily_attempts),
                'weekly_performance': list(weekly_perf),
            },
            'top_performing_tests': [
                {
                    'test_id': t.id,
                    'title': t.title,
                    'pass_rate': agg_pass_rate(models.TestResult.objects.filter(test=t), 'test__pass_score'),
                    'attempts': models.TestResult.objects.filter(test=t).count(),
                } for t in vt.order_by('-created_at')[:5]
            ],
            'struggling_areas': [],
        }
        return Response(payload, status=200)


class TeacherTestAttemptsAPIView(APIView):
    """Return attempts for a specific test (video or course_type) under the teacher's channel."""
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request, channel_slug, test_id):
        channel = get_object_or_404(models.Channel, slug=channel_slug, user=request.user)

        # Try find as VideoTest
        test = models.VideoTest.objects.filter(id=test_id, course_video__course__channel=channel).first()
        test_type = 'video'
        if not test:
            # Try CourseTypeTest
            test = models.CourseTypeTest.objects.filter(id=test_id, course_type__course__channel=channel).first()
            test_type = 'course_type'
        if not test:
            return Response({'detail': 'Test not found or not owned by channel'}, status=404)

        # Gather results and answers
        attempts_data = []
        per_student_counts = {}
        if test_type == 'video':
            results = models.TestResult.objects.filter(test=test).select_related('user').order_by('-completed_at', '-started_at')
            # Preload correct options per question
            q_correct_map = {
                q.id: list(q.options.filter(is_correct=True).values('id', 'text', 'order', 'is_correct'))
                for q in test.questions.all().prefetch_related('options')
            }
            for r in results:
                per_student_counts[r.user_id] = per_student_counts.get(r.user_id, 0) + 1
                answers = []
                for a in r.answers.select_related('question', 'selected_option').all():
                    answers.append({
                        'question_id': a.question_id,
                        'question_text': a.question.text,
                        'selected_option': (
                            {'id': a.selected_option.id, 'text': a.selected_option.text, 'order': a.selected_option.order, 'is_correct': a.selected_option.is_correct}
                            if a.selected_option else None
                        ),
                        'is_correct': a.is_correct,
                        'correct_options': q_correct_map.get(a.question_id, []),
                    })
                attempts_data.append({
                    'user': r.user,
                    'attempt': r.attempt,
                    'score': r.score,
                    'started_at': r.started_at,
                    'completed_at': r.completed_at,
                    'answers': answers,
                })
        else:
            results = models.CourseTypeTestResult.objects.filter(test=test).select_related('user').order_by('-completed_at', '-started_at')
            q_correct_map = {
                q.id: list(q.options.filter(is_correct=True).values('id', 'text', 'order', 'is_correct'))
                for q in test.questions.all().prefetch_related('options')
            }
            for r in results:
                per_student_counts[r.user_id] = per_student_counts.get(r.user_id, 0) + 1
                answers = []
                for a in r.answers.select_related('question', 'selected_option').all():
                    answers.append({
                        'question_id': a.question_id,
                        'question_text': a.question.text,
                        'selected_option': (
                            {'id': a.selected_option.id, 'text': a.selected_option.text, 'order': a.selected_option.order, 'is_correct': a.selected_option.is_correct}
                            if a.selected_option else None
                        ),
                        'is_correct': a.is_correct,
                        'correct_options': q_correct_map.get(a.question_id, []),
                    })
                attempts_data.append({
                    'user': r.user,
                    'attempt': r.attempt,
                    'score': r.score,
                    'started_at': r.started_at,
                    'completed_at': r.completed_at,
                    'answers': answers,
                })

        # Build per-student summary
        user_objs = {u.id: u for u in models.User.objects.filter(id__in=per_student_counts.keys())}
        per_student = [
            {
                'user': {'id': uid, 'full_name': (user_objs[uid].get_full_name() or user_objs[uid].username) if uid in user_objs else '', 'username': user_objs[uid].username if uid in user_objs else ''},
                'attempts_count': cnt
            }
            for uid, cnt in per_student_counts.items()
        ]

        # Pagination for attempts
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(attempts_data, request)
        ser = serializers.TeacherTestAttemptSerializer(page, many=True)
        resp = paginator.get_paginated_response(ser.data)
        resp.data['test'] = {
            'id': test.id,
            'type': test_type,
            'title': test.title,
        }
        resp.data['summary'] = {
            'total_attempts': len(attempts_data),
            'unique_students': len(per_student_counts),
            'per_student': per_student,
        }
        return resp

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


class TeacherVideoCTTestsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, channel_slug, course_slug, course_type_slug):
        channel = get_object_or_404(models.Channel, slug=channel_slug, user=request.user)
        course = get_object_or_404(models.Course, slug=course_slug, channel=channel)
        # course_type_slug = get_object_or_404(models.CourseType, course=course)
        course_type = models.CourseType.objects.filter(course=course, slug=course_type_slug).first()
        test = models.CourseTypeTest.objects.filter(course_type=course_type, is_active=True).order_by('-created_at').first()
        if not test:
            return Response({"course_type": course_type.id, "course_type_test": None}, status=200)

        payload = serializers.TeacherCourseTypeTestSerializer(test).data
        return Response({"course_type": course_type.id, "course_type_test": payload}, status=200)

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



# =============================
# Teacher: Students (buyers) per course
# =============================
class TeacherCourseStudentsAPIView(APIView):
    """List students who purchased the course (full or course_type)."""
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request, channel_slug, course_slug):
        channel = get_object_or_404(models.Channel, slug=channel_slug, user=request.user)
        course = get_object_or_404(models.Course, slug=course_slug, channel=channel)

        # Purchases for this course: full course or course_type under this course
        purchase_qs = models.WalletTransaction.objects.filter(
            Q(course=course, transaction_type='course_purchase') |
            Q(course_type__course=course, transaction_type='course_type_purchase')
        ).select_related('wallet__user').order_by('-created_at')

        user_ids = list(purchase_qs.values_list('wallet__user_id', flat=True).distinct())
        users = {u.id: u for u in models.User.objects.filter(id__in=user_ids)}

        # Precompute counts per user
        videos = models.CourseVideo.objects.filter(course=course)
        video_ids = list(videos.values_list('id', flat=True))

        rows = []
        for uid in user_ids:
            user = users.get(uid)
            if not user:
                continue
            purchases_count = purchase_qs.filter(wallet__user_id=uid).count()
            tests_count = models.TestResult.objects.filter(user_id=uid, test__course_video_id__in=video_ids).count() \
                + models.CourseTypeTestResult.objects.filter(user_id=uid, test__course_type__course=course).count()
            assignments_count = models.AssignmentSubmission.objects.filter(student_id=uid, assignment__course_video_id__in=video_ids).count()

            rows.append({
                'user': user,
                'purchases_count': purchases_count,
                'tests_count': tests_count,
                'assignments_count': assignments_count,
            })

        # Pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(rows, request)
        if page is not None:
            data = serializers.TeacherStudentRowSerializer(page, many=True).data
            resp = paginator.get_paginated_response(data)
            resp.data['course'] = {'id': course.id, 'title': course.title}
            return resp

        data = serializers.TeacherStudentRowSerializer(rows, many=True).data
        return Response({'course': {'id': course.id, 'title': course.title}, 'count': len(data), 'students': data}, status=200)


class TeacherCourseStudentActivityAPIView(APIView):
    """Detailed activity of a specific student within a course."""
    permission_classes = [IsAuthenticated]

    def get(self, request, channel_slug, course_slug, user_id):
        channel = get_object_or_404(models.Channel, slug=channel_slug, user=request.user)
        course = get_object_or_404(models.Course, slug=course_slug, channel=channel)
        student = get_object_or_404(models.User, id=user_id)

        videos = models.CourseVideo.objects.filter(course=course)
        video_ids = list(videos.values_list('id', flat=True))

        video_test_results = models.TestResult.objects.filter(user=student, test__course_video_id__in=video_ids).order_by('-completed_at', '-started_at')
        course_type_test_results = models.CourseTypeTestResult.objects.filter(user=student, test__course_type__course=course).order_by('-completed_at', '-started_at')
        assignment_submissions = models.AssignmentSubmission.objects.filter(student=student, assignment__course_video_id__in=video_ids).order_by('-submitted_at')

        payload = {
            'student': student,
            'video_test_results': video_test_results,
            'course_type_test_results': course_type_test_results,
            'assignment_submissions': assignment_submissions,
        }
        data = serializers.TeacherStudentActivitySerializer(payload).data
        return Response({'course': {'id': course.id, 'title': course.title}, 'activity': data}, status=200)


class TeacherCourseStudentsStatsAPIView(APIView):
    """Aggregate stats about students for a course (counts, recent, revenue)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, channel_slug, course_slug):
        channel = get_object_or_404(models.Channel, slug=channel_slug, user=request.user)
        course = get_object_or_404(models.Course, slug=course_slug, channel=channel)

        # Window size
        try:
            days = int(request.query_params.get('days', 30))
        except (TypeError, ValueError):
            days = 30
        days = max(1, min(days, 365))
        since = timezone.now() - timedelta(days=days)

        # Purchases (distinct buyers)
        purchases = models.WalletTransaction.objects.filter(
            Q(course=course, transaction_type='course_purchase') |
            Q(course_type__course=course, transaction_type='course_type_purchase')
        )
        total_students = purchases.values('wallet__user').distinct().count()
        new_students_window = purchases.filter(created_at__gte=since).values('wallet__user').distinct().count()

        # Purchases by day
        purchases_daily = (
            purchases.filter(created_at__gte=since)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(count=Count('id', distinct=True), buyers=Count('wallet__user', distinct=True))
            .order_by('day')
        )

        # Revenue (teacher earnings)
        earnings_qs = models.WalletTransaction.objects.filter(
            Q(course=course, transaction_type='course_earning') |
            Q(course_type__course=course, transaction_type='course_type_earning'),
            wallet__user=channel.user,
        )
        revenue_total = earnings_qs.aggregate(s=Sum('amount'))['s'] or 0
        revenue_window = earnings_qs.filter(created_at__gte=since).aggregate(s=Sum('amount'))['s'] or 0
        revenue_daily = (
            earnings_qs.filter(created_at__gte=since)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(amount=Sum('amount'))
            .order_by('day')
        )

        # Engagement within the course (progress events per day, active learners per day)
        videos = models.CourseVideo.objects.filter(course=course)
        progress_qs = models.CourseVideoProgress.objects.filter(course_video__in=videos, updated_at__gte=since)
        progress_daily = (
            progress_qs.annotate(day=TruncDate('updated_at'))
            .values('day')
            .annotate(events=Count('id'), active_learners=Count('user', distinct=True))
            .order_by('day')
        )

        # Test results (video + course_type) by day
        video_results = models.TestResult.objects.filter(test__course_video__in=videos, completed_at__gte=since)
        ct_results = models.CourseTypeTestResult.objects.filter(test__course_type__course=course, completed_at__gte=since)
        def _results_agg(qs):
            return (
                qs.annotate(day=TruncDate('completed_at'))
                .values('day')
                .annotate(
                    attempts=Count('id'),
                    passed=Count('id', filter=Q(score__gte=F('test__pass_score')))
                )
                .order_by('day')
            )
        video_tests_daily = _results_agg(video_results)
        ct_tests_daily = _results_agg(ct_results)

        # Assignment submissions by day
        va_qs = models.AssignmentSubmission.objects.filter(assignment__course_video__in=videos, submitted_at__gte=since)
        ct_va_qs = models.CourseTypeAssignmentSubmission.objects.filter(assignment__course_type__course=course, submitted_at__gte=since)
        submissions_daily = (
            va_qs.annotate(day=TruncDate('submitted_at')).values('day').annotate(count=Count('id')).order_by('day')
        )
        ct_submissions_daily = (
            ct_va_qs.annotate(day=TruncDate('submitted_at')).values('day').annotate(count=Count('id')).order_by('day')
        )

        return Response({
            'course': {'id': course.id, 'title': course.title},
            'window_days': days,
            'students': {
                'total': total_students,
                'new_in_window': new_students_window,
                'purchases_daily': list(purchases_daily),
            },
            'revenue': {
                'total': revenue_total,
                'in_window': revenue_window,
                'daily': list(revenue_daily),
            },
            'engagement': {
                'progress_daily': list(progress_daily),
                'tests_daily': {
                    'video': list(video_tests_daily),
                    'course_type': list(ct_tests_daily),
                },
                'submissions_daily': {
                    'video': list(submissions_daily),
                    'course_type': list(ct_submissions_daily),
                }
            }
        }, status=200)

