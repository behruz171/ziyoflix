from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.db.models import Q
from decimal import Decimal


# NOTE: If you plan to use the custom user model below, add this to your settings.py:
# AUTH_USER_MODEL = 'app.User'
# Make migrations after setting AUTH_USER_MODEL.


class User(AbstractUser):
    """
    Maxsus User modeli.

    - is_creator: foydalanuvchi darslik/yuklovchi (creator) ekanligini belgilaydi.
    - bio, avatar: profil ma'lumotlari.

    Eslatma: loyihada foydalanuvchi rollarini kengaytirish kerak bo'lsa, bu modelga
    qo'shimcha maydonlar yoki ruxsatlar qo'shing.
    """
    CHOICE_ROLE = [
        ('user', 'User'),
        ('teacher', 'Teacher'),
        ('admin', 'Admin'),
        ('director', 'Director'),
        
    ]

    role = models.CharField(max_length=10, choices=CHOICE_ROLE, default='user')
    bio = models.TextField(blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    def __str__(self):
        return self.get_full_name() or self.username


class Channel(models.Model):
    """
    Kanallar — creator(yozuvchi)ga tegishli bo'lgan profil sahifasi.

    - user: OneToOneField qilib bog'lash tavsiya etiladi (har bir creator uchun bitta kanal).
    - subscribers: kanali obunachilarini hisoblash uchun ManyToMany.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='channel')
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='channel_avatars/', blank=True, null=True)
    banner = models.ImageField(upload_to='channel_banners/', blank=True, null=True)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    subscribers = models.ManyToManyField(settings.AUTH_USER_MODEL, through='Subscription', related_name='subscriptions', blank=True)
    # Optional profile fields for richer channel cards and pages
    badge = models.CharField(max_length=120, blank=True, null=True, help_text="Short expertise label, e.g. 'Frontend Development'")
    website = models.URLField(blank=True, null=True)
    telegram = models.CharField(max_length=120, blank=True, null=True)
    instagram = models.CharField(max_length=120, blank=True, null=True)
    github = models.CharField(max_length=120, blank=True, null=True)
    linkedin = models.CharField(max_length=120, blank=True, null=True)
    location_country = models.CharField(max_length=100, blank=True, null=True)
    location_city = models.CharField(max_length=100, blank=True, null=True)
    years_experience = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        verbose_name = 'Channel'
        verbose_name_plural = 'Channels'

    def __str__(self):
        return f"{self.title} ({self.user.username})"


class Category(models.Model):
    """Kino yoki kurs uchun kategoriya (masalan: Fantastika, Drama, IT, Matematika)."""
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    category_img = models.ImageField(upload_to='category_images/', blank=True, null=True)
    category_banner = models.ImageField(upload_to='category_banners/', blank=True, null=True)

    def __str__(self):
        return self.name


class Language(models.Model):
    """Til model — kinolarning audio tillari yoki subtitr tillari uchun."""
    code = models.CharField(max_length=10, help_text='ISO kod (masalan: en, uz, ru)')
    name = models.CharField(max_length=80)

    def __str__(self):
        return f"{self.id} {self.name} ({self.code})"


class Movie(models.Model):
    """
    Kino modeli: umumiy ma'lumotlar.

    - categories: filmga tegishli kategoriyalar.
    - languages: filmda mavjud audio tillar (ManyToMany).
    - subtitles: mavjud subtitr tillari.
    - channels: kim joylagan (yoki qaysi kanal bilan bog'liq).
    """
    MOVIE_TYPE_CHOICES = [
        ("movie", "Movie"),
        ("serial", "Serial"),
    ]

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True)
    description = models.TextField(blank=True)
    release_date = models.DateField(blank=True, null=True)
    duration = models.PositiveIntegerField(help_text='Davomiylik sekundda', blank=True, null=True)
    poster = models.ImageField(upload_to='movies/posters/', blank=True, null=True)
    cover = models.ImageField(upload_to='movies/covers/', blank=True, null=True)
    categories = models.ManyToManyField(Category, related_name='movies', blank=True)
    languages = models.ManyToManyField(Language, related_name='movies_audio', blank=True)
    subtitles = models.ManyToManyField(Language, related_name='movies_subs', blank=True)
    channels = models.ManyToManyField(Channel, related_name='movies', blank=True, help_text='Kanallar yoki uploaderlar')
    director = models.CharField(max_length=255, blank=True, null=True)
    actors = models.TextField(blank=True, null=True, help_text='Aktorlar royhati, vergul bilan ajratilgan')
    # Use a date-producing callable to avoid DRF AssertionError (expects date, got datetime)
    created_date = models.DateField(default=timezone.localdate)
    country = models.CharField(max_length=100, blank=True, null=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    type = models.CharField(max_length=10, choices=MOVIE_TYPE_CHOICES, default="movie")  # ✅ qo‘shildi

    def __str__(self):
        return self.title


class MovieFile(models.Model):
    """Movie uchun fayl (yoki streaming URL). Bir filmga bir nechta fayl bo'lishi mumkin
    (masalan: trailer, 720p, 1080p, audio track har bir til uchun va h.k.)."""
    QUALITY_CHOICES = [
        ('360p', '360p'),
        ('480p', '480p'),
        ('720p', '720p'),
        ('1080p', '1080p'),
        ('4k', '4k'),
    ]

    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='files')
    title = models.CharField(max_length=220, blank=True, help_text='Masalan: main file, trailer')
    file_url = models.URLField(max_length=2000, blank=True, help_text='CDN yoki storage URL')
    upload_file = models.FileField(upload_to='movies/files/', blank=True, null=True)
    poster = models.ImageField(upload_to='movies/posters/', blank=True, null=True)
    quality = models.CharField(max_length=10, choices=QUALITY_CHOICES, blank=True)
    language = models.ForeignKey(Language, on_delete=models.SET_NULL, blank=True, null=True)
    is_trailer = models.BooleanField(default=False)
    duration = models.PositiveIntegerField(blank=True, null=True, help_text='soniyada')
    created_at = models.DateTimeField(auto_now_add=True)

    # Qo'shimcha maydonlar HLS uchun
    hls_playlist_url = models.CharField(max_length=2000, blank=True, null=True, help_text='HLS playlist (m3u8) URL')
    hls_segment_path = models.CharField(max_length=500, blank=True, null=True, help_text='HLS segmentlar joylashuvi')

    season = models.PositiveIntegerField(blank=True, null=True, help_text='Agar serial bo\'lsa, qaysi mavsum')
    episode = models.PositiveIntegerField(blank=True, null=True, help_text='Agar serial bo\'lsa, qaysi epizod')

    def __str__(self):
        return f"{self.id} {self.movie.title} - {self.title or self.quality or 'file'}"



class CourseCategory(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    category_img = models.ImageField(upload_to='category_course_images/', blank=True, null=True)
    category_banner = models.ImageField(upload_to='category_course_banners/', blank=True, null=True)
    color = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return self.name



class Course(models.Model):
    """Video darslik (masalan: Python darsligi). Bitta darslikda ko'p video bo'ladi."""
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True)
    description = models.TextField(blank=True)
    channel = models.ForeignKey(Channel, on_delete=models.SET_NULL, null=True, related_name='courses')
    categories = models.ManyToManyField(CourseCategory, related_name='courses', blank=True)
    language = models.ForeignKey(Language, on_delete=models.SET_NULL, null=True, blank=True)
    is_free = models.BooleanField(default=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # UI dan ko'rinadigan qo'shimcha atributlar
    # Xarid qamrovi: butun kursmi yoki faqat CourseType bo'yicha sotiladimi
    PURCHASE_SCOPE_CHOICES = [
        ('course', 'Butun kurs bo\'yicha sotib olish'),
        ('course_type', 'Faqat CourseType bo\'yicha sotib olish'),
    ]
    purchase_scope = models.CharField(
        max_length=20,
        choices=PURCHASE_SCOPE_CHOICES,
        default='course',
        help_text="To'lov qamrovini aniqlaydi: butun kurs yoki CourseType darajasida"
    )
    LEVEL_CHOICES = [
        ('beginner', "Boshlang'ich"),
        ('intermediate', "O'rta"),
        ('advanced', "Yuqori"),
    ]
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner')
    is_new = models.BooleanField(default=False)
    is_bestseller = models.BooleanField(default=False)
    is_serial = models.BooleanField(default=True)
    certificate_available = models.BooleanField(default=True)
    students_count = models.PositiveIntegerField(default=0)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=1, default=0, help_text='Masalan: 4.8')
    rating_count = models.PositiveIntegerField(default=0)
    lessons_count = models.PositiveIntegerField(default=0, help_text='Keshlangan darslar soni (UI uchun)')
    total_duration_minutes = models.PositiveIntegerField(default=0)
    thumbnail = models.ImageField(upload_to='courses/thumbnails/', blank=True, null=True)
    cover = models.ImageField(upload_to='courses/covers/', blank=True, null=True)
    # Moderatsiya holati
    is_active = models.BooleanField(default=False, help_text='Moderator tasdiqlaganidan keyin faollashadi')
    STATUS_CHOICES = [
        ('moderation', 'Moderatsiya'),
        ('rejected', 'Bekor qilindi'),
        ('approved', 'Tasdiqlandi'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='moderation', db_index=True)
    reason = models.TextField(null=True, blank=True)
    def __str__(self):
        return self.title


class CourseType(models.Model):

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(Channel, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='course_types')
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, 
                             help_text='Price for this specific course type. If not set, the course price will be used.')
    # Moderatsiya holati
    is_active = models.BooleanField(default=False)
    STATUS_CHOICES = [
        ('moderation', 'Moderatsiya'),
        ('rejected', 'Bekor qilindi'),
        ('approved', 'Tasdiqlandi'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='moderation', db_index=True)
    reason = models.TextField(null=True, blank=True)
    def __str__(self):
        return self.name


class CourseVideo(models.Model):
    """Darslik ichidagi video. 'order' yordamida tartiblanadi."""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='videos')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file_url = models.URLField(max_length=2000, blank=True)
    upload_file = models.FileField(upload_to='courses/videos/', blank=True, null=True)
    poster = models.ImageField(upload_to='courses/videos/posters/', blank=True, null=True)
    duration = models.PositiveIntegerField(blank=True, null=True, help_text='soniyada')
    order = models.PositiveIntegerField(default=0, help_text='Darslik ichidagi tartib raqami')
    created_at = models.DateTimeField(auto_now_add=True)
    course_type = models.ForeignKey(CourseType, on_delete=models.SET_NULL, null=True, blank=True)

    # HLS (m3u8) ma'lumotlari
    hls_playlist_url = models.CharField(max_length=500, blank=True, null=True)
    hls_segment_path = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        ordering = ['order', 'created_at']

    # Moderatsiya holati
    is_active = models.BooleanField(default=False)
    STATUS_CHOICES = [
        ('moderation', 'Moderatsiya'),
        ('rejected', 'Bekor qilindi'),
        ('approved', 'Tasdiqlandi'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='moderation', db_index=True)
    reason = models.TextField(null=True, blank=True)
    def __str__(self):
        return f"{self.id} - {self.course.title} — {self.title}"

    # Qulaylik uchun helper xususiyatlar
    @property
    def has_test(self) -> bool:
        return self.tests.filter(is_active=True).exists()

    @property
    def has_assignment(self) -> bool:
        return self.assignments.filter(is_active=True).exists()


# =========================
# CourseType (Monthly) Test/Assignment
# =========================
class CourseTypeTest(models.Model):
    """Monthly/section test linked to a CourseType."""
    course_type = models.ForeignKey(CourseType, on_delete=models.CASCADE, related_name='tests')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_ct_tests')
    time_limit_minutes = models.PositiveIntegerField(blank=True, null=True)
    attempts_allowed = models.PositiveIntegerField(default=1)
    pass_score = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"CT Test: {self.title} ({self.course_type.name})"


class CourseTypeTestQuestion(models.Model):
    test = models.ForeignKey(CourseTypeTest, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    order = models.PositiveIntegerField(default=0)
    points = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"CT Q{self.order} ({self.test.title})"


class CourseTypeTestOption(models.Model):
    question = models.ForeignKey(CourseTypeTestQuestion, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"CT Opt: {self.text[:30]}..."


class CourseTypeTestResult(models.Model):
    test = models.ForeignKey(CourseTypeTest, on_delete=models.CASCADE, related_name='results')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ct_test_results')
    attempt = models.PositiveIntegerField(default=1)
    score = models.FloatField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('test', 'user', 'attempt')
        ordering = ['-completed_at', '-started_at']

    def __str__(self):
        return f"{self.user} -> {self.test} (#{self.attempt})"


class CourseTypeTestAnswer(models.Model):
    result = models.ForeignKey(CourseTypeTestResult, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(CourseTypeTestQuestion, on_delete=models.CASCADE)
    selected_option = models.ForeignKey(CourseTypeTestOption, on_delete=models.SET_NULL, null=True, blank=True)
    is_correct = models.BooleanField(default=False)

    class Meta:
        unique_together = ('result', 'question')

    def __str__(self):
        return f"CT Answer: {self.result.user} / Q{self.question_id}"


class CourseTypeAssignment(models.Model):
    course_type = models.ForeignKey(CourseType, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=255)
    description = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_ct_assignments')
    due_at = models.DateTimeField(blank=True, null=True)
    # Barcha videolarni tugatgandan so'ng topshirish uchun beriladigan muddat (kunlarda)
    due_days_after_completion = models.PositiveIntegerField(blank=True, null=True, help_text="CourseType dagi barcha videolarni yakunlagandan keyin topshirish uchun beriladigan kunlar soni")
    max_points = models.PositiveIntegerField(default=100)
    allow_multiple_submissions = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"CT Vazifa: {self.title} ({self.course_type.name})"


class CourseTypeAssignmentSubmission(models.Model):
    assignment = models.ForeignKey(CourseTypeAssignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ct_assignment_submissions')
    text_answer = models.TextField(blank=True)
    attachment = models.FileField(upload_to='courses/ct_assignments/submissions/', blank=True, null=True)
    external_link = models.URLField(max_length=1000, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    grade = models.FloatField(blank=True, null=True)
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='graded_ct_assignment_submissions')

    class Meta:
        ordering = ['-submitted_at']
        unique_together = ('assignment', 'student')

    def __str__(self):
        return f"CT Submission: {self.student} -> {self.assignment}"


class CourseVideoProgress(models.Model):
    """Per-user progress for a CourseVideo.

    - last_position: last watched position in seconds.
    - seconds_watched: cumulative watched seconds (optional but handy for analytics).
    - completed: derived/explicit flag if last_position >= duration * threshold.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='course_video_progress')
    course_video = models.ForeignKey(CourseVideo, on_delete=models.CASCADE, related_name='progress')
    last_position = models.PositiveIntegerField(default=0, help_text='Seconds')
    seconds_watched = models.PositiveIntegerField(default=0, help_text='Aggregate watched seconds')
    completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'course_video')
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user} -> {self.course_video} @ {self.last_position}s completed={self.completed}"


# =========================
# Test (Quiz) modellari
# =========================
class VideoTest(models.Model):
    """Kurs videosiga biriktiriladigan test (quiz).

    Testni odatda o'qituvchi (teacher) yaratadi. Talabalar uni yechadi.
    """
    course_video = models.ForeignKey(CourseVideo, on_delete=models.CASCADE, related_name='tests')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_tests')
    time_limit_minutes = models.PositiveIntegerField(blank=True, null=True)
    attempts_allowed = models.PositiveIntegerField(default=1)
    pass_score = models.PositiveIntegerField(default=0, help_text='Foiz yoki ball sifatida talqin qilinishi mumkin')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Test: {self.title} ({self.course_video.title})"


class TestQuestion(models.Model):
    test = models.ForeignKey(VideoTest, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    order = models.PositiveIntegerField(default=0)
    points = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"Savol #{self.order} ({self.test.title})"


class TestOption(models.Model):
    question = models.ForeignKey(TestQuestion, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"Variant: {self.text[:30]}..."



class TestResult(models.Model):
    """Foydalanuvchining test bo'yicha umumiy natijasi (har bir urinish uchun)."""
    test = models.ForeignKey(VideoTest, on_delete=models.CASCADE, related_name='results')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='test_results')
    attempt = models.PositiveIntegerField(default=1)
    score = models.FloatField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('test', 'user', 'attempt')
        ordering = ['-completed_at', '-started_at']

    def __str__(self):
        return f"{self.user} -> {self.test} (#{self.attempt})"


class TestAnswer(models.Model):
    """Har bir savol uchun foydalanuvchi tanlagan javob."""
    result = models.ForeignKey(TestResult, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(TestQuestion, on_delete=models.CASCADE)
    selected_option = models.ForeignKey(TestOption, on_delete=models.SET_NULL, null=True, blank=True)
    is_correct = models.BooleanField(default=False)

    class Meta:
        unique_together = ('result', 'question')

    def __str__(self):
        return f"Answer: {self.result.user} / Q{self.question_id}"


# =========================
# Vazifa (Assignment) modellari
# =========================
class VideoAssignment(models.Model):
    course_video = models.ForeignKey(CourseVideo, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=255)
    description = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_assignments')
    due_at = models.DateTimeField(blank=True, null=True)
    max_points = models.PositiveIntegerField(default=100)
    allow_multiple_submissions = models.BooleanField(default=False)
    due_days_after_completion = models.PositiveIntegerField(blank=True, null=True, help_text="CourseType dagi barcha videolarni yakunlagandan keyin topshirish uchun beriladigan kunlar soni")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to='courses/assignments/', blank=True, null=True)

    def __str__(self):
        return f"Vazifa: {self.title} ({self.course_video.title})"


class AssignmentSubmission(models.Model):
    assignment = models.ForeignKey(VideoAssignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assignment_submissions')
    text_answer = models.TextField(blank=True)
    attachment = models.FileField(upload_to='courses/assignments/submissions/', blank=True, null=True)
    external_link = models.URLField(max_length=1000, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    grade = models.FloatField(blank=True, null=True)
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='graded_assignment_submissions')

    class Meta:
        ordering = ['-submitted_at']
        unique_together = ('assignment', 'student')

    def __str__(self):
        return f"Submission: {self.student} -> {self.assignment}"


class Reel(models.Model):
    """Instagram-ga o'xshash qisqa videolar (reels)."""
    CHOICE_TYPE = (
        ('course', 'Course'),
        ('channel', 'Channel'),
        ('movie', 'Movie'),
        ('course_video', 'Course Video'),
        ('none', 'None')
    )

    title = models.CharField(max_length=220, blank=True)
    caption = models.TextField(blank=True)
    file_url = models.URLField(max_length=2000, blank=True)
    upload_file = models.FileField(upload_to='reels/', blank=True, null=True)
    poster = models.FileField(upload_to='reels/posters/', blank=True, null=True)
    duration = models.PositiveIntegerField(help_text='soniyada', blank=True, null=True)
    channel = models.ForeignKey(Channel, on_delete=models.SET_NULL, null=True, related_name='reels')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='reels')
    likes = models.PositiveIntegerField(default=0)
    views = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    reel_type = models.CharField(max_length=20, choices=CHOICE_TYPE, default='none')
    reel_type_id_or_slug = models.CharField(max_length=220, blank=True)
    hls_playlist_url = models.CharField(max_length=500, blank=True, null=True)

    def __str__(self):
        return self.title or f"Reel by {self.channel or self.created_by}"


class ReelView(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reel_views')
    reel = models.ForeignKey('Reel', on_delete=models.CASCADE, related_name='view_records')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'reel')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} viewed {self.reel.title}"

class LikeReels(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='liked_reels')
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name='likes_relation')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'reel')

    def __str__(self):
        return f"{self.user} liked {self.reel}"
    
    def save(self, *args, **kwargs):
        if not self.pk:  # faqat yangi like yaratilsa
            self.reel.likes += 1
            self.reel.save(update_fields=['likes'])
        return super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        if self.reel.likes > 0:
            self.reel.likes -= 1
            self.reel.save(update_fields=['likes'])
        return super().delete(*args, **kwargs)

class Playlist(models.Model):
    """Foydalanuvchi yoki kanal tomonidan yaratilgan playlist.

    Playlist ichiga film fayllari (MovieFile), CourseVideo yoki Reel'larni qo'shishingiz mumkin.
    Bu yerdagi implementatsiya osonroq bo'lishi uchun ikki ManyToMany maydon ishlatilgan:
    - movies: `Movie` obyektlarini to'playdi
    - course_videos: kurs videolarini to'playdi
    (zarur bo'lsa GenericRelation ishlatib yagona 'items' jadvalini qilish mumkin).
    """
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='playlists')
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=True)
    movies = models.ManyToManyField(Movie, blank=True, related_name='in_playlists')
    course_videos = models.ManyToManyField(CourseVideo, blank=True, related_name='in_playlists')
    reels = models.ManyToManyField(Reel, blank=True, related_name='in_playlists')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.owner})"


class Subscription(models.Model):
    """Foydalanuvchi kanallarga obuna bo'lishi uchun model."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='channel_subscriptions')
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='subscribers_relation')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'channel')

    def __str__(self):
        return f"{self.user} -> {self.channel}"




class CommentBase(models.Model):
    """Abstract comment base — har bir content turiga mos concrete modeldan meros olar.

    Ushbu yechim GenericForeignKey o'rniga aniq ForeignKey turlari bilan ishlash imkonini beradi.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    text = models.TextField()
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"Comment by {self.user}: {self.text[:50]}"


class MovieComment(CommentBase):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='comments')


class CourseVideoComment(CommentBase):
    course_video = models.ForeignKey(CourseVideo, on_delete=models.CASCADE, related_name='comments')


class ReelComment(CommentBase):
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name='comments')


class ChannelComment(CommentBase):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='comments')


class PlaylistComment(CommentBase):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='comments')


class RatingBase(models.Model):
    """Abstract rating base; concrete klasslar user va value bilan meros oladi."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    value = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.value < 1:
            self.value = 1
        if self.value > 5:
            self.value = 5
        return super().save(*args, **kwargs)


class MovieRating(RatingBase):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='ratings')


class CourseVideoRating(RatingBase):
    course_video = models.ForeignKey(CourseVideo, on_delete=models.CASCADE, related_name='ratings')


class ReelRating(RatingBase):
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name='ratings')


class ChannelRating(RatingBase):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='ratings')


class PlaylistRating(RatingBase):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='ratings')


class ReelSave(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_reels')
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name='saved_by')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} saved {self.reel}"

class Banner(models.Model):
    """Banner without GenericForeignKey — explicit FK fields for each supported target.

    Ushbu yondashuv GenericForeignKey ishlatmasdan oddiyroq va admin/form uchun aniqroq ishlaydi.
    Agar banner biror kontentga bog'langan bo'lsa, tegishli FK maydon to'ldiriladi.
    """
    POSITION_CHOICES = [
        ('hero', 'Hero (bosh sahifa katta banner)'),
        ('top', 'Top (sahifa ustida)'),
        ('sidebar', 'Sidebar'),
        ('footer', 'Footer'),
        ('carousel', 'Carousel'),
        ('custom', 'Custom'),
        ('advertisement', 'Advertisement')
    ]

    title = models.CharField(max_length=220, blank=True)
    image = models.ImageField(upload_to='banners/')
    image_mobile = models.ImageField(upload_to='banners/', blank=True, null=True)
    image_tablet = models.ImageField(upload_to='banners/', blank=True, null=True)
    alt_text = models.CharField(max_length=220, blank=True)

    # Explicit targets (nullable) — faqat bittasi to'ldiriladi deb qabul qilamiz
    movie = models.ForeignKey(Movie, on_delete=models.SET_NULL, null=True, blank=True, related_name='banners')
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='banners')
    reel = models.ForeignKey(Reel, on_delete=models.SET_NULL, null=True, blank=True, related_name='banners')
    channel = models.ForeignKey(Channel, on_delete=models.SET_NULL, null=True, blank=True, related_name='banners')
    playlist = models.ForeignKey(Playlist, on_delete=models.SET_NULL, null=True, blank=True, related_name='banners')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='banners')

    # Agar banner tashqi manzilga olib borsa — shu url ishlatiladi
    url = models.URLField(max_length=2000, blank=True)

    # Joylashuvi va tartib
    position = models.CharField(max_length=30, choices=POSITION_CHOICES, default='hero')
    order = models.IntegerField(default=0, help_text='Bir nechta banner bo`lsa tartib')

    # Ko'rsatilish vaqti
    start_at = models.DateTimeField(default=timezone.now)
    end_at = models.DateTimeField(null=True, blank=True, help_text='Agar belgilansa, shu vaqtdan keyin banner yopiladi')

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'order', '-created_at']
        verbose_name = 'Banner'
        verbose_name_plural = 'Banners'

    def __str__(self):
        return self.title or f"Banner ({self.position})"

    def is_current(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_at and self.start_at > now:
            return False
        if self.end_at and self.end_at < now:
            return False
        return True

    def get_target(self):
        """Return first non-null target object or None."""
        for attr in ('movie', 'course', 'reel', 'channel', 'playlist', 'category'):
            obj = getattr(self, attr)
            if obj:
                return obj
        return None

    def get_target_url(self):
        t = self.get_target()
        if t:
            try:
                return t.get_absolute_url()
            except Exception:
                pass
        return self.url or ''


# =============================
# Wallet System (FixCoin)
# =============================
class Wallet(models.Model):
    """
    Har bir foydalanuvchi uchun hamyon. FixCoin valyutasida balans.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), help_text='FixCoin miqdori')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Wallet'
        verbose_name_plural = 'Wallets'

    def __str__(self):
        return f"{self.user.username} - {self.balance} FixCoin"

    def recalculate_balance(self):
        """Tranzaksiyalar asosida balansni qayta hisoblash (debug uchun)."""
        from django.db.models import Sum
        total = self.transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        print(f"Calculated balance: {total}, Current balance: {self.balance}")
        return total

    def add_balance(self, amount, transaction_type='deposit', description=''):
        """Balansga pul qo'shish va tranzaksiya yaratish."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        self.balance += Decimal(str(amount))
        self.save()
        # Tranzaksiya yaratish
        return WalletTransaction.objects.create(
            wallet=self,
            transaction_type=transaction_type,
            amount=amount,
            balance_after=self.balance,
            description=description
        )

    def subtract_balance(self, amount, transaction_type='withdrawal', description=''):
        """Balansdan pul yechish va tranzaksiya yaratish."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if self.balance < Decimal(str(amount)):
            raise ValueError("Insufficient balance")
        self.balance -= Decimal(str(amount))
        self.save()
        # Tranzaksiya yaratish
        WalletTransaction.objects.create(
            wallet=self,
            transaction_type=transaction_type,
            amount=-amount,  # manfiy qiymat
            balance_after=self.balance,
            description=description
        )

    @staticmethod
    def transfer_for_course_purchase(buyer_user, seller_user, course, amount, platform_commission_rate=0.05, course_type=None, transaction_type='course_purchase', *, original_amount=None, discount_amount=None, promo_code=None):
        """
        Kurs yoki kurs turini sotib olish uchun pul o'tkazish.
        2 ta tranzaksiya yaratadi: buyer dan chiqim, seller ga kirim.
        Platforma komissiyasini ham hisobga oladi.
        
        Args:
            buyer_user: Xaridor foydalanuvchisi
            seller_user: Sotuvchi foydalanuvchisi
            course: Kurs obyekti
            amount: Sotib olish summasi
            platform_commission_rate: Platforma komissiyasi foizi (0.05 = 5%)
            course_type: Kurs turi (ixtiyoriy)
            transaction_type: Tranzaksiya turi ('course_purchase' yoki 'course_type_purchase')
        """
        from django.db import transaction
        
        # O'zini-o'zi sotib olishni tekshirish
        if buyer_user == seller_user:
            raise ValueError("O'z kursini sotib olish mumkin emas")
        
        amount = Decimal(str(amount))
        orig_amount = Decimal(str(original_amount)) if original_amount is not None else amount
        disc_amount = Decimal(str(discount_amount)) if discount_amount is not None else Decimal('0.00')
        commission = amount * Decimal(str(platform_commission_rate))
        seller_earning = amount - commission
        
        # Xaridorning hamyonini tekshirish
        buyer_wallet, _ = Wallet.objects.get_or_create(user=buyer_user)
        if buyer_wallet.balance < amount:
            raise ValueError("Yetarli mablag' mavjud emas")
        
        # Sotuvchining hamyonini yaratish/olish
        seller_wallet, _ = Wallet.objects.get_or_create(user=seller_user)
        
        # Tranzaksiya tavsifi
        purchase_type = "Kurs turi" if course_type else "Kurs"
        item_name = f"{course_type.name}" if course_type else course.title
        
        with transaction.atomic():
            # 1. Xaridordan pul yechish
            buyer_wallet.balance -= amount
            buyer_wallet.save()
            
            transaction_data = {
                'wallet': buyer_wallet,
                'transaction_type': transaction_type,
                'amount': -amount,
                'balance_after': buyer_wallet.balance,
                'description': f"{purchase_type} sotib olish: {item_name}",
                'course': course,
                'from_user': buyer_user,
                'to_user': seller_user,
                'promo_code': promo_code,
                'original_amount': orig_amount,
                'discount_amount': disc_amount,
            }
            
            # Agar kurs turi kiritilgan bo'lsa, uni ham qo'shamiz
            if course_type:
                buyer_transaction = WalletTransaction.objects.create(
                    **transaction_data,
                    course_type=course_type
                )
            else:
                buyer_transaction = WalletTransaction.objects.create(**transaction_data)
            
            # 2. Sotuvchiga pul qo'shish (komissiyasiz)
            seller_wallet.balance += seller_earning
            seller_wallet.save()
            
            seller_transaction = WalletTransaction.objects.create(
                wallet=seller_wallet,
                transaction_type=('course_type_earning' if course_type else 'course_earning'),
                amount=seller_earning,
                balance_after=seller_wallet.balance,
                description=f"{purchase_type} sotishdan daromad: {item_name}",
                course=course,
                course_type=course_type,
                from_user=buyer_user,
                to_user=seller_user,
                related_transaction=buyer_transaction
            )
            
            # Bog'langan tranzaksiyani yangilash
            buyer_transaction.related_transaction = seller_transaction
            buyer_transaction.save()
            # Promo usage increment
            if promo_code:
                try:
                    PromoCode.objects.filter(id=promo_code.id).update(uses=models.F('uses') + 1)
                except Exception:
                    pass
            
            # 3. Agar komissiya bor bo'lsa, platforma uchun tranzaksiya (ixtiyoriy)
            if commission > 0:
                try:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    platform_user = User.objects.filter(is_superuser=True).first()
                    if platform_user:
                        platform_wallet, _ = Wallet.objects.get_or_create(user=platform_user)
                        platform_wallet.balance += commission
                        platform_wallet.save()
                        
                        WalletTransaction.objects.create(
                            wallet=platform_wallet,
                            transaction_type='commission',
                            amount=commission,
                            balance_after=platform_wallet.balance,
                            description=f"Platforma komissiyasi: {item_name}",
                            course=course,
                            course_type=course_type,
                            from_user=buyer_user,
                            to_user=platform_user
                        )
                except Exception:
                    pass  # Komissiya tranzaksiyasi muvaffaqiyatsiz bo'lsa, asosiy tranzaksiya bajariladi
            
            return buyer_transaction, seller_transaction


class WalletTransaction(models.Model):
    """
    Hamyon tranzaksiyalari tarixi.
    """
    TRANSACTION_TYPES = [
        ('deposit', 'Pul toldirish'),
        ('withdrawal', 'Pul yechish'),
        ('course_purchase', 'Kurs sotib olish (chiqim)'),
        ('course_type_purchase', 'Kurs turini sotib olish (chiqim)'),
        ('course_earning', 'Kurs sotishdan daromad (kirim)'),
        ('course_type_earning', 'Kurs turi sotishdan daromad (kirim)'),
        ('transfer_sent', 'Pul jo\'natish'),
        ('refund', 'Qaytarib berish'),
        ('bonus', 'Bonus'),
        ('penalty', 'Jarima'),
        ('commission', 'Komissiya (platforma)'),
    ]
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2, help_text='Musbat - kirim, manfiy - chiqim')
    original_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text='Asl narx')
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text='Chegirma miqdori (musbat)')
    balance_after = models.DecimalField(max_digits=15, decimal_places=2, help_text='Tranzaksiyadan keyin balans')
    description = models.TextField(blank=True, help_text='Tranzaksiya tavsifi')
    
    # Bog'liq obyektlar
    course = models.ForeignKey('Course', on_delete=models.SET_NULL, null=True, blank=True, help_text="Agar kurs bilan bog'liq bo'lsa")
    course_type = models.ForeignKey('CourseType', on_delete=models.SET_NULL, null=True, blank=True, help_text='Agar kurs turi bilan bog\'liq bo\'lsa')
    # Kimdan-kimga ma'lumotlari
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_transactions', help_text="Pul jo'natuvchi")
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_transactions', help_text='Pul qabul qiluvchi')
    # Bog'langan tranzaksiya (masalan, kurs sotib olishda 2 ta tranzaksiya bir-biriga bog'langan)
    related_transaction = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, help_text='Bog\'langan tranzaksiya')
    # Qo'llangan promokod
    promo_code = models.ForeignKey('PromoCode', on_delete=models.SET_NULL, null=True, blank=True, help_text='Agar promokod ishlatilgan bo\'lsa')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Wallet Transaction'
        verbose_name_plural = 'Wallet Transactions'

    def __str__(self):
        return f"{self.wallet.user.username} - {self.get_transaction_type_display()} - {self.amount} FixCoin"

    def is_income(self):
        """Kirim tranzaksiyasi ekanligini tekshirish."""
        return self.amount > 0

    def is_expense(self):
        """Chiqim tranzaksiyasi ekanligini tekshirish."""
        return self.amount < 0


# =============================
# Promo Codes
# =============================
class PromoCode(models.Model):
    """Promokodlar: foizli yoki fix-coin chegirma. Ixtiyoriy ravishda ma'lum kurs(lar)ga bog'lanadi."""
    DISCOUNT_TYPES = [
        ('percent', 'Foizda'),
        ('coins', 'FixCoin'),
    ]
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES)
    value = models.DecimalField(max_digits=10, decimal_places=2, help_text='percent uchun 0-100; coins uchun miqdor')
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text='Cheksiz bo‘lsa bo‘sh qoldiring')
    uses = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    # Cheklovlar
    created_at = models.DateTimeField(auto_now_add=True)
    courses = models.ManyToManyField('Course', blank=True)
    course_types = models.ManyToManyField('CourseType', blank=True)

    class Meta:
        verbose_name = 'Promo Code'
        verbose_name_plural = 'Promo Codes'

    def __str__(self):
        return self.code

    @property
    def is_valid_now(self):
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_to and now > self.valid_to:
            return False
        if self.max_uses is not None and self.uses >= self.max_uses:
            return False
        return True
