from rest_framework import viewsets, generics
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.core.files import File
from rest_framework.permissions import *
from .. import models
from . import serializers
import shutil
import os
from django.conf import settings
import subprocess
from app.tasks import process_video_task, process_reel_task, process_course_video_task
from redis import Redis
import random
from app.pagination import *
from django.shortcuts import get_object_or_404
from django.utils import timezone


redis_client = Redis(host="localhost", port=6379, db=0)


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response({"error": "Username va password kiritilishi shart."}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)
        if not user:
            return Response({"error": "Login yoki parol noto‘g‘ri."}, status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
            }
        }, status=status.HTTP_200_OK)



class SignUpAPIView(APIView):
    permission_classes = [AllowAny]  # lekin tekshiruvni o‘zimiz yozamiz

    def post(self, request):
        username = request.data.get("username")
        email = request.data.get("email")
        password = request.data.get("password")
        role = request.data.get("role", "user")  # default user bo‘ladi
        first_name = request.data.get("first_name", "")
        last_name = request.data.get("last_name", "")

        if not username or not email or not password:
            return Response({"error": "username, email, password kiritilishi shart"}, status=status.HTTP_400_BAD_REQUEST)

        # agar direktor yaratmoqchi bo‘lsa
        if role == "director" or role == "admin":
            if not request.user.is_authenticated:
                return Response({"error": "Director yaratish uchun token bilan kiring"}, status=status.HTTP_403_FORBIDDEN)
            if request.user.role != "director" and not request.user.is_superuser:
                return Response({"error": "Sizda director yaratish huquqi yo‘q"}, status=status.HTTP_403_FORBIDDEN)

        # Teacher yoki oddiy user o‘zi yaratishi mumkin
        if role not in ["user", "teacher", "admin", "director"]:
            return Response({"error": "Noto‘g‘ri role"} , status=status.HTTP_400_BAD_REQUEST)

        if models.User.objects.filter(username=username).exists():
            return Response({"error": "Bunday username allaqachon mavjud"}, status=status.HTTP_400_BAD_REQUEST)

        user = models.User(username=username, email=email, role=role, first_name=first_name, last_name=last_name)
        user.set_password(password)
        user.save()

        user = authenticate(username=username, password=password)
        if not user:
            return Response({"error": "Foydalanuvchi yaratishda noma'lum xato yuz berdi"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "Foydalanuvchi yaratildi",
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }
        }, status=status.HTTP_201_CREATED)

class BannerViewSet(viewsets.ModelViewSet):
    queryset = models.Banner.objects.all().order_by('position', 'order')
    serializer_class = serializers.BannerSerializer


class MovieViewSet(viewsets.ModelViewSet):
    queryset = models.Movie.objects.filter(is_published=True).order_by('-created_at')
    serializer_class = serializers.MovieSerializer


class CourseViewSet(viewsets.ModelViewSet):
    queryset = models.Course.objects.all().order_by('-created_at')
    serializer_class = serializers.CourseSerializer
    pagination_class = CoursePagination
    lookup_field = "slug"


class CourseTypeViewSet(viewsets.ModelViewSet):
    queryset = models.CourseType.objects.all()
    serializer_class = serializers.CourseTypeSerializer
    pagination_class = CustomPagination
    lookup_field = "slug"

class LanguageViewSet(viewsets.ModelViewSet):
    queryset = models.Language.objects.all()
    pagination_class = CustomPagination
    serializer_class = serializers.LanguageSerializer

class ReelViewSet(viewsets.ModelViewSet):
    queryset = models.Reel.objects.all().order_by('-created_at')
    serializer_class = serializers.ReelSerializer


class ChannelViewSet(viewsets.ModelViewSet):
    queryset = models.Channel.objects.all().order_by('-created_at')
    lookup_field = "slug"
    pagination_class = ChannelPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return serializers.ChannelCardSerializer
        return serializers.ChannelDetailSerializer  
    
    # Create channel
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = models.Category.objects.all().order_by("name")
    serializer_class = serializers.CategorySerializer
    lookup_field = "slug" 


class CourseVideoViewSet(viewsets.ModelViewSet):
    queryset = models.CourseVideo.objects.all().order_by('course_id', 'order')
    serializer_class = serializers.CourseVideoSerializer


class VideoTestViewSet(viewsets.ModelViewSet):
    queryset = models.VideoTest.objects.all().order_by('-created_at')
    serializer_class = serializers.VideoTestSerializer


class VideoAssignmentViewSet(viewsets.ModelViewSet):
    queryset = models.VideoAssignment.objects.all().order_by('-created_at')
    serializer_class = serializers.VideoAssignmentSerializer


class AssignmentSubmissionViewSet(viewsets.ModelViewSet):
    queryset = models.AssignmentSubmission.objects.all().order_by('-submitted_at')
    serializer_class = serializers.AssignmentSubmissionSerializer

class CourseCategoryViewSet(viewsets.ModelViewSet):
    queryset = models.CourseCategory.objects.all().order_by('name')
    serializer_class = serializers.CourseCategorySerializer
    lookup_field = "slug"

# ----------------------------
# Banner API
# ----------------------------
class BannerHomepageListView(APIView):
    def get(self, request, format=None):
        banners = serializers.BannerSerializer(
            models.Banner.objects.filter(is_active=True).order_by('position', 'order')[:10],
            many=True,
            context={'request': request}
        ).data
        return Response({'banners': banners}, status=status.HTTP_200_OK)

# ----------------------------
# Movies API
# ----------------------------
class MovieHomepageListView(APIView):
    def get(self, request, format=None):
        movies = serializers.MovieSerializer(
            models.Movie.objects.filter(is_published=True).order_by('-created_at')[:8],
            many=True,
            context={'request': request}
        ).data
        return Response({'movies': movies}, status=status.HTTP_200_OK)


# Movie ro‘yxati
class MovieListAPIView(generics.ListAPIView):
    serializer_class = serializers.MovieSerializer
    pagination_class = MoviePagination

    def get_queryset(self):
        return models.Movie.objects.filter(is_published=True).order_by("-created_at")

# Category bo‘yicha filterlangan ro‘yxat
class MovieByCategoryAPIView(generics.ListAPIView):
    serializer_class = serializers.MovieSerializer
    pagination_class = MoviePagination
    

    def get_queryset(self):
        category_slug = self.kwargs["slug"]
        return models.Movie.objects.filter(
            is_published=True,
            categories__slug=category_slug
        ).order_by("-created_at")

# Slug bo‘yicha bitta kino
class MovieDetailAPIView(generics.RetrieveAPIView):
    serializer_class = serializers.GetMovieSerializer
    lookup_field = "slug"
    queryset = models.Movie.objects.filter(is_published=True)

# ----------------------------
# Courses API
# ----------------------------
class CourseHomepageListView(APIView):
    def get(self, request, format=None):
        courses = serializers.CourseSerializer(
            models.Course.objects.all().order_by('-created_at')[:6],
            many=True,
            context={'request': request}
        ).data
        return Response({'courses': courses}, status=status.HTTP_200_OK)

class CourseTypeAPIView(generics.ListAPIView):
    serializer_class = serializers.CourseTypeSerializer
    pagination_class = CoursePagination

    def get_queryset(self):
        course_slug = self.kwargs["course_slug"]
        return models.CourseType.objects.filter(course__slug=course_slug).order_by('id')

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        types = list(page if page is not None else qs)

        # Unauthenticated: unlock only the very first type
        user = request.user if request.user.is_authenticated else None

        # Collect all videos grouped by type
        course = get_object_or_404(models.Course, slug=self.kwargs["course_slug"])
        vids_by_type = {
            ct.id: list(models.CourseVideo.objects.filter(course=course, course_type=ct).only('id'))
            for ct in types
        }
        all_video_ids = [v.id for vids in vids_by_type.values() for v in vids]

        # Build requirement maps across all these videos
        progress_map = {}
        tests_required = set()
        passed_by_video = set()
        assignments_required = set()
        submitted_by_video = set()

        if user and all_video_ids:
            prog_qs = models.CourseVideoProgress.objects.filter(user=user, course_video_id__in=all_video_ids)\
                .values_list('course_video_id', 'completed')
            progress_map = {vid: completed for vid, completed in prog_qs}

            tests = list(models.VideoTest.objects.filter(is_active=True, course_video_id__in=all_video_ids)
                         .values('id', 'course_video_id', 'pass_score'))
            if tests:
                tests_required = {t['course_video_id'] for t in tests}
                pass_score_by_test = {t['id']: t['pass_score'] for t in tests}
                test_video_map = {t['id']: t['course_video_id'] for t in tests}
                results = list(models.TestResult.objects.filter(user=user, test_id__in=list(pass_score_by_test.keys()))
                               .values('test_id', 'score'))
                for r in results:
                    t_id = r['test_id']
                    if r['score'] is not None and pass_score_by_test.get(t_id) is not None:
                        if float(r['score']) >= float(pass_score_by_test[t_id]):
                            passed_by_video.add(test_video_map[t_id])

            assigns = list(models.VideoAssignment.objects.filter(is_active=True, course_video_id__in=all_video_ids)
                           .values('id', 'course_video_id'))
            if assigns:
                assignments_required = {a['course_video_id'] for a in assigns}
                assign_video_map = {a['id']: a['course_video_id'] for a in assigns}
                subs = list(models.AssignmentSubmission.objects.filter(assignment_id__in=list(assign_video_map.keys()), student=user)
                            .values('assignment_id'))
                for s in subs:
                    vid = assign_video_map.get(s['assignment_id'])
                    if vid:
                        submitted_by_video.add(vid)

        # CourseType-level (monthly) tests/assignments across these types
        ct_tests = []
        ct_assigns = []
        passed_types = set()
        submitted_types = set()

        if user:
            ct_tests = list(models.CourseTypeTest.objects.filter(is_active=True, course_type__in=types)
                            .values('id', 'course_type_id', 'pass_score'))
            if ct_tests:
                ct_test_ids = [t['id'] for t in ct_tests]
                pass_score_by_ct_test = {t['id']: t['pass_score'] for t in ct_tests}
                type_by_ct_test = {t['id']: t['course_type_id'] for t in ct_tests}
                results = list(models.CourseTypeTestResult.objects.filter(user=user, test_id__in=ct_test_ids)
                               .values('test_id', 'score'))
                for r in results:
                    tid = r['test_id']
                    if r['score'] is not None and float(r['score']) >= float(pass_score_by_ct_test.get(tid, 0)):
                        passed_types.add(type_by_ct_test[tid])

            ct_assigns = list(models.CourseTypeAssignment.objects.filter(is_active=True, course_type__in=types)
                               .values('id', 'course_type_id'))
            if ct_assigns:
                assign_ids = [a['id'] for a in ct_assigns]
                type_by_assign = {a['id']: a['course_type_id'] for a in ct_assigns}
                subs = list(models.CourseTypeAssignmentSubmission.objects.filter(assignment_id__in=assign_ids, student=user)
                            .values('assignment_id'))
                for s in subs:
                    submitted_types.add(type_by_assign[s['assignment_id']])

        def requirements_met(video_id: int) -> bool:
            if not progress_map.get(video_id, False):
                return False
            if video_id in tests_required and video_id not in passed_by_video:
                return False
            if video_id in assignments_required and video_id not in submitted_by_video:
                return False
            return True

        # Serialize base data
        data = serializers.CourseTypeSerializer(types, many=True, context={'request': request}).data

        # Walk types in order and mark is_locked
        prev_types_all_ok = True
        for idx, ct in enumerate(types):
            if not user:
                # only first type unlocked for anonymous
                data[idx]['is_locked'] = not (idx == 0)
                continue

            # is current locked due to previous types not completed?
            is_locked = not prev_types_all_ok
            data[idx]['is_locked'] = is_locked

            # Compute current type completion (for next types decision)
            vids = vids_by_type.get(ct.id, [])
            if vids:
                videos_ok = all(requirements_met(v.id) for v in vids)
                # For this type, if it has CT test(s)/assignment(s), require those too to consider it fully done
                type_ok = videos_ok
                # Only gate by CT requirements when they exist for this type
                has_ct_test = any(t['course_type_id'] == ct.id for t in ct_tests) if user else False
                if has_ct_test:
                    type_ok = type_ok and (ct.id in passed_types)
                has_ct_assign = any(a['course_type_id'] == ct.id for a in ct_assigns) if user else False
                if has_ct_assign:
                    type_ok = type_ok and (ct.id in submitted_types)
                prev_types_all_ok = prev_types_all_ok and type_ok
            else:
                # No videos in this type → treat as completed
                prev_types_all_ok = prev_types_all_ok and True

        if page is not None:
            return self.get_paginated_response(data)
        return Response(data)

# List courses by CourseCategory slug
class CourseByCourseCategoryAPIView(generics.ListAPIView):
    serializer_class = serializers.CourseSerializer
    pagination_class = CoursePagination

    def get_queryset(self):
        category_slug = self.kwargs["category_slug"]
        return models.Course.objects.filter(categories__slug=category_slug).order_by('-created_at')

# List course videos by course slug
class CourseVideosByCourseSlugAPIView(generics.ListAPIView):
    serializer_class = serializers.CourseVideoSerializer
    pagination_class = CoursePagination

    def get_queryset(self):
        course_slug = self.kwargs["course_slug"]
        return models.CourseVideo.objects.filter(course__slug=course_slug).order_by('order', 'created_at')

class CourseVideosByCourseSlugAndCourseTypeAPIView(generics.ListAPIView):
    serializer_class = serializers.CourseVideoSerializer
    pagination_class = CoursePagination

    def get_queryset(self):
        course_slug = self.kwargs["course_slug"]
        course_type_slug = self.kwargs["course_type_slug"]
        return models.CourseVideo.objects.filter(course__slug=course_slug, course_type__slug=course_type_slug).order_by('order', 'created_at')

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        current_items = list(page if page is not None else qs)

        # If not authenticated, everything except the very first video in the entire current type is locked
        user = request.user if request.user.is_authenticated else None

        # Gather prior CourseTypes for the same course (ordered by id)
        course_slug = self.kwargs["course_slug"]
        course_type_slug = self.kwargs["course_type_slug"]
        course = get_object_or_404(models.Course, slug=course_slug)
        all_types = list(models.CourseType.objects.filter(course=course).order_by('id'))
        cur_index = next((i for i, t in enumerate(all_types) if t.slug == course_type_slug), -1)
        prior_types = all_types[:cur_index] if cur_index > 0 else []

        # Build the universe of videos we need progress for: prior types' videos + current type's items
        prior_videos_qs = models.CourseVideo.objects.filter(course=course, course_type__in=prior_types)
        universe_videos = list(prior_videos_qs.only('id')) + current_items
        universe_ids = [v.id for v in universe_videos]

        # Maps for requirements
        progress_map = {}
        tests_required = set()
        passed_by_video = set()
        assignments_required = set()
        submitted_by_video = set()

        if user:
            # Progress completion map
            prog_qs = models.CourseVideoProgress.objects.filter(
                user=user,
                course_video_id__in=universe_ids
            ).values_list('course_video_id', 'completed')
            progress_map = {vid: completed for vid, completed in prog_qs}

            # Tests requirement and pass status
            tests = list(models.VideoTest.objects.filter(is_active=True, course_video_id__in=universe_ids)
                         .values('id', 'course_video_id', 'pass_score'))
            if tests:
                tests_required = {t['course_video_id'] for t in tests}
                test_ids = [t['id'] for t in tests]
                # Fetch user's results for these tests
                results = list(models.TestResult.objects.filter(user=user, test_id__in=test_ids)
                               .values('test_id', 'score'))
                # Build pass mapping per video: pass if any result.score >= that test's pass_score
                pass_score_by_test = {t['id']: t['pass_score'] for t in tests}
                test_video_map = {t['id']: t['course_video_id'] for t in tests}
                for r in results:
                    t_id = r['test_id']
                    if r['score'] is not None and pass_score_by_test.get(t_id) is not None:
                        if float(r['score']) >= float(pass_score_by_test[t_id]):
                            passed_by_video.add(test_video_map[t_id])

            # Assignments requirement and submission status
            assigns = list(models.VideoAssignment.objects.filter(is_active=True, course_video_id__in=universe_ids)
                           .values('id', 'course_video_id'))
            if assigns:
                assignments_required = {a['course_video_id'] for a in assigns}
                assign_ids = [a['id'] for a in assigns]
                subs = list(models.AssignmentSubmission.objects.filter(assignment_id__in=assign_ids, student=user)
                            .values('assignment_id'))
                if subs:
                    assign_video_map = {a['id']: a['course_video_id'] for a in assigns}
                    for s in subs:
                        vid = assign_video_map.get(s['assignment_id'])
                        if vid:
                            submitted_by_video.add(vid)

            # CourseType-level requirements for PRIOR types (CourseTypeTest/CourseTypeAssignment)
            ct_tests = list(models.CourseTypeTest.objects.filter(is_active=True, course_type__in=prior_types)
                            .values('id', 'course_type_id', 'pass_score'))
            passed_types = set()
            if ct_tests:
                ct_test_ids = [t['id'] for t in ct_tests]
                pass_score_by_ct_test = {t['id']: t['pass_score'] for t in ct_tests}
                type_by_ct_test = {t['id']: t['course_type_id'] for t in ct_tests}
                ct_results = list(models.CourseTypeTestResult.objects.filter(user=user, test_id__in=ct_test_ids)
                                  .values('test_id', 'score'))
                for r in ct_results:
                    tid = r['test_id']
                    if r['score'] is not None and float(r['score']) >= float(pass_score_by_ct_test.get(tid, 0)):
                        passed_types.add(type_by_ct_test[tid])
            ct_assigns = list(models.CourseTypeAssignment.objects.filter(is_active=True, course_type__in=prior_types)
                               .values('id', 'course_type_id'))
            submitted_types = set()
            if ct_assigns:
                assign_ids = [a['id'] for a in ct_assigns]
                type_by_assign = {a['id']: a['course_type_id'] for a in ct_assigns}
                ct_subs = list(models.CourseTypeAssignmentSubmission.objects.filter(assignment_id__in=assign_ids, student=user)
                               .values('assignment_id'))
                for s in ct_subs:
                    submitted_types.add(type_by_assign[s['assignment_id']])

        def requirements_met(video_id: int) -> bool:
            # Progress completed
            if not progress_map.get(video_id, False):
                return False
            # Test pass if required
            if video_id in tests_required and video_id not in passed_by_video:
                return False
            # Assignment submission if required
            if video_id in assignments_required and video_id not in submitted_by_video:
                return False
            return True

        # Check previous CourseTypes completion; if not all met, lock everything in current type
        lock_whole_type = False
        if cur_index > 0:
            prior_vid_ids = list(prior_videos_qs.values_list('id', flat=True))
            if not prior_vid_ids:
                lock_whole_type = False
            else:
                videos_ok = all(requirements_met(vid) for vid in prior_vid_ids)
                # Additionally require CourseType-level test pass and assignment submission where present
                types_ok = True
                if user:
                    for t in prior_types:
                        # if there is any active test for this type, it must be passed
                        has_test = any(getattr(x, 'course_type_id', None) == t.id for x in [])  # placeholder
                    # Re-compute has_test/has_assignment using earlier lists
                    if 'ct_tests' in locals() and ct_tests:
                        required_type_ids = {t['course_type_id'] for t in ct_tests}
                        for type_id in required_type_ids:
                            if type_id not in passed_types:
                                types_ok = False
                                break
                    if types_ok and 'ct_assigns' in locals() and ct_assigns:
                        required_assign_type_ids = {a['course_type_id'] for a in ct_assigns}
                        for type_id in required_assign_type_ids:
                            if type_id not in submitted_types:
                                types_ok = False
                                break
                lock_whole_type = not (videos_ok and types_ok)

        # Serialize base data for current items
        data = serializers.CourseVideoSerializer(current_items, many=True, context={'request': request}).data

        if lock_whole_type or not user:
            # If previous types not complete, or unauthenticated → lock all except first of very first type
            for idx in range(len(current_items)):
                data[idx]['is_locked'] = True
            # Special case: very first type and very first video is unlocked
            if user is None and cur_index == 0 and len(current_items) > 0:
                data[0]['is_locked'] = False
            elif user is not None and cur_index == 0 and len(current_items) > 0:
                # For first type, first video is always unlocked
                data[0]['is_locked'] = False
            if page is not None:
                return self.get_paginated_response(data)
            return Response(data)

        # Otherwise, apply sequential locking within current type
        prev_all_ok = True
        for idx, obj in enumerate(current_items):
            if idx == 0:
                is_locked = False
            else:
                is_locked = not prev_all_ok
            data[idx]['is_locked'] = is_locked
            # Update prev_all_ok for next item using current item's full requirements
            prev_all_ok = prev_all_ok and requirements_met(obj.id)

        if page is not None:
            return self.get_paginated_response(data)
        return Response(data)

# ----------------------------
# Reels API
# ----------------------------
class ReelHomepageListView(APIView):
    def get(self, request, format=None):
        reels = serializers.ReelSerializer(
            models.Reel.objects.all().order_by('-created_at')[:6],
            many=True,
            context={'request': request}
        ).data
        return Response({'reels': reels}, status=status.HTTP_200_OK)

# ----------------------------
# Channels API
# ----------------------------
class ChannelHomepageListView(APIView):
    def get(self, request, format=None):
        channels = serializers.ChannelAboutSerializer(
            models.Channel.objects.all().order_by('-created_at')[:8],
            many=True,
            context={'request': request}
        ).data
        return Response({'channels': channels}, status=status.HTTP_200_OK)

class ChannelAboutAPIView(APIView):
    permission_classes = [AllowAny]
    def get(self, request, slug):
        channel = get_object_or_404(models.Channel, slug=slug)
        data = serializers.ChannelAboutSerializer(channel, context={'request': request}).data
        return Response(data)

class ChannelCoursesAPIView(generics.ListAPIView):
    serializer_class = serializers.ChannelCoursesSerializer
    pagination_class = CoursePagination

    def get_queryset(self):
        slug = self.kwargs['slug']
        return models.Course.objects.filter(channel__slug=slug).order_by('-created_at')

class ChannelReelsAPIView(generics.ListAPIView):
    serializer_class = serializers.ReelSerializer
    pagination_class = ChannelPagination

    def get_queryset(self):
        slug = self.kwargs['slug']
        return models.Reel.objects.filter(channel__slug=slug).order_by('-created_at')


# ----------------------------
# Course Progress API
# ----------------------------
class CourseVideoProgressAPIView(APIView):
    """Create/Update and Get progress for a single CourseVideo for the current user."""
    permission_classes = [IsAuthenticated]

    def get(self, request, video_id):
        cv = get_object_or_404(models.CourseVideo, id=video_id)
        prog = models.CourseVideoProgress.objects.filter(user=request.user, course_video=cv).first()
        if not prog:
            # return an empty progress state
            data = {
                'id': None,
                'course_video': cv.id,
                'last_position': 0,
                'seconds_watched': 0,
                'completed': False,
                'updated_at': None,
                'created_at': None,
            }
            return Response(data)
        return Response(serializers.CourseVideoProgressSerializer(prog).data)

    def post(self, request, video_id):
        return self._upsert(request, video_id)

    def patch(self, request, video_id):
        return self._upsert(request, video_id)

    def _upsert(self, request, video_id):
        cv = get_object_or_404(models.CourseVideo, id=video_id)
        prog, _created = models.CourseVideoProgress.objects.get_or_create(user=request.user, course_video=cv)

        last_position = request.data.get('last_position')
        seconds_watched = request.data.get('seconds_watched')
        completed = request.data.get('completed')

        # Defensive casts
        if last_position is not None:
            try:
                last_position = max(0, int(float(last_position)))
            except (TypeError, ValueError):
                return Response({'error': 'last_position must be a number (seconds).'}, status=400)
            # Save exactly as provided (do not cap with previous value)
            prog.last_position = last_position

        if seconds_watched is not None:
            try:
                seconds_watched = max(0, int(float(seconds_watched)))
            except (TypeError, ValueError):
                return Response({'error': 'seconds_watched must be a number (seconds).'}, status=400)
            # Keep the max to avoid decreasing due to client-side retries
            prog.seconds_watched = max(prog.seconds_watched, seconds_watched)

        # Auto-complete if last_position close to duration
        if cv.duration:
            threshold = int(0.9 * int(cv.duration))
            if prog.last_position >= threshold:
                prog.completed = True

        # Do not downgrade completed from True to False
        if completed is not None:
            if bool(completed):
                prog.completed = True

        prog.save()
        return Response(serializers.CourseVideoProgressSerializer(prog).data, status=200)


# ----------------------------
# CourseType Test/Assignment APIs
# ----------------------------
class CreateCourseTypeTestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if getattr(request.user, 'role', 'user') not in ["teacher", "admin", "director"] and not request.user.is_superuser:
            return Response({"detail": "Permission denied"}, status=403)
        serializer = serializers.CourseTypeTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save(created_by=request.user)
        return Response({"id": obj.id}, status=201)


class StudentCourseTypeTestByTypeAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, course_type_id):
        test = models.CourseTypeTest.objects.filter(course_type_id=course_type_id, is_active=True).order_by('-created_at').first()
        if not test:
            return Response({"detail": "No active test for this course type"}, status=404)
        return Response(serializers.StudentCourseTypeTestSerializer(test).data)


class SubmitCourseTypeTestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        test_id = request.data.get('test_id')
        answers = request.data.get('answers', [])
        test = get_object_or_404(models.CourseTypeTest, id=test_id, is_active=True)

        last = models.CourseTypeTestResult.objects.filter(test=test, user=request.user).order_by('-attempt').first()
        attempt_no = (last.attempt + 1) if last else 1
        if attempt_no > test.attempts_allowed:
            return Response({"error": "Attempt limit reached"}, status=400)

        result = models.CourseTypeTestResult.objects.create(test=test, user=request.user, attempt=attempt_no)

        total_points = 0
        earned = 0
        for q in test.questions.all():
            total_points += q.points

        for item in answers:
            qid = item.get('question_id')
            oid = item.get('selected_option_id')
            question = models.CourseTypeTestQuestion.objects.filter(id=qid, test=test).first()
            if not question:
                continue
            selected = models.CourseTypeTestOption.objects.filter(id=oid, question=question).first()
            is_corr = bool(selected and selected.is_correct)
            if is_corr:
                earned += question.points
            models.CourseTypeTestAnswer.objects.create(result=result, question=question, selected_option=selected, is_correct=is_corr)

        percent = (earned / total_points * 100) if total_points else 0
        result.score = percent
        result.completed_at = timezone.now()
        result.save()

        passed = percent >= test.pass_score
        return Response({"result_id": result.id, "score_percent": round(percent,2), "passed": passed}, status=201)


class CreateCourseTypeAssignmentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if getattr(request.user, 'role', 'user') not in ["teacher", "admin", "director"] and not request.user.is_superuser:
            return Response({"detail": "Permission denied"}, status=403)
        serializer = serializers.CourseTypeAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save(created_by=request.user)
        return Response({"id": obj.id}, status=201)

class StudentCourseTypeAssignmentByTypeAPIView(APIView):
    permission_classes = [AllowAny]
    def get(self, request, course_type_id):
        assignment = models.CourseTypeAssignment.objects.filter(course_type_id=course_type_id, is_active=True).order_by('-created_at').first()
        if not assignment:
            return Response({"detail": "No active assignment for this course type"}, status=404)
        return Response(serializers.StudentCourseTypeAssignmentSerializer(assignment).data)

class SubmitCourseTypeAssignmentAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        assignment_id = request.data.get('assignment_id')
        assignment = get_object_or_404(models.CourseTypeAssignment, id=assignment_id, is_active=True)

        if not assignment.allow_multiple_submissions and models.CourseTypeAssignmentSubmission.objects.filter(assignment=assignment, student=request.user).exists():
            return Response({"error": "Submission already exists"}, status=400)

        submission = models.CourseTypeAssignmentSubmission.objects.create(
            assignment=assignment,
            student=request.user,
            text_answer=request.data.get('text_answer', ''),
            external_link=request.data.get('external_link', ''),
        )

        if 'attachment' in request.FILES:
            submission.attachment = request.FILES['attachment']
            submission.save()

        return Response({"submission_id": submission.id}, status=201)


class CourseTypeTestResultDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, result_id):
        # Allow owner or staff
        res = get_object_or_404(models.CourseTypeTestResult, id=result_id)
        if res.user_id != request.user.id and not (request.user.is_staff or request.user.is_superuser):
            return Response({"detail": "Not allowed"}, status=403)
        return Response(serializers.CourseTypeTestResultSerializer(res).data)


class MyCourseTypeTestResultsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = models.CourseTypeTestResult.objects.filter(user=request.user).order_by('-completed_at', '-started_at')
        test_id = request.query_params.get('test_id')
        ct_id = request.query_params.get('course_type_id')
        if test_id:
            qs = qs.filter(test_id=test_id)
        if ct_id:
            qs = qs.filter(test__course_type_id=ct_id)
        data = serializers.CourseTypeTestResultSerializer(qs, many=True).data
        return Response(data)


class CourseProgressAPIView(APIView):
    """Return overall progress for a course for the current user."""
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        course = get_object_or_404(models.Course, slug=slug)
        total_videos = models.CourseVideo.objects.filter(course=course).count()
        if total_videos == 0:
            payload = {
                'course_id': course.id,
                'course_slug': course.slug,
                'total_videos': 0,
                'completed_videos': 0,
                'percent': 0.0,
                'types': [],
            }
            return Response(payload)

        completed_videos = models.CourseVideoProgress.objects.filter(
            user=request.user,
            course_video__course=course,
            completed=True,
        ).count()

        # Per-CourseType breakdown for this course
        type_payload = []
        for ct in models.CourseType.objects.filter(course=course).order_by('name'):
            type_total = models.CourseVideo.objects.filter(course=course, course_type=ct).count()
            if type_total == 0:
                type_payload.append({
                    'id': ct.id,
                    'name': ct.name,
                    'slug': ct.slug,
                    'total_videos': 0,
                    'completed_videos': 0,
                    'percent': 0.0,
                })
                continue
            type_completed = models.CourseVideoProgress.objects.filter(
                user=request.user,
                course_video__course=course,
                course_video__course_type=ct,
                completed=True,
            ).count()
            type_percent = round((type_completed / type_total) * 100.0, 2)
            type_payload.append({
                'id': ct.id,
                'name': ct.name,
                'slug': ct.slug,
                'total_videos': type_total,
                'completed_videos': type_completed,
                'percent': type_percent,
            })

        percent = round((completed_videos / total_videos) * 100.0, 2)
        payload = {
            'course_id': course.id,
            'course_slug': course.slug,
            'total_videos': total_videos,
            'completed_videos': completed_videos,
            'percent': percent,
            'types': type_payload,
         }
        return Response(payload)

@api_view(['GET'])
def homepage(request):
    # return hero banners, featured movies, featured courses, reels, channels
    banners = serializers.BannerSerializer(models.Banner.objects.filter(is_active=True).order_by('position', 'order')[:10], many=True, context={'request': request}).data
    movies = serializers.MovieSerializer(models.Movie.objects.filter(is_published=True).order_by('-created_at')[:8], many=True, context={'request': request}).data
    courses = serializers.CourseSerializer(models.Course.objects.all().order_by('-created_at')[:6], many=True, context={'request': request}).data
    reels = serializers.ReelSerializer(models.Reel.objects.all().order_by('-created_at')[:6], many=True, context={'request': request}).data
    channels = serializers.ChannelSerializer(models.Channel.objects.all().order_by('-created_at')[:8], many=True, context={'request': request}).data

    return Response({
        'banners': banners,
        'movies': movies,
        'courses': courses,
        'reels': reels,
        'channels': channels,
    })

class VideoUploadAPIView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        movie_id = request.data.get("movie_id")
        if not movie_id:
            return Response({"error": "movie_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        movie = models.Movie.objects.filter(id=movie_id).first()
        if not movie:
            return Response({"error": "Movie not found"}, status=status.HTTP_404_NOT_FOUND)

        file = request.FILES.get("file")
        if not file:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)


class CourseVideoUploadAPIView(APIView):
    """CourseVideo uchun yuklash (single va chunked)."""
    parser_classes = (MultiPartParser, FormParser)

    def _save_course_video_from_path(self, course_video: models.CourseVideo, source_path: str):
        with open(source_path, "rb") as f:
            filename = os.path.basename(source_path)
            course_video.upload_file.save(filename, File(f), save=True)
        return course_video

    def post(self, request, *args, **kwargs):
        course_id = request.data.get("course_id")
        if not course_id:
            return Response({"error": "course_id is required"}, status=400)

        course = models.Course.objects.filter(id=course_id).first()
        if not course:
            return Response({"error": "Course not found"}, status=404)

        title = request.data.get("title", "")
        description = request.data.get("description", "")
        order = int(request.data.get("order", 0))

        # NOTE: Do NOT create CourseVideo here for chunked upload, since each chunk is a new request.
        # We'll only create/update the CourseVideo:
        #  - for single upload immediately
        #  - for chunked upload only when the final chunk arrives.
        video_id = request.data.get("video_id")
        course_video = None

        # Single upload
        if "file" in request.FILES and "chunkIndex" not in request.data:
            uploaded_file = request.FILES["file"]

            temp_dir = os.path.join(settings.MEDIA_ROOT, "temp_courses")
            os.makedirs(temp_dir, exist_ok=True)
            temp_file_path = os.path.join(temp_dir, f"{os.urandom(6).hex()}_{uploaded_file.name}")

            with open(temp_file_path, "wb+") as dst:
                for chunk in uploaded_file.chunks():
                    dst.write(chunk)

            # Get or create the CourseVideo (single upload)
            if video_id:
                course_video = models.CourseVideo.objects.filter(id=video_id, course=course).first()
                if not course_video:
                    return Response({"error": "CourseVideo not found"}, status=404)
                # update meta optionally
                if title:
                    course_video.title = title
                if description:
                    course_video.description = description
                if order is not None:
                    course_video.order = order
                course_video.save()
            else:
                course_video = models.CourseVideo.objects.create(
                    course=course, title=title, description=description, order=order
                )

            self._save_course_video_from_path(course_video, temp_file_path)

            redis_client.set(f"progress:course_video:{course_video.id}", "processing")
            process_course_video_task.delay(course_video.id, temp_file_path)

            return Response({"message": "File uploaded successfully", "video_id": course_video.id}, status=201)

        # Chunked upload
        if "file" in request.FILES and "chunkIndex" in request.data:
            chunk = request.FILES["file"]
            try:
                chunk_index = int(request.data["chunkIndex"])
                total_chunks = int(request.data["totalChunks"])
            except (TypeError, ValueError):
                return Response({"error": "chunkIndex and totalChunks must be integers"}, status=400)

            upload_id = request.data.get("uploadId")
            if not upload_id:
                return Response({"error": "uploadId is required for chunked upload"}, status=400)

            chunks_dir = os.path.join(settings.MEDIA_ROOT, "temp_course_chunks", upload_id)
            os.makedirs(chunks_dir, exist_ok=True)

            chunk_path = os.path.join(chunks_dir, f"chunk_{chunk_index}")
            with open(chunk_path, "wb+") as destination:
                for c in chunk.chunks():
                    destination.write(c)

            if chunk_index + 1 == total_chunks:
                temp_dir = os.path.join(settings.MEDIA_ROOT, "temp_courses")
                os.makedirs(temp_dir, exist_ok=True)
                final_temp_path = os.path.join(temp_dir, f"{upload_id}.mp4")

                with open(final_temp_path, "wb") as final_file:
                    for i in range(total_chunks):
                        part_path = os.path.join(chunks_dir, f"chunk_{i}")
                        if not os.path.exists(part_path):
                            return Response({"error": f"Missing chunk {i}"}, status=400)
                        with open(part_path, "rb") as pf:
                            shutil.copyfileobj(pf, final_file)

                for i in range(total_chunks):
                    try:
                        os.remove(os.path.join(chunks_dir, f"chunk_{i}"))
                    except FileNotFoundError:
                        pass
                try:
                    os.rmdir(chunks_dir)
                except OSError:
                    pass

                # On final chunk, now create or fetch the CourseVideo and save the file
                if video_id:
                    course_video = models.CourseVideo.objects.filter(id=video_id, course=course).first()
                    if not course_video:
                        return Response({"error": "CourseVideo not found"}, status=404)
                    # update meta optionally
                    if title:
                        course_video.title = title
                    if description:
                        course_video.description = description
                    if order is not None:
                        course_video.order = order
                    course_video.save()
                else:
                    course_video = models.CourseVideo.objects.create(
                        course=course, title=title, description=description, order=order
                    )

                self._save_course_video_from_path(course_video, final_temp_path)

                redis_client.set(f"progress:course_video:{course_video.id}", "processing")
                process_course_video_task.delay(course_video.id, final_temp_path)

                return Response({"message": "Upload completed and processing started", "video_id": course_video.id}, status=201)

            return Response({"message": f"Chunk {chunk_index+1}/{total_chunks} uploaded"}, status=200)

        return Response({"error": "No file provided"}, status=400)


class CourseVideoProcessingStatusAPIView(APIView):
    def get(self, request, video_id):
        progress = redis_client.get(f"progress:course_video:{video_id}")
        if not progress:
            return Response({"status": "unknown"}, status=404)
        return Response({"status": progress.decode("utf-8")})


class CourseVideoStreamAPIView(APIView):
    def get(self, request, video_id):
        cv = models.CourseVideo.objects.filter(id=video_id).first()
        if not cv:
            return Response({"error": "CourseVideo not found"}, status=404)
        if not cv.hls_playlist_url:
            return Response({"error": "HLS not ready"}, status=202)
        return Response({"hls_url": cv.hls_playlist_url})


class SubmitTestAPIView(APIView):
    """Foydalanuvchi javoblarini qabul qilib, natijani hisoblaydi."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        test_id = request.data.get('test_id')
        answers = request.data.get('answers', [])
        test = get_object_or_404(models.VideoTest, id=test_id, is_active=True)

        last = models.TestResult.objects.filter(test=test, user=request.user).order_by('-attempt').first()
        attempt_no = (last.attempt + 1) if last else 1
        if attempt_no > test.attempts_allowed:
            return Response({"error": "Attempt limit reached"}, status=400)

        result = models.TestResult.objects.create(test=test, user=request.user, attempt=attempt_no)

        correct = 0
        total_points = 0
        earned_points = 0
        for q in test.questions.all():
            total_points += q.points

        for item in answers:
            qid = item.get('question_id')
            oid = item.get('selected_option_id')
            question = models.TestQuestion.objects.filter(id=qid, test=test).first()
            if not question:
                continue
            selected = models.TestOption.objects.filter(id=oid, question=question).first()
            is_corr = bool(selected and selected.is_correct)
            if is_corr:
                correct += 1
                earned_points += question.points
            models.TestAnswer.objects.create(result=result, question=question, selected_option=selected, is_correct=is_corr)

        percent = (earned_points / total_points * 100) if total_points else 0
        result.score = percent
        result.completed_at = timezone.now()
        result.save()

        passed = percent >= test.pass_score
        return Response({
            "result_id": result.id,
            "score_percent": round(percent, 2),
            "correct_count": correct,
            "total_questions": test.questions.count(),
            "passed": passed
        }, status=201)


class AssignmentSubmitAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        assignment_id = request.data.get('assignment_id')
        assignment = get_object_or_404(models.VideoAssignment, id=assignment_id, is_active=True)

        if not assignment.allow_multiple_submissions and models.AssignmentSubmission.objects.filter(assignment=assignment, student=request.user).exists():
            return Response({"error": "Submission already exists"}, status=400)

        submission = models.AssignmentSubmission.objects.create(
            assignment=assignment,
            student=request.user,
            text_answer=request.data.get('text_answer', ''),
            external_link=request.data.get('external_link', ''),
        )

        if 'attachment' in request.FILES:
            submission.attachment = request.FILES['attachment']
            submission.save()

        return Response({"submission_id": submission.id}, status=201)


class AssignmentDetailAPIView(generics.RetrieveAPIView):
    """Return a single assignment by its ID (student-facing)."""
    permission_classes = [AllowAny]
    serializer_class = serializers.VideoAssignmentSerializer
    lookup_url_kwarg = 'assignment_id'
    queryset = models.VideoAssignment.objects.filter(is_active=True)


class AssignmentsByVideoIdAPIView(generics.ListAPIView):
    """List active assignments attached to a CourseVideo by video ID (student-facing)."""
    permission_classes = [AllowAny]
    serializer_class = serializers.VideoAssignmentSerializer
    pagination_class = CoursePagination

    def get_queryset(self):
        video_id = self.kwargs['video_id']
        return models.VideoAssignment.objects.filter(course_video_id=video_id, is_active=True).order_by('created_at')


class StudentTestDetailAPIView(APIView):
    """Return a test for students WITHOUT exposing correct answers."""
    permission_classes = [AllowAny]

    def get(self, request, test_id):
        test = get_object_or_404(models.VideoTest, id=test_id, is_active=True)
        data = serializers.StudentVideoTestSerializer(test).data
        return Response(data)


class StudentTestByVideoAPIView(APIView):
    """Return active test attached to a CourseVideo (student-safe)."""
    permission_classes = [AllowAny]

    def get(self, request, video_id):
        test = models.VideoTest.objects.filter(course_video_id=video_id, is_active=True).order_by('-created_at').first()
        if not test:
            return Response({"detail": "No active test for this video"}, status=404)
        return Response(serializers.StudentVideoTestSerializer(test).data)


class CreateVideoTestAPIView(APIView):
    """Teacher creates a test with questions and options (nested)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Optional role check; allow teacher/admin/director
        if getattr(request.user, 'role', 'user') not in ["teacher", "admin", "director"] and not request.user.is_superuser:
            return Response({"detail": "Permission denied"}, status=403)

        serializer = serializers.VideoTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save(created_by=request.user)
        return Response({"id": obj.id}, status=201)


class CreateVideoAssignmentAPIView(APIView):
    """Teacher creates an assignment for a CourseVideo."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Allow teacher/admin/director/superuser
        if getattr(request.user, 'role', 'user') not in ["teacher", "admin", "director"] and not request.user.is_superuser:
            return Response({"detail": "Permission denied"}, status=403)

        serializer = serializers.VideoAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save(created_by=request.user)
        return Response({"id": obj.id}, status=201)


class TestResultsListAPIView(APIView):
    """List results for a given test (teacher view)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, test_id):
        # role check
        if getattr(request.user, 'role', 'user') not in ["teacher", "admin", "director"] and not request.user.is_superuser:
            return Response({"detail": "Permission denied"}, status=403)

        test = get_object_or_404(models.VideoTest, id=test_id)
        qs = models.TestResult.objects.filter(test=test).select_related('user').order_by('-completed_at', '-started_at')
        data = serializers.TestResultListItemSerializer(qs, many=True).data
        return Response({"results": data})


class MyTestResultsAPIView(APIView):
    """List current user's results for a given test or all tests."""
    permission_classes = [IsAuthenticated]

    def get(self, request, test_id=None):
        qs = models.TestResult.objects.filter(user=request.user)
        if test_id:
            qs = qs.filter(test_id=test_id)
        qs = qs.select_related('user').order_by('-completed_at', '-started_at')
        data = serializers.TestResultListItemSerializer(qs, many=True).data
        return Response({"results": data})

class VideoProcessingStatusAPIView(APIView):
    def get(self, request, file_id):
        progress = redis_client.get(f"progress:{file_id}")
        if not progress:
            return Response({"status": "unknown"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"status": progress.decode("utf-8")})

class VideoStreamAPIView(APIView):
    def get(self, request, *args, **kwargs):
        file_id = kwargs.get('file_id')
        movie_file = models.MovieFile.objects.filter(id=file_id).first()
        if not movie_file:
            return Response({'error': 'File not found'}, status=status.HTTP_404_NOT_FOUND)

        if not movie_file.hls_playlist_url:
            return Response({'error': 'HLS playlist not available for this file'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'hls_url': movie_file.hls_playlist_url}, status=status.HTTP_200_OK)


class UnifiedUploadAPIView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def _save_movie_file_from_path(self, movie, source_path, title, quality, language_id):
        """
        source_path — to'liq yo'l (temp/final) ga olib beradi.
        Bu funksiya MovieFile obyektini yaratadi va upload_file ga saqlaydi.
        Fayl nomi sifatida faqat basename ishlatiladi.
        """
        movie_file = models.MovieFile.objects.create(
            movie=movie,
            title=title or "",
            quality=quality or "",
            language_id=language_id or None,
        )
        # ochib, storage ga saqlaymiz (name = basename, shunda Windows colon muammosi bo'lmaydi)
        with open(source_path, "rb") as f:
            filename = os.path.basename(source_path)
            movie_file.upload_file.save(filename, File(f), save=True)
        return movie_file

    def post(self, request, *args, **kwargs):
        movie_id = request.data.get("movie_id")
        quality = request.data.get("quality", "")
        language_id = request.data.get("language_id")

        if not movie_id:
            return Response({"error": "movie_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        movie = models.Movie.objects.filter(id=movie_id).first()
        if not movie:
            return Response({"error": "Movie not found"}, status=status.HTTP_404_NOT_FOUND)

        # --------------------------
        # Single (non-chunked) upload
        # --------------------------
        if "file" in request.FILES and "chunkIndex" not in request.data:
            uploaded_file = request.FILES["file"]

            # 1) temp papkaga yozamiz (ffmpeg uchun)
            temp_dir = os.path.join(settings.MEDIA_ROOT, "temp")
            os.makedirs(temp_dir, exist_ok=True)
            temp_file_path = os.path.join(temp_dir, f"{os.urandom(6).hex()}_{uploaded_file.name}")

            with open(temp_file_path, "wb+") as dst:
                for chunk in uploaded_file.chunks():
                    dst.write(chunk)

            # 2) temp fayldan modelga saqlash (upload_file -> MEDIA_ROOT/movies/files/)
            movie_file = self._save_movie_file_from_path(
                movie=movie,
                source_path=temp_file_path,
                title=request.data.get("title", ""),
                quality=quality,
                language_id=language_id,
            )

            # 3) progress va background task (task temp_file_path ni o‘chiradi)
            redis_client.set(f"progress:{movie_file.id}", "processing")
            process_video_task.delay(movie_file.id, temp_file_path)

            return Response({"message": "File uploaded successfully", "id": movie_file.id}, status=status.HTTP_201_CREATED)

        # --------------------------
        # Chunked upload
        # --------------------------
        if "file" in request.FILES and "chunkIndex" in request.data:
            chunk = request.FILES["file"]
            try:
                chunk_index = int(request.data["chunkIndex"])
                total_chunks = int(request.data["totalChunks"])
            except (TypeError, ValueError):
                return Response({"error": "chunkIndex and totalChunks must be integers"}, status=status.HTTP_400_BAD_REQUEST)

            upload_id = request.data.get("uploadId")
            if not upload_id:
                return Response({"error": "uploadId is required for chunked upload"}, status=status.HTTP_400_BAD_REQUEST)

            title = request.data.get("title", "")

            # papkalar
            chunks_dir = os.path.join(settings.MEDIA_ROOT, "temp_chunks", upload_id)
            os.makedirs(chunks_dir, exist_ok=True)

            chunk_path = os.path.join(chunks_dir, f"chunk_{chunk_index}")
            with open(chunk_path, "wb+") as destination:
                for c in chunk.chunks():
                    destination.write(c)

            # agar oxirgi chunk bo'lsa → birlashtiramiz
            if chunk_index + 1 == total_chunks:
                # final temp fayl (ffmpeg va keyin storage uchun)
                temp_dir = os.path.join(settings.MEDIA_ROOT, "temp")
                os.makedirs(temp_dir, exist_ok=True)
                final_temp_path = os.path.join(temp_dir, f"{upload_id}.mp4")

                with open(final_temp_path, "wb") as final_file:
                    for i in range(total_chunks):
                        part_path = os.path.join(chunks_dir, f"chunk_{i}")
                        if not os.path.exists(part_path):
                            # agar qism yetishmasa — xato
                            return Response({"error": f"Missing chunk {i}"}, status=status.HTTP_400_BAD_REQUEST)
                        with open(part_path, "rb") as pf:
                            shutil.copyfileobj(pf, final_file)

                # chunk fayllarini o'chirish va papkani tozalash
                for i in range(total_chunks):
                    try:
                        os.remove(os.path.join(chunks_dir, f"chunk_{i}"))
                    except FileNotFoundError:
                        pass
                try:
                    os.rmdir(chunks_dir)
                except OSError:
                    pass

                # filmni modelga saqlaymiz (upload_file)
                movie_file = self._save_movie_file_from_path(
                    movie=movie,
                    source_path=final_temp_path,
                    title=title,
                    quality=quality,
                    language_id=language_id,
                )

                redis_client.set(f"progress:{movie_file.id}", "processing")
                process_video_task.delay(movie_file.id, final_temp_path)

                return Response({"message": "Upload completed and processing started", "id": movie_file.id}, status=status.HTTP_201_CREATED)

            # agar hali barcha chunklar kelmagan bo'lsa
            return Response({"message": f"Chunk {chunk_index+1}/{total_chunks} uploaded"}, status=status.HTTP_200_OK)

        return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

class ReelUploadAPIView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

        temp_dir = os.path.join(settings.MEDIA_ROOT, "temp_reels")
        os.makedirs(temp_dir, exist_ok=True)

        temp_file_path = os.path.join(temp_dir, file.name)
        with open(temp_file_path, "wb+") as temp_file:
            for chunk in file.chunks():
                temp_file.write(chunk)
        channel = models.Channel.objects.filter(user=request.user).first()  # Chan
        reel = models.Reel.objects.create(
            title=request.data.get("title", ""),
            caption=request.data.get("caption", ""),
            upload_file=file,
            created_by=request.user if request.user.is_authenticated else None,
            channel=channel if channel else None,
        )

        redis_client.set(f"progress:reel:{reel.id}", "processing")

        process_reel_task.delay(reel.id, temp_file_path)

        return Response(
            {
                "message": "Reel uploaded. Processing in background.",
                "reel_id": reel.id,
            },
            status=status.HTTP_201_CREATED,
        )


class ReelProgressAPIView(APIView):
    def get(self, request, reel_id):
        progress = redis_client.get(f"progress:reel:{reel_id}")
        if not progress:
            return Response({"status": "not_found"}, status=404)
        return Response({"status": progress.decode("utf-8")})


class ReelStreamAPIView(APIView):
    permission_classes = [AllowAny]
    def get(self, request, *args, **kwargs):
        reel_id = kwargs.get("reel_id")
        reel = models.Reel.objects.filter(id=reel_id).first()
        if not reel:
            return Response({"error": "Reel not found"}, status=404)

        if not reel.hls_playlist_url:
            progress = redis_client.get(f"progress:reel:{reel_id}")
            return Response({
                "status": progress.decode("utf-8") if progress else "processing",
                "hls_url": None
            }, status=202)  # 202 = Processing

        return Response({
            "status": "ready",
            "hls_url": reel.hls_playlist_url
        }, status=200)


class RandomReelFeedAPIView(APIView):
    pagination_class = ReelPagination
    permission_classes = [AllowAny]

    def get(self, request):
        # seed olish
        seed = request.query_params.get("seed")
        if not seed:
            seed = str(random.randint(1, 999999))

        reels = list(
            models.Reel.objects.exclude(hls_playlist_url__isnull=True).exclude(hls_playlist_url="")
        )

        # deterministik shuffle → BIR marta tartiblanadi
        rng = random.Random(seed)
        rng.shuffle(reels)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(reels, request)

        data = []
        for r in page:
            liked = False
            if request.user.is_authenticated:
                liked = models.LikeReels.objects.filter(user=request.user, reel=r).exists()

            data.append({
                "id": r.id,
                "title": r.title,
                "caption": r.caption,
                "hls_url": r.hls_playlist_url,
                "likes_count": r.likes,
                "comments_count": r.comments.count(),
                "created_at": r.created_at,
                "liked": liked,  # ✅ yangi qo‘shildi
                "user": {
                    "username": r.channel.user.username if r.channel else "Anonymous",
                    "avatar": r.channel.avatar.url if r.channel and r.channel.avatar else None
                }
            })

        response = paginator.get_paginated_response(data)
        response.data["seed"] = seed
        return response

class CommentReelAPIView(APIView):
    # def get_permissions(self):
    #     if self.request.method == "POST":
    #         return [IsAuthenticated()]  # faqat login user yozishi mumkin
    #     return [AllowAny()]  # GET uchun hammaga ruxsat
    permission_classes = [IsAuthenticated]

    def get(self, request, reel_id):
        reel = get_object_or_404(models.Reel, id=reel_id)
        comments = models.ReelComment.objects.filter(
            reel=reel, parent__isnull=True
        ).order_by("-created_at")

        paginator = CommentPagination()
        page = paginator.paginate_queryset(comments, request)

        def serialize_comment(comment):
            return {
                "id": comment.id,
                "user": {
                    "username": comment.user.username if comment.user else "Anonymous",
                    "avatar": comment.user.avatar.url if comment.user and comment.user.avatar else None,
                },
                "text": comment.text,
                "created_at": comment.created_at,
                "replies": [
                    serialize_comment(reply)
                    for reply in comment.replies.all().order_by("created_at")
                ],
            }

        data = [serialize_comment(c) for c in page]
        return paginator.get_paginated_response(data)

    def post(self, request, reel_id):
        reel = get_object_or_404(models.Reel, id=reel_id)

        text = request.data.get("text", "").strip()
        parent_id = request.data.get("parent_id")
        if not text:
            return Response({"error": "Comment text is required"}, status=400)

        parent = None
        if parent_id:
            parent = models.ReelComment.objects.filter(id=parent_id, reel=reel).first()
            if not parent:
                return Response({"error": "Parent comment not found"}, status=404)

        comment = models.ReelComment.objects.create(
            reel=reel,
            user=request.user,
            text=text,
            parent=parent,
        )

        return Response(
            {
                "id": comment.id,
                "reel_id": reel.id,
                "parent_id": comment.parent.id if comment.parent else None,
                "user": {
                    "username": comment.user.username,
                    "avatar": comment.user.avatar.url if comment.user.avatar else None,
                },
                "text": comment.text,
                "created_at": comment.created_at,
            },
            status=201,
        )


class ReelLikeAPIView(APIView):
    permission_classes = [IsAuthenticated]  # faqat login user like qila oladi

    def post(self, request, reel_id):
        reel = get_object_or_404(models.Reel, id=reel_id)

        like, created = models.LikeReels.objects.get_or_create(
            user=request.user,
            reel=reel
        )

        if not created:
            # Agar like avval mavjud bo‘lsa, unlike qilamiz
            like.delete()
            return Response({
                "message": "Unliked",
                "likes_count": reel.likes
            }, status=200)

        return Response({
            "message": "Liked",
            "likes_count": reel.likes
        }, status=201) 