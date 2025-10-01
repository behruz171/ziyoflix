from rest_framework import serializers
from app import models
from decimal import Decimal


class ChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Channel
        fields = '__all__'


class CourseTypeBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CourseType
        fields = ('id', 'name', 'slug')


class TeacherCourseSerializer(serializers.ModelSerializer):
    course_types_count = serializers.SerializerMethodField()
    videos_count = serializers.SerializerMethodField()
    students_count = serializers.SerializerMethodField()

    class Meta:
        model = models.Course
        fields = (
            'id', 'title', 'slug', 'students_count', 'created_at', 'price','cover', 'thumbnail',
            'course_types_count', 'videos_count', 'purchase_scope'
        )

    def get_course_types_count(self, obj):
        return models.CourseType.objects.filter(course=obj).count()

    def get_videos_count(self, obj):
        return models.CourseVideo.objects.filter(course=obj).count()
    
    def get_students_count(self, obj):
        return models.WalletTransaction.objects.filter(course=obj, transaction_type='course_purchase').count()

class TeacherCourseVideoSerializer(serializers.ModelSerializer):
    course_type = CourseTypeBriefSerializer(read_only=True)
    has_test = serializers.SerializerMethodField()
    has_assignment = serializers.SerializerMethodField()
    class Meta:
        model = models.CourseVideo
        fields = (
            'id', 'title', 'order', 'duration', 'created_at', 'course_type',
            'has_test', 'has_assignment'
        )

    def get_has_test(self, obj):
        return obj.tests.filter(is_active=True).count() > 0

    def get_has_assignment(self, obj):
        return obj.assignments.filter(is_active=True).exists()


# ===== Teacher-facing test serializers (include is_correct) =====
class TeacherVideoTestOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.TestOption
        fields = ('id', 'text', 'is_correct', 'order')


class TeacherVideoTestQuestionSerializer(serializers.ModelSerializer):
    options = TeacherVideoTestOptionSerializer(many=True)

    class Meta:
        model = models.TestQuestion
        fields = ('id', 'text', 'order', 'points', 'options')


class TeacherVideoTestSerializer(serializers.ModelSerializer):
    questions = TeacherVideoTestQuestionSerializer(many=True)
    attempts = serializers.SerializerMethodField()
    pass_rate = serializers.SerializerMethodField()

    class Meta:
        model = models.VideoTest
        fields = (
            'id', 'course_video', 'title', 'description', 'time_limit_minutes',
            'attempts_allowed', 'pass_score', 'is_active', 'created_at',
            'attempts', 'pass_rate', 'questions'
        )

    def get_attempts(self, obj):
        return models.TestResult.objects.filter(test=obj).count()

    def get_pass_rate(self, obj):
        total = models.TestResult.objects.filter(test=obj).count()
        if not total:
            return 0.0
        passed = models.TestResult.objects.filter(test=obj, score__gte=obj.pass_score).count()
        return round((passed / total) * 100.0, 2)


class TeacherVideoAssignmentSerializer(serializers.ModelSerializer):
    submissions_count = serializers.SerializerMethodField()
    graded_count = serializers.SerializerMethodField()
    avg_grade = serializers.SerializerMethodField()

    class Meta:
        model = models.VideoAssignment
        fields = (
            'id', 'course_video', 'title', 'description', 'due_at', 'max_points',
            'allow_multiple_submissions', 'is_active', 'created_at',
            'submissions_count', 'graded_count', 'avg_grade'
        )

    def get_submissions_count(self, obj):
        return obj.submissions.count()

    def get_graded_count(self, obj):
        return obj.submissions.filter(grade__isnull=False).count()

    def get_avg_grade(self, obj):
        from django.db.models import Avg
        avg = obj.submissions.aggregate(a=Avg('grade'))['a']
        return float(avg) if avg is not None else None


# ===== Teacher Reels serializers =====
class TeacherReelSerializer(serializers.ModelSerializer):
    comments_count = serializers.SerializerMethodField()

    class Meta:
        model = models.Reel
        fields = (
            'id', 'title', 'caption', 'duration', 'likes', 'views', 'created_at',
            'file_url', 'hls_playlist_url', 'comments_count'
        )

    def get_comments_count(self, obj):
        return obj.comments.count()


# =============================
# Assignment Submission APIs
# =============================
class StudentBriefSerializer(serializers.ModelSerializer):
    """O'quvchi haqida qisqacha ma'lumot."""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = models.User
        fields = ('id', 'username', 'full_name', 'email', 'avatar')
        read_only_fields = ('id', 'username', 'full_name', 'email', 'avatar')
    
    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class VideoAssignmentBriefSerializer(serializers.ModelSerializer):
    """Vazifa haqida qisqacha ma'lumot."""
    course_title = serializers.CharField(source='course_video.course.title', read_only=True)
    video_title = serializers.CharField(source='course_video.title', read_only=True)
    
    class Meta:
        model = models.VideoAssignment
        fields = ('id', 'title', 'description', 'course_title', 'video_title', 'due_at', 'max_points')
        read_only_fields = ('id', 'title', 'description', 'course_title', 'video_title', 'due_at', 'max_points')


class TeacherAssignmentSubmissionSerializer(serializers.ModelSerializer):
    """O'qituvchi uchun vazifa topshiriqlarini ko'rish."""
    student = StudentBriefSerializer(read_only=True)
    assignment = VideoAssignmentBriefSerializer(read_only=True)
    is_graded = serializers.SerializerMethodField()
    is_late = serializers.SerializerMethodField()
    
    class Meta:
        model = models.AssignmentSubmission
        fields = (
            'id', 'student', 'assignment', 'text_answer', 'attachment', 
            'external_link', 'submitted_at', 'grade', 'feedback', 
            'graded_by', 'is_graded', 'is_late'
        )
        read_only_fields = (
            'id', 'student', 'assignment', 'text_answer', 'attachment',
            'external_link', 'submitted_at', 'is_graded', 'is_late'
        )
    
    def get_is_graded(self, obj):
        """Baholangan yoki yo'qligini tekshirish."""
        return obj.grade is not None
    
    def get_is_late(self, obj):
        """Muddatdan kech topshirilgan yoki yo'qligini tekshirish."""
        if obj.assignment.due_at:
            return obj.submitted_at > obj.assignment.due_at
        return False


class GradeAssignmentSerializer(serializers.Serializer):
    """Vazifani baholash uchun."""
    grade = serializers.FloatField(min_value=0)
    feedback = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    
    def validate_grade(self, value):
        # Assignment max_points ni tekshirish
        assignment_submission = self.context.get('assignment_submission')
        if assignment_submission and value > assignment_submission.assignment.max_points:
            raise serializers.ValidationError(
                f"Grade cannot exceed {assignment_submission.assignment.max_points} points"
            )
        return value


class AssignmentSubmissionStatsSerializer(serializers.Serializer):
    """Vazifa topshiriqlar statistikasi."""
    total_submissions = serializers.IntegerField()
    graded_submissions = serializers.IntegerField()
    ungraded_submissions = serializers.IntegerField()
    average_grade = serializers.FloatField(allow_null=True)
    late_submissions = serializers.IntegerField()
    on_time_submissions = serializers.IntegerField()