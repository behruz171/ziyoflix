from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Avg, Count, Q
from django.utils import timezone

from app import models
from .serializers import (
    TeacherAssignmentSubmissionSerializer, GradeAssignmentSerializer,
    AssignmentSubmissionStatsSerializer
)


class TeacherAssignmentSubmissionsAPIView(APIView):
    """O'qituvchi uchun vazifa topshiriqlarini ko'rish."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Faqat o'qituvchi kanallariga tegishli vazifalar
        teacher_channels = models.Channel.objects.filter(user=request.user)
        
        # Barcha vazifa topshiriqlarini olish
        submissions = models.AssignmentSubmission.objects.filter(
            assignment__course_video__course__channel__in=teacher_channels
        ).select_related(
            'student', 'assignment', 'assignment__course_video', 
            'assignment__course_video__course', 'graded_by'
        ).order_by('-submitted_at')
        
        # Filtrlash
        assignment_id = request.query_params.get('assignment_id')
        if assignment_id:
            submissions = submissions.filter(assignment_id=assignment_id)
        
        course_id = request.query_params.get('course_id')
        if course_id:
            submissions = submissions.filter(assignment__course_video__course_id=course_id)
        
        graded = request.query_params.get('graded')  # true/false
        if graded is not None:
            if graded.lower() == 'true':
                submissions = submissions.filter(grade__isnull=False)
            elif graded.lower() == 'false':
                submissions = submissions.filter(grade__isnull=True)
        
        # Pagination
        limit = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))
        
        total_count = submissions.count()
        submissions = submissions[offset:offset + limit]
        
        serializer = TeacherAssignmentSubmissionSerializer(submissions, many=True)
        
        return Response({
            'submissions': serializer.data,
            'count': len(serializer.data),
            'total_count': total_count,
            'has_more': offset + limit < total_count
        })


class TeacherAssignmentSubmissionDetailAPIView(APIView):
    """Bitta vazifa topshiriqni batafsil ko'rish."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, submission_id):
        # Faqat o'qituvchi kanallariga tegishli vazifalar
        teacher_channels = models.Channel.objects.filter(user=request.user)
        
        submission = get_object_or_404(
            models.AssignmentSubmission.objects.select_related(
                'student', 'assignment', 'assignment__course_video',
                'assignment__course_video__course', 'graded_by'
            ),
            id=submission_id,
            assignment__course_video__course__channel__in=teacher_channels
        )
        
        serializer = TeacherAssignmentSubmissionSerializer(submission)
        return Response(serializer.data)


class GradeAssignmentSubmissionAPIView(APIView):
    """Vazifa topshiriqni baholash."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, submission_id, channel_slug):
        # Faqat o'qituvchi kanallariga tegishli vazifalar
        # teacher_channels = models.Channel.objects.filter(user=request.user)
        teacher_channels = models.Channel.objects.get(slug=channel_slug)
        
        submission = get_object_or_404(
            models.AssignmentSubmission,
            id=submission_id,
            assignment__course_video__course__channel=teacher_channels
        )
        
        serializer = GradeAssignmentSerializer(
            data=request.data,
            context={'assignment_submission': submission}
        )
        
        if serializer.is_valid():
            # Bahoni saqlash
            submission.grade = serializer.validated_data['grade']
            submission.feedback = serializer.validated_data.get('feedback', '')
            submission.graded_by = request.user
            submission.save()
            
            # Yangilangan ma'lumotlarni qaytarish
            response_serializer = TeacherAssignmentSubmissionSerializer(submission)
            
            return Response({
                'success': True,
                'message': 'Vazifa muvaffaqiyatli baholandi',
                'submission': response_serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AssignmentSubmissionStatsAPIView(APIView):
    """Vazifa topshiriqlar statistikasi."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Faqat o'qituvchi kanallariga tegishli vazifalar
        teacher_channels = models.Channel.objects.filter(user=request.user)
        
        submissions = models.AssignmentSubmission.objects.filter(
            assignment__course_video__course__channel__in=teacher_channels
        )
        
        # Filtrlash (ixtiyoriy)
        assignment_id = request.query_params.get('assignment_id')
        if assignment_id:
            submissions = submissions.filter(assignment_id=assignment_id)
        
        course_id = request.query_params.get('course_id')
        if course_id:
            submissions = submissions.filter(assignment__course_video__course_id=course_id)
        
        # Statistikalar
        total_submissions = submissions.count()
        graded_submissions = submissions.filter(grade__isnull=False).count()
        ungraded_submissions = total_submissions - graded_submissions
        
        # O'rtacha baho
        average_grade = submissions.filter(grade__isnull=False).aggregate(
            avg=Avg('grade'))['avg']
        
        # Kech topshirilgan vazifalar
        late_submissions = 0
        on_time_submissions = 0
        
        for submission in submissions.select_related('assignment'):
            if submission.assignment.due_at:
                if submission.submitted_at > submission.assignment.due_at:
                    late_submissions += 1
                else:
                    on_time_submissions += 1
            else:
                on_time_submissions += 1  # Muddat yo'q bo'lsa, o'z vaqtida deb hisoblaymiz
        
        stats_data = {
            'total_submissions': total_submissions,
            'graded_submissions': graded_submissions,
            'ungraded_submissions': ungraded_submissions,
            'average_grade': round(average_grade, 2) if average_grade else None,
            'late_submissions': late_submissions,
            'on_time_submissions': on_time_submissions
        }
        
        serializer = AssignmentSubmissionStatsSerializer(stats_data)
        return Response(serializer.data)


class TeacherAssignmentsByVideoAPIView(APIView):
    """Video bo'yicha vazifalarni ko'rish."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, video_id):
        # Faqat o'qituvchi kanallariga tegishli videolar
        teacher_channels = models.Channel.objects.filter(user=request.user)
        
        video = get_object_or_404(
            models.CourseVideo,
            id=video_id,
            course__channel__in=teacher_channels
        )
        
        # Video uchun vazifalar
        assignments = models.VideoAssignment.objects.filter(
            course_video=video
        ).prefetch_related('submissions')
        
        assignments_data = []
        for assignment in assignments:
            submissions = assignment.submissions.all()
            assignments_data.append({
                'id': assignment.id,
                'title': assignment.title,
                'description': assignment.description,
                'due_at': assignment.due_at,
                'max_points': assignment.max_points,
                'submissions_count': submissions.count(),
                'graded_count': submissions.filter(grade__isnull=False).count(),
                'ungraded_count': submissions.filter(grade__isnull=True).count()
            })
        
        return Response({
            'video': {
                'id': video.id,
                'title': video.title,
                'course_title': video.course.title
            },
            'assignments': assignments_data
        })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_assignment_submission(request, submission_id):
    """Vazifa topshiriqni o'chirish (faqat o'qituvchi)."""
    teacher_channels = models.Channel.objects.filter(user=request.user)
    
    submission = get_object_or_404(
        models.AssignmentSubmission,
        id=submission_id,
        assignment__course_video__course__channel__in=teacher_channels
    )
    
    submission.delete()
    
    return Response({
        'success': True,
        'message': 'Vazifa topshiriqi o\'chirildi'
    }, status=status.HTTP_200_OK)
