from rest_framework import serializers
from .. import models
from collections import defaultdict
from django.db.models import Avg, Max
from django.db.models.functions import Coalesce
from django.urls import reverse

class BannerSerializer(serializers.ModelSerializer):
    target_url = serializers.SerializerMethodField()

    class Meta:
        model = models.Banner
        fields = ('id', 'title', 'image', 'image_mobile', 'image_tablet', 'alt_text', 'position', 'order', 'start_at', 'end_at', 'is_active', 'target_url')

    def get_target_url(self, obj):
        return obj.get_target_url()


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Category
        fields = ["id", "name", "slug", "description", 'category_img', 'category_banner']

class CourseCategorySerializer(serializers.ModelSerializer):
    course_count = serializers.SerializerMethodField()

    class Meta:
        model = models.CourseCategory
        fields = ["id", "name", "slug", "description", 'category_img', 'category_banner', 'color', 'course_count']

    def get_course_count(self, obj):
        return int(obj.courses.count())

class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Language
        fields = ['id', 'name', 'code']

class MovieSerializer(serializers.ModelSerializer):
    files_count = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    max_season = serializers.SerializerMethodField()
    categories_list = CategorySerializer(many=True, read_only=True, source='categories')
    class Meta:
        model = models.Movie
        fields = (
            "id", "title", "slug", "poster", "cover", "description",
            "release_date", "duration", "type", "categories",
            "created_date", "director", "actors", "country",
            "files_count", "average_rating", "max_season",
            "categories_list"
        )
        read_only_fields = (
            "id", "files_count", "average_rating", "max_season", "created_date", "categories_list"
        )

    def get_files_count(self, obj):
        
        return obj.files.count()

    def get_average_rating(self, obj):
        avg = obj.ratings.aggregate(avg=Avg("value"))["avg"]
        return round(avg, 1) if avg else None
    
    def get_max_season(self, obj):
        return obj.files.aggregate(max_season=Max("season"))["max_season"] or 0

class GetMovieFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MovieFile
        fields = [
            "id", "title", "file_url", "upload_file", "quality",
            "language", "is_trailer", "duration",
            "hls_playlist_url", "hls_segment_path",
            "season", "episode", "created_at"
        ]

class GetMovieSerializer(serializers.ModelSerializer):
    categories = serializers.SlugRelatedField(
        many=True, slug_field="name", read_only=True
    )
    grouped_files = serializers.SerializerMethodField()  # 🔹 qo‘shildi
    languages_list = LanguageSerializer(many=True, read_only=True, source='languages')
    class Meta:
        model = models.Movie
        fields = [
            "id", "title", "slug", "description", "release_date", "duration",
            "director", "actors", "created_date", "country",
            "poster", "cover", "categories", "languages", "languages_list", "subtitles",
            "channels", "is_published", "created_at", "type",
            "grouped_files",  # oddiy `files` o‘rniga shu
        ]
        read_only_fields = ("id", "created_at", "grouped_files")

    def get_grouped_files(self, obj):
        files = obj.files.all().order_by("season", "episode")
        grouped = defaultdict(list)

        for f in files:
            grouped[f.season or 0].append(GetMovieFileSerializer(f).data)

        # dictionary → array format (season raqam bilan)
        result = []
        for season, episodes in grouped.items():
            result.append({
                "season": season,
                "episodes": episodes
            })
        return result
class ChannelCardSerializer(serializers.ModelSerializer):
    subscriber_count = serializers.SerializerMethodField()
    videos_count = serializers.SerializerMethodField()
    reels_count = serializers.SerializerMethodField()
    rating_avg = serializers.SerializerMethodField()
    is_subscribed = serializers.SerializerMethodField()
    class Meta:
        model = models.Channel
        fields = (
            'id', 'title', 'slug', 'description', 'avatar', 'banner', 'verified', 'badge',
            'subscriber_count', 'videos_count', 'reels_count', 'rating_avg', 'is_subscribed'
        )

        read_only_fields = (
            'id', 'subscriber_count', 'videos_count', 'reels_count', 'rating_avg', 'is_subscribed'
        )

    def get_subscriber_count(self, obj):
        return obj.subscribers.count()

    def get_videos_count(self, obj):
        # All course videos across this channel's courses
        return models.CourseVideo.objects.filter(course__channel=obj).count()

    def get_reels_count(self, obj):
        return obj.reels.count()

    def get_rating_avg(self, obj):
        avg = obj.ratings.aggregate(avg=Avg('value'))['avg']
        return round(avg, 1) if avg else None

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            return obj.subscribers.filter(pk=user.pk).exists()
        return False

    def get_is_subscripted(self, obj):
        # Alias for the same value
        return self.get_is_subscribed(obj)


class ChannelDetailSerializer(serializers.ModelSerializer):
    subscriber_count = serializers.SerializerMethodField()
    videos_count = serializers.SerializerMethodField()
    reels_count = serializers.SerializerMethodField()
    rating_avg = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    is_subscribed = serializers.SerializerMethodField()
    is_subscripted = serializers.SerializerMethodField()
    class Meta:
        model = models.Channel
        fields = (
            'id', 'title', 'slug', 'description', 'avatar', 'banner', 'verified', 'badge',
            'subscriber_count', 'videos_count', 'reels_count', 'rating_avg', 'created_at', 'username', 'is_subscribed', 'is_subscripted'
        )
        read_only_fields = ('id', 'created_at', 'subscriber_count', 'videos_count', 'reels_count', 'rating_avg', 'username', 'is_subscribed', 'is_subscripted')

    def get_subscriber_count(self, obj):
        return obj.subscribers.count()

    def get_videos_count(self, obj):
        return models.CourseVideo.objects.filter(course__channel=obj).count()

    def get_reels_count(self, obj):
        return obj.reels.count()

    def get_rating_avg(self, obj):
        avg = obj.ratings.aggregate(avg=Avg('value'))['avg']
        return round(avg, 1) if avg else None

    def get_username(self, obj):
        return getattr(obj.user, 'username', '')

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            return obj.subscribers.filter(pk=user.pk).exists()
        return False

    def get_is_subscripted(self, obj):
        # Alias for the same value
        return self.get_is_subscribed(obj)


class ChannelAboutSerializer(serializers.ModelSerializer):
    subscriber_count = serializers.SerializerMethodField()
    rating_avg = serializers.SerializerMethodField()
    is_subscribed = serializers.SerializerMethodField()
    class Meta:
        model = models.Channel
        fields = (
            'id', 'title', 'slug', 'description', 'avatar', 'banner', 'verified', 'badge',
            'website', 'telegram', 'instagram', 'github', 'linkedin',
            'location_country', 'location_city', 'years_experience',
            'subscriber_count', 'rating_avg', 'is_subscribed', 'created_at'
        )

    def get_subscriber_count(self, obj):
        return obj.subscribers.count()

    def get_rating_avg(self, obj):
        avg = obj.ratings.aggregate(avg=Avg('value'))['avg']
        return round(avg, 1) if avg else None
    
    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            return obj.subscribers.filter(pk=user.pk).exists()
        return False

class ChannelCoursesSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Course
        fields = (
            'id', 'title', 'slug', 'description', 'language', 'is_free', 'price',
            'level', 'is_new', 'is_bestseller', 'is_serial', 'certificate_available',
            'students_count', 'rating_avg', 'rating_count', 'lessons_count', 'total_duration_minutes',
            'thumbnail', 'cover','channel',
        )


class CourseSerializer(serializers.ModelSerializer):
    channel_info = ChannelCardSerializer(read_only=True, source='channel')
    is_purchased = serializers.SerializerMethodField()

    class Meta:
        model = models.Course
        fields = (
            'id', 'title', 'slug', 'description', 'language', 'is_free', 'price',
            'level', 'is_new', 'is_bestseller', 'is_serial', 'certificate_available',
            'students_count', 'rating_avg', 'rating_count', 'lessons_count', 'total_duration_minutes',
            'thumbnail', 'cover', 'channel', 'channel_info', 'categories', 'language', 'purchase_scope', 'is_purchased'
        )
        read_only_fields = (
            'id', 'created_at', 'channel_info'
        )

    def get_is_purchased(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        scope = getattr(obj, 'purchase_scope', 'course')
        if scope == 'course':
            return models.WalletTransaction.objects.filter(
                wallet__user=user,
                course=obj,
                transaction_type='course_purchase'
            ).exists()
        # scope == 'course_type': any type purchase under this course counts
        return models.WalletTransaction.objects.filter(
            wallet__user=user,
            course=obj,
            transaction_type='course_type_purchase'
        ).exists()


class CourseVideoProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CourseVideoProgress
        fields = (
            'id', 'course_video', 'last_position', 'seconds_watched', 'completed', 'updated_at', 'created_at'
        )
        read_only_fields = ('updated_at', 'created_at')


class CourseProgressSerializer(serializers.Serializer):
    course_id = serializers.IntegerField()
    course_slug = serializers.CharField()
    total_videos = serializers.IntegerField()
    completed_videos = serializers.IntegerField()
    percent = serializers.FloatField()

# ===== CourseType Test/Assignment serializers =====
class CTTestOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CourseTypeTestOption
        fields = ('id', 'text', 'is_correct', 'order')


class CTTestQuestionSerializer(serializers.ModelSerializer):
    options = CTTestOptionSerializer(many=True)

    class Meta:
        model = models.CourseTypeTestQuestion
        fields = ('id', 'text', 'order', 'points', 'options')


class CourseTypeTestSerializer(serializers.ModelSerializer):
    questions = CTTestQuestionSerializer(many=True)

    class Meta:
        model = models.CourseTypeTest
        fields = (
            'id', 'course_type', 'title', 'description', 'created_by',
            'time_limit_minutes', 'attempts_allowed', 'pass_score', 'is_active', 'created_at',
            'questions'
        )
        read_only_fields = ('created_at', 'created_by')

    def create(self, validated_data):
        questions_data = validated_data.pop('questions', [])
        test = models.CourseTypeTest.objects.create(**validated_data)
        for q in questions_data:
            options = q.pop('options', [])
            question = models.CourseTypeTestQuestion.objects.create(test=test, **q)
            for opt in options:
                models.CourseTypeTestOption.objects.create(question=question, **opt)
        return test


class StudentCourseTypeTestSerializer(serializers.ModelSerializer):
    """Student-safe serializer that hides is_correct flags."""
    questions = serializers.SerializerMethodField()

    class Meta:
        model = models.CourseTypeTest
        fields = (
            'id', 'course_type', 'title', 'description', 'time_limit_minutes', 'attempts_allowed', 'pass_score', 'questions'
        )

    def get_questions(self, obj):
        data = []
        for q in obj.questions.all().order_by('order', 'id'):
            data.append({
                'id': q.id,
                'text': q.text,
                'order': q.order,
                'points': q.points,
                'options': [
                    {'id': o.id, 'text': o.text, 'order': o.order}
                    for o in q.options.all().order_by('order', 'id')
                ]
            })
        return data


class CourseTypeAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CourseTypeAssignment
        fields = (
            'id', 'course_type', 'title', 'description', 'created_by', 'due_at',
            'due_days_after_completion', 'max_points', 'allow_multiple_submissions', 'is_active', 'created_at'
        )
        read_only_fields = ('created_at', 'created_by')


class CourseTypeAssignmentSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CourseTypeAssignmentSubmission
        fields = ('id', 'assignment', 'student', 'text_answer', 'attachment', 'external_link', 'submitted_at', 'grade', 'feedback', 'graded_by')
        read_only_fields = ('submitted_at',)

class CourseTypeTestAnswerReadSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='question.text', read_only=True)
    selected_option_text = serializers.CharField(source='selected_option.text', read_only=True)
    points = serializers.IntegerField(source='question.points', read_only=True)

    class Meta:
        model = models.CourseTypeTestAnswer
        fields = (
            'id', 'question', 'question_text', 'selected_option', 'selected_option_text', 'is_correct', 'points'
        )


class CourseTypeTestResultSerializer(serializers.ModelSerializer):
    test_title = serializers.CharField(source='test.title', read_only=True)
    course_type_id = serializers.IntegerField(source='test.course_type_id', read_only=True)
    answers = CourseTypeTestAnswerReadSerializer(many=True, read_only=True)

    class Meta:
        model = models.CourseTypeTestResult
        fields = (
            'id', 'test', 'test_title', 'course_type_id', 'user', 'attempt', 'score', 'started_at', 'completed_at', 'answers'
        )
class StudentCourseTypeAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CourseTypeAssignment
        fields = [
            'id', 'title', 'description', 'due_at', 'due_days_after_completion', 'max_points',
            'allow_multiple_submissions', 'is_active', 'created_at'
        ]
        read_only_fields = ('created_at',)

class CourseTypeSerializer(serializers.ModelSerializer):
    total_course_videos = serializers.SerializerMethodField()

    class Meta:
        model = models.CourseType
        fields = (
            'id', 'course', 'name', 'slug', 'description',"is_active", 'created_by', 'price', 'total_course_videos'
        )

    def get_total_course_videos(self, obj):
        return models.CourseVideo.objects.filter(course_type=obj).count()


class CourseVideoSerializer(serializers.ModelSerializer):
    tests_brief = serializers.SerializerMethodField()
    assignments_brief = serializers.SerializerMethodField()
    course_type_info = serializers.SerializerMethodField()
    # hls_playlist_url = serializers.SerializerMethodField()
    class Meta:
        model = models.CourseVideo
        fields = (
            'id', 'course', 'title', 'description', 'poster', 'file_url', 'upload_file',
            'duration', 'is_active', 'order', 'created_at', 'hls_playlist_url', 'hls_segment_path',
            'has_test', 'has_assignment', 'tests_brief', 'assignments_brief', 'course_type', 'course_type_info'
        )
        read_only_fields = (
            'created_at', 'hls_playlist_url', 'hls_segment_path', 'has_test', 'has_assignment',
            'tests_brief', 'assignments_brief', 'course_type_info'
        )

    def get_tests_brief(self, obj):
        qs = obj.tests.filter(is_active=True).only('id', 'title').order_by('id')
        return [{'id': t.id, 'title': t.title} for t in qs]

    def get_assignments_brief(self, obj):
        qs = obj.assignments.filter(is_active=True).only('id', 'title').order_by('id')
        return [{'id': a.id, 'title': a.title} for a in qs]

    def get_course_type_info(self, obj):
        ct = obj.course_type
        if not ct:
            return None
        return {
            'id': ct.id,
            'name': ct.name,
            'slug': ct.slug,
            'description': ct.description,
            'created_by': ct.created_by_id,
            'is_active': ct.is_active,
            'price': ct.price,
        }

# ---- Test/Quiz serializers ----
class TestOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.TestOption
        fields = ('id', 'text', 'is_correct', 'order')


class TestQuestionSerializer(serializers.ModelSerializer):
    options = TestOptionSerializer(many=True)

    class Meta:
        model = models.TestQuestion
        fields = ('id', 'text', 'order', 'points', 'options')

    def create(self, validated_data):
        options_data = validated_data.pop('options', [])
        question = models.TestQuestion.objects.create(**validated_data)
        for opt in options_data:
            models.TestOption.objects.create(question=question, **opt)
        return question

    def update(self, instance, validated_data):
        options_data = validated_data.pop('options', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if options_data is not None:
            instance.options.all().delete()
            for opt in options_data:
                models.TestOption.objects.create(question=instance, **opt)
        return instance


class VideoTestSerializer(serializers.ModelSerializer):
    questions = TestQuestionSerializer(many=True)

    class Meta:
        model = models.VideoTest
        fields = (
            'id', 'course_video', 'title', 'description', 'created_by',
            'time_limit_minutes', 'attempts_allowed', 'pass_score', 'is_active', 'created_at',
            'questions'
        )
        read_only_fields = ('created_at', 'created_by')

    def create(self, validated_data):
        questions_data = validated_data.pop('questions', [])
        test = models.VideoTest.objects.create(**validated_data)
        for q in questions_data:
            options = q.pop('options', [])
            question = models.TestQuestion.objects.create(test=test, **q)
            for opt in options:
                models.TestOption.objects.create(question=question, **opt)
        return test

    def update(self, instance, validated_data):
        questions_data = validated_data.pop('questions', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if questions_data is not None:
            instance.questions.all().delete()
            for q in questions_data:
                options = q.pop('options', [])
                question = models.TestQuestion.objects.create(test=instance, **q)
                for opt in options:
                    models.TestOption.objects.create(question=question, **opt)
        return instance


class TestResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.TestResult
        fields = ('id', 'test', 'user', 'attempt', 'score', 'started_at', 'completed_at')
        read_only_fields = ('started_at', 'completed_at')


class TestAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.TestAnswer
        fields = ('id', 'result', 'question', 'selected_option', 'is_correct')


class TestResultListItemSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = models.TestResult
        fields = ('id', 'attempt', 'score', 'started_at', 'completed_at', 'user')

    def get_user(self, obj):
        u = obj.user
        return {
            'id': u.id,
            'username': u.username,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'email': u.email,
        }


# ===== Student-safe serializers (do not expose is_correct) =====
class StudentTestOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.TestOption
        fields = ('id', 'text', 'order')  # hide is_correct


class StudentTestQuestionSerializer(serializers.ModelSerializer):
    options = StudentTestOptionSerializer(many=True)

    class Meta:
        model = models.TestQuestion
        fields = ('id', 'text', 'order', 'points', 'options')


class StudentVideoTestSerializer(serializers.ModelSerializer):
    questions = StudentTestQuestionSerializer(many=True)

    class Meta:
        model = models.VideoTest
        fields = (
            'id', 'course_video', 'title', 'description', 'time_limit_minutes',
            'attempts_allowed', 'pass_score', 'questions'
        )


# ---- Assignment serializers ----
class VideoAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.VideoAssignment
        fields = ('id', 'course_video', 'title', 'description', 'created_by', 'due_at', 'max_points', 'allow_multiple_submissions', 'is_active', 'created_at', 'file')
        read_only_fields = ('created_at', 'created_by')


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AssignmentSubmission
        fields = ('id', 'assignment', 'student', 'text_answer', 'attachment', 'external_link', 'submitted_at', 'grade', 'feedback', 'graded_by')
        read_only_fields = ('submitted_at',)


class ReelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Reel
        fields = ('id', 'title', 'caption','poster', 'file_url', 'hls_playlist_url', 'duration', 'likes', 'views', 'reel_type', 'reel_type_id_or_slug')




