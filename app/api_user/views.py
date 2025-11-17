from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Sum, Avg
from django.utils import timezone

from app import models
from . import serializers
from app.api.wallet_serializers import WalletSerializer, WalletTransactionSerializer


def ensure_student(user):
    # Treat role 'user' as student; allow others to call but primarily intended for students
    return getattr(user, 'role', 'user') == 'user'


class UserOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # Video progress
        progress_qs = models.CourseVideoProgress.objects.filter(user=user)
        videos_watched = progress_qs.values('course_video_id').distinct().count()
        seconds_watched = int(progress_qs.aggregate(s=Sum('seconds_watched'))['s'] or 0)
        # Tests
        test_results = models.TestResult.objects.filter(user=user)
        ct_test_results = models.CourseTypeTestResult.objects.filter(user=user)
        tests_attempts = test_results.count() + ct_test_results.count()
        avg1 = test_results.aggregate(a=Avg('score'))['a'] or 0
        avg2 = ct_test_results.aggregate(a=Avg('score'))['a'] or 0
        denom = (1 if test_results.exists() else 0) + (1 if ct_test_results.exists() else 0)
        avg_test_score = round(((avg1 + avg2) / denom), 2) if denom else None
        # Assignments
        assignments_submitted = models.AssignmentSubmission.objects.filter(student=user).count() \
                               + models.CourseTypeAssignmentSubmission.objects.filter(student=user).count()
        # Likes
        liked_reels = models.LikeReels.objects.filter(user=user).count()
        # Comments (sum across comment models)
        comments_count = (
            models.MovieComment.objects.filter(user=user).count() +
            models.CourseVideoComment.objects.filter(user=user).count() +
            models.ReelComment.objects.filter(user=user).count() +
            models.ChannelComment.objects.filter(user=user).count() +
            models.PlaylistComment.objects.filter(user=user).count()
        )
        # Playlists
        playlists_count = models.Playlist.objects.filter(owner=user).count()
        # Wallet
        wallet, _ = models.Wallet.objects.get_or_create(user=user)

        data = serializers.OverviewStatsSerializer({
            'videos_watched': videos_watched,
            'seconds_watched': seconds_watched,
            'tests_attempts': tests_attempts,
            'avg_test_score': avg_test_score,
            'assignments_submitted': assignments_submitted,
            'liked_reels': liked_reels,
            'comments_count': comments_count,
            'playlists_count': playlists_count,
            'wallet_balance': wallet.balance,
        }).data
        return Response({'is_student': ensure_student(user), 'stats': data}, status=200)


class UserVideoLessonsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = (
            models.CourseVideoProgress.objects
            .filter(user=user)
            .select_related('course_video__course')
            .order_by('-updated_at')[:100]
        )
        items = []
        for p in qs:
            cv = p.course_video
            items.append({
                'video_id': cv.id,
                'video_title': cv.title,
                'course_id': cv.course_id,
                'course_title': getattr(cv.course, 'title', ''),
                'completed': p.completed,
                'seconds_watched': p.seconds_watched,
                'updated_at': p.updated_at,
            })
        return Response({'items': items}, status=200)


class UserSavedPlaylistsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = models.Playlist.objects.filter(owner=user).annotate(
            movies_count=Count('movies'),
            course_videos_count=Count('course_videos'),
            reels_count=Count('reels')
        ).order_by('-created_at')
        data = serializers.PlaylistBriefSerializer(qs, many=True).data
        return Response({'playlists': data}, status=200)


class UserSavedReelsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        saves = (
            models.ReelSave.objects
            .filter(user=user)
            .select_related('reel')
            .order_by('-created_at')[:200]
        )
        items = []
        for s in saves:
            r = s.reel
            items.append({
                'save_id': s.id,
                'saved_at': s.created_at,
                'reel_id': r.id,
                'title': r.title,
                'poster': r.poster.url if r.poster else None,
                'duration': r.duration,
                'file_url': r.file_url,
                'hls_playlist_url': r.hls_playlist_url,
            })
        return Response({'saved_reels': items}, status=200)


class UserLikesCommentsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        likes = list(models.LikeReels.objects.filter(user=user).values('id', 'reel_id', 'reel__poster', 'created_at').order_by('-created_at')[:100])
        # Latest comments across all comment models
        comments = []
        for m, key in [
            (models.MovieComment, 'movie_id'),
            (models.CourseVideoComment, 'course_video_id'),
            (models.ReelComment, 'reel_id'),
            (models.ChannelComment, 'channel_id'),
            (models.PlaylistComment, 'playlist_id'),
        ]:
            for c in m.objects.filter(user=user).order_by('-created_at')[:20].values('id', 'text', 'created_at', key):
                item = dict(c)
                item['target_field'] = key
                comments.append(item)
        comments.sort(key=lambda x: x['created_at'], reverse=True)
        comments = comments[:100]
        return Response({'likes': likes, 'comments': comments}, status=200)


class UserSubmittedAssignmentsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        video_subs = models.AssignmentSubmission.objects.filter(student=user).select_related('assignment').order_by('-submitted_at')
        ct_subs = models.CourseTypeAssignmentSubmission.objects.filter(student=user).select_related('assignment').order_by('-submitted_at')
        items = []
        for s in video_subs:
            items.append({
                'id': s.id,
                'type': 'video',
                'title': s.assignment.title,
                'grade': s.grade,
                'submitted_at': s.submitted_at,
            })
        for s in ct_subs:
            items.append({
                'id': s.id,
                'type': 'course_type',
                'title': s.assignment.title,
                'grade': s.grade,
                'submitted_at': s.submitted_at,
            })
        items.sort(key=lambda x: x['submitted_at'], reverse=True)
        return Response({'submissions': items}, status=200)


class UserSubmittedAssignmentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id: int):
        user = request.user
        # Try video assignment submission first
        sub = (
            models.AssignmentSubmission.objects
            .filter(id=id, student=user)
            .select_related('assignment__course_video__course', 'graded_by')
            .first()
        )
        sub_type = 'video'
        if not sub:
            ct_sub = (
                models.CourseTypeAssignmentSubmission.objects
                .filter(id=id, student=user)
                .select_related('assignment__course_type__course', 'graded_by')
                .first()
            )
            if not ct_sub:
                return Response({'detail': 'Topilmadi'}, status=404)
            sub = ct_sub
            sub_type = 'course_type'

        if sub_type == 'video':
            a = sub.assignment
            cv = a.course_video
            course = getattr(cv, 'course', None)
            data = {
                'id': sub.id,
                'type': 'video',
                'submitted_at': sub.submitted_at,
                'grade': sub.grade,
                'feedback': sub.feedback,
                'graded_by': getattr(sub.graded_by, 'username', None),
                'text_answer': sub.text_answer,
                'attachment': sub.attachment.url if sub.attachment else None,
                'external_link': sub.external_link,
                'assignment': {
                    'id': a.id,
                    'title': a.title,
                    'description': a.description,
                    'due_at': a.due_at,
                    'max_points': a.max_points,
                    'allow_multiple_submissions': a.allow_multiple_submissions,
                    'due_days_after_completion': a.due_days_after_completion,
                    'is_active': a.is_active,
                },
                'course_video': {
                    'id': getattr(cv, 'id', None),
                    'title': getattr(cv, 'title', ''),
                    'course_id': getattr(course, 'id', None) if course else None,
                    'course_title': getattr(course, 'title', '') if course else '',
                },
            }
        else:
            a = sub.assignment
            ct = a.course_type
            course = getattr(ct, 'course', None)
            data = {
                'id': sub.id,
                'type': 'course_type',
                'submitted_at': sub.submitted_at,
                'grade': sub.grade,
                'feedback': sub.feedback,
                'graded_by': getattr(sub.graded_by, 'username', None),
                'text_answer': sub.text_answer,
                'attachment': sub.attachment.url if sub.attachment else None,
                'external_link': sub.external_link,
                'assignment': {
                    'id': a.id,
                    'title': a.title,
                    'description': a.description,
                    'due_at': a.due_at,
                    'max_points': a.max_points,
                    'allow_multiple_submissions': a.allow_multiple_submissions,
                    'due_days_after_completion': a.due_days_after_completion,
                    'is_active': a.is_active,
                },
                'course_type': {
                    'id': getattr(ct, 'id', None),
                    'name': getattr(ct, 'name', ''),
                    'slug': getattr(ct, 'slug', ''),
                    'course_id': getattr(course, 'id', None) if course else None,
                    'course_title': getattr(course, 'title', '') if course else '',
                    'course_slug': getattr(course, 'slug', '') if course else '',
                },
            }

        return Response(data, status=200)

class UserPurchasesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # Courses purchased fully
        course_txs = (
            models.WalletTransaction.objects
            .filter(wallet__user=user, transaction_type='course_purchase')
            .select_related('course')
            .order_by('-created_at')
        )
        courses = []
        seen_course_ids = set()
        for tx in course_txs:
            if tx.course and tx.course_id not in seen_course_ids:
                seen_course_ids.add(tx.course_id)
                courses.append({
                    'course_id': tx.course_id,
                    'course_thumbnail': tx.course.thumbnail.url if tx.course.thumbnail else None,
                    'course_cover': tx.course.cover.url if tx.course.cover else None,
                    'course_slug': tx.course.slug,
                    'title': tx.course.title,
                    'purchased_at': tx.created_at,
                })

        # Course types purchased individually
        type_txs = (
            models.WalletTransaction.objects
            .filter(wallet__user=user, transaction_type='course_type_purchase')
            .select_related('course_type', 'course')
            .order_by('-created_at')
        )
        course_types = []
        seen_type_ids = set()
        for tx in type_txs:
            if tx.course_type and tx.course_type_id not in seen_type_ids:
                seen_type_ids.add(tx.course_type_id)
                course_types.append({
                    'course_type_thumbnail': tx.course.thumbnail.url if tx.course.thumbnail else None,
                    'course_type_cover': tx.course.cover.url if tx.course.cover else None,
                    'course_type_id': tx.course_type_id,
                    'name': tx.course_type.name,
                    'course_type_slug': tx.course_type.slug,
                    'course_id': tx.course_id,
                    'course_slug': tx.course.slug,
                    'course_title': tx.course.title if tx.course else '',
                    'purchased_at': tx.created_at,
                })

        return Response({'courses': courses, 'course_types': course_types}, status=200)


class UserTestResultsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # Video tests
        v_results = (
            models.TestResult.objects
            .filter(user=user)
            .select_related('test')
            .order_by('-completed_at')[:200]
        )
        items = []
        for r in v_results:
            pass_score = r.test.pass_score if r.test else None
            is_passed = (r.score is not None and pass_score is not None and float(r.score) >= float(pass_score))
            items.append({
                'type': 'video',
                'result_id': r.id,
                'test_id': r.test_id,
                'score': r.score,
                'pass_score': pass_score,
                'is_passed': is_passed,
                'attempt': r.attempt,
                'started_at': r.started_at,
                'completed_at': r.completed_at,
            })

        # CourseType tests
        ct_results = (
            models.CourseTypeTestResult.objects
            .filter(user=user)
            .select_related('test')
            .order_by('-completed_at')[:200]
        )
        for r in ct_results:
            pass_score = r.test.pass_score if r.test else None
            is_passed = (r.score is not None and pass_score is not None and float(r.score) >= float(pass_score))
            items.append({
                'type': 'course_type',
                'result_id': r.id,
                'test_id': r.test_id,
                'score': r.score,
                'pass_score': pass_score,
                'is_passed': is_passed,
                'attempt': r.attempt,
                'started_at': r.started_at,
                'completed_at': r.completed_at,
            })

        items.sort(key=lambda x: (x['completed_at'] or x['started_at']), reverse=True)
        return Response({'results': items}, status=200)


class UserTestResultDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id: int):
        user = request.user
        # Try video test result first
        result = models.TestResult.objects.filter(id=id, user=user).select_related('test__course_video').first()
        result_type = 'video'
        if not result:
            # Try course type test result
            ct_result = models.CourseTypeTestResult.objects.filter(id=id, user=user).select_related('test__course_type').first()
            if not ct_result:
                return Response({'detail': 'Natija topilmadi'}, status=404)
            result = ct_result
            result_type = 'course_type'

        data = {
            'result_id': result.id,
            'type': result_type,
            'test_id': result.test_id,
            'score': result.score,
            'attempt': result.attempt,
            'started_at': result.started_at,
            'completed_at': result.completed_at,
        }

        if result_type == 'video':
            test = result.test
            data['test_title'] = getattr(test, 'title', '')
            data['course_video'] = {
                'id': getattr(test.course_video, 'id', None) if test else None,
                'title': getattr(test.course_video, 'title', '') if test and test.course_video else '',
            }
            # Build per-question details
            qset = models.TestQuestion.objects.filter(test=test).order_by('order', 'id')
            answers = {a.question_id: a for a in models.TestAnswer.objects.filter(result=result).select_related('selected_option')}
            items = []
            for q in qset:
                opts = list(models.TestOption.objects.filter(question=q).order_by('order', 'id'))
                selected_id = answers.get(q.id).selected_option_id if q.id in answers else None
                correct_ids = {o.id for o in opts if o.is_correct}
                is_correct = (selected_id in correct_ids) if selected_id else False
                items.append({
                    'question_id': q.id,
                    'text': q.text,
                    'order': q.order,
                    'selected_option_id': selected_id,
                    'is_correct': is_correct,
                    'options': [
                        {
                            'id': o.id,
                            'text': o.text,
                            'is_correct': o.is_correct,
                            'is_selected': (o.id == selected_id),
                        } for o in opts
                    ]
                })
            data['questions'] = items
        else:
            test = result.test
            data['test_title'] = getattr(test, 'title', '')
            data['course_type'] = {
                'id': getattr(test.course_type, 'id', None) if test else None,
                'name': getattr(test.course_type, 'name', '') if test and test.course_type else '',
            }
            qset = models.CourseTypeTestQuestion.objects.filter(test=test).order_by('order', 'id')
            answers = {a.question_id: a for a in models.CourseTypeTestAnswer.objects.filter(result=result).select_related('selected_option')}
            items = []
            for q in qset:
                opts = list(models.CourseTypeTestOption.objects.filter(question=q).order_by('order', 'id'))
                selected_id = answers.get(q.id).selected_option_id if q.id in answers else None
                correct_ids = {o.id for o in opts if o.is_correct}
                is_correct = (selected_id in correct_ids) if selected_id else False
                items.append({
                    'question_id': q.id,
                    'text': q.text,
                    'order': q.order,
                    'selected_option_id': selected_id,
                    'is_correct': is_correct,
                    'options': [
                        {
                            'id': o.id,
                            'text': o.text,
                            'is_correct': o.is_correct,
                            'is_selected': (o.id == selected_id),
                        } for o in opts
                    ]
                })
            data['questions'] = items

        return Response(data, status=200)

class UserCertificatesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Placeholder: no certificate model in current codebase
        return Response({'certificates': []}, status=200)


class UserWalletAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        wallet, _ = models.Wallet.objects.get_or_create(user=request.user)
        wallet_data = WalletSerializer(wallet).data
        tx = models.WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')[:50]
        tx_data = WalletTransactionSerializer(tx, many=True).data
        return Response({'wallet': wallet_data, 'transactions': tx_data}, status=200)


class UserSettingsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(serializers.UserProfileSerializer(request.user).data, status=200)

    def patch(self, request):
        ser = serializers.UserProfileSerializer(instance=request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data, status=200)
