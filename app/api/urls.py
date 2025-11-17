from rest_framework.routers import DefaultRouter
from django.urls import path, include
from . import views
from . import wallet_views
from django.urls import include as dj_include

router = DefaultRouter()
router.register(r'banners', views.BannerViewSet, basename='banner')
router.register(r'movies', views.MovieViewSet, basename='movie')
router.register(r'courses', views.CourseViewSet, basename='course')
router.register(r'coursetypes', views.CourseTypeViewSet, basename='coursetype')
router.register(r'course-videos', views.CourseVideoViewSet, basename='course-video')
router.register(r'video-tests', views.VideoTestViewSet, basename='video-test')
router.register(r'video-assignments', views.VideoAssignmentViewSet, basename='video-assignment')
router.register(r'assignment-submissions', views.AssignmentSubmissionViewSet, basename='assignment-submission')
router.register(r'reels', views.ReelViewSet, basename='reel')
router.register(r'channels', views.ChannelViewSet, basename='channel')
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'coursecategories', views.CourseCategoryViewSet, basename='coursecategory')
router.register(r'languages', views.LanguageViewSet, basename='language')
router.register(r'video-test-questions', views.VideoTestQuestionViewSet, basename='video-test-question')
router.register(r'video-test-answers', views.VideoTestAnswerViewSet, basename='video-test-answer')
router.register(r'video-test-results', views.VideoTestResultViewSet, basename='video-test-result')
router.register(r'video-test-options', views.VideoTestOptionViewSet, basename='video-test-option')
urlpatterns = [
    path('', include(router.urls)),
    path('director/', dj_include('app.api_director.urls')),
    path('user/', include('app.api_user.urls')),
    path('users/login/', views.LoginAPIView.as_view(), name='api-login'),
    path('users/signup/', views.SignUpAPIView.as_view(), name='api-signup'),
    path('homepage/', views.homepage, name='api-homepage'),
    path('homepage/banners/', views.BannerHomepageListView.as_view(), name='api-homepage-banners'),
    path('homepage/movies/', views.MovieHomepageListView.as_view(), name='api-homepage-movies'),
    path('homepage/courses/', views.CourseHomepageListView.as_view(), name='api-homepage-courses'),
    path('homepage/reels/', views.ReelHomepageListView.as_view(), name='api-homepage-reels'),
    path('homepage/channels/', views.ChannelHomepageListView.as_view(), name='api-homepage-channels'),
    path("upload-video/", views.UnifiedUploadAPIView.as_view(), name="api-upload-video"),
    path('stream-video/<int:file_id>/', views.VideoStreamAPIView.as_view()),
    path('video-processing-status/<int:file_id>/', views.VideoProcessingStatusAPIView.as_view()),
    # CourseVideo HLS upload/stream
    path('course-video/upload/', views.CourseVideoUploadAPIView.as_view(), name='course_video_upload'),
    path('course-video/<int:video_id>/status/', views.CourseVideoProcessingStatusAPIView.as_view(), name='course_video_status'),
    path('course-video/<int:video_id>/stream/', views.CourseVideoStreamAPIView.as_view(), name='course_video_stream'),

    # Secure HLS endpoints
    path('course-video/<int:video_id>/playlist.m3u8', views.SecureCourseVideoPlaylistAPIView.as_view(), name='secure_course_video_playlist'),
    path('course-video/<int:video_id>/<str:segment>', views.SecureCourseVideoSegmentAPIView.as_view(), name='secure_course_video_segment'),
    
    # Test submit and assignment submit
    path('tests/submit/', views.SubmitTestAPIView.as_view(), name='submit_test'),
    path('assignments/submit/', views.AssignmentSubmitAPIView.as_view(), name='submit_assignment'),
    # Progress tracking
    path('progress/video/<int:video_id>/', views.CourseVideoProgressAPIView.as_view(), name='course_video_progress'),
    path('progress/course/<slug:slug>/', views.CourseProgressAPIView.as_view(), name='course_progress'),
    # Assignments: retrieve
    path('assignments/<int:assignment_id>/', views.AssignmentDetailAPIView.as_view(), name='assignment_detail'),
    path('assignments/by-video/<int:video_id>/', views.AssignmentsByVideoIdAPIView.as_view(), name='assignments_by_video_id'),
    path('assignments/create/', views.CreateVideoAssignmentAPIView.as_view(), name='create_video_assignment'),
    # Tests: student view, teacher create, results
    path('tests/<int:test_id>/', views.StudentTestDetailAPIView.as_view(), name='student_test_detail'),
    path('tests/by-video/<int:video_id>/', views.StudentTestByVideoAPIView.as_view(), name='student_test_by_video'),
    path('tests/create/', views.CreateVideoTestAPIView.as_view(), name='create_video_test'),
    path('tests/<int:test_id>/results/', views.TestResultsListAPIView.as_view(), name='test_results'),
    path('tests/my-results/', views.MyTestResultsAPIView.as_view(), name='my_test_results'),
    path('tests/<int:test_id>/my-results/', views.MyTestResultsAPIView.as_view(), name='my_test_results_for_test'),

    # CourseType tests and assignments
    path('ct-tests/create/', views.CreateCourseTypeTestAPIView.as_view(), name='create_course_type_test'),
    path('ct-tests/by-type/<int:course_type_id>/', views.StudentCourseTypeTestByTypeAPIView.as_view(), name='student_course_type_test'),
    path('ct-tests/submit/', views.SubmitCourseTypeTestAPIView.as_view(), name='submit_course_type_test'),
    path('ct-tests/results/<int:result_id>/', views.CourseTypeTestResultDetailAPIView.as_view(), name='ct_test_result_detail'),
    path('ct-tests/my-results/', views.MyCourseTypeTestResultsAPIView.as_view(), name='my_ct_test_results'),
    path('ct-assignments/by-type/<int:course_type_id>/', views.StudentCourseTypeAssignmentByTypeAPIView.as_view(), name='student_course_type_assignment'),
    path('ct-assignments/create/', views.CreateCourseTypeAssignmentAPIView.as_view(), name='create_course_type_assignment'),
    path('ct-assignments/submit/', views.SubmitCourseTypeAssignmentAPIView.as_view(), name='submit_course_type_assignment'),

    # Channel detail 'About' tab
    path('channels/<slug:slug>/about/', views.ChannelAboutAPIView.as_view(), name='channel_about'),
    path('channels/<slug:slug>/courses/', views.ChannelCoursesAPIView.as_view(), name='channel_courses'),
    path('channels/<slug:slug>/reels/', views.ChannelReelsAPIView.as_view(), name='channel_reels'),

    # Reels
    path('reel/upload/', views.ReelUploadAPIView.as_view(), name='reel_upload'),
    path('reel/<int:reel_id>/stream/', views.ReelStreamAPIView.as_view(), name='reel_stream'),
    path("reel/random-feed/", views.RandomReelFeedAPIView.as_view(), name="reel_random_feed"),
    path("reel/<int:reel_id>/comments/", views.CommentReelAPIView.as_view(), name="reel_comments"),
    path("reel/<int:reel_id>/like/", views.ReelLikeAPIView.as_view(), name="reel_like"),
    path("reel/<int:reel_id>/save/", views.ReelSaveAPIView.as_view(), name="reel_save"),

    path("get-movies/", views.MovieListAPIView.as_view(), name="movie_list"),
    path("get-movies/category/<slug:slug>/", views.MovieByCategoryAPIView.as_view(), name="movie_by_category"),
    path("get-movies/<slug:slug>/", views.MovieDetailAPIView.as_view(), name="movie_detail"),
    # Courses
    path("get-course-type/<slug:course_slug>/", views.CourseTypeAPIView.as_view(), name="course_type"),
    path("get-courses/coursecategory/<slug:category_slug>/", views.CourseByCourseCategoryAPIView.as_view(), name="courses_by_coursecategory"),
    path("get-course-videos/<slug:course_slug>/", views.CourseVideosByCourseSlugAPIView.as_view(), name="course_videos_by_course_slug"),
    path("get-course-videos/<slug:course_slug>/<slug:course_type_slug>/", views.CourseVideosByCourseSlugAndCourseTypeAPIView.as_view(), name="course_videos_by_course_slug_and_course_type"),
    
    # Wallet APIs
    path('wallet/', wallet_views.WalletDetailAPIView.as_view(), name='wallet_detail'),
    path('wallet/balance/', wallet_views.wallet_balance, name='wallet_balance'),
    path('wallet/transactions/', wallet_views.WalletTransactionsAPIView.as_view(), name='wallet_transactions'),
    path('wallet/deposit/', wallet_views.WalletDepositAPIView.as_view(), name='wallet_deposit'),
    path('wallet/withdrawal/', wallet_views.WalletWithdrawalAPIView.as_view(), name='wallet_withdrawal'),
    path('wallet/purchase-course/', wallet_views.CoursePurchaseAPIView.as_view(), name='course_purchase'),
    path('wallet/purchase-course-type/', wallet_views.CourseTypePurchaseAPIView.as_view(), name='course_type_purchase'),
    path('wallet/stats/', wallet_views.WalletStatsAPIView.as_view(), name='wallet_stats'),
]
