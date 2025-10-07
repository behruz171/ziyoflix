from rest_framework.routers import DefaultRouter
from django.urls import path, include
from . import views
from . import assignment_views

urlpatterns = [
    # TEACHER CHANNEL APIS
    path('teacher/channels/', views.TeacherChannelsAPIView.as_view(), name='teacher-channels'),
    # TEACHER ANALYTICS APIS
    path('teacher/analytics/overview/', views.TeacherAnalyticsOverviewAPIView.as_view(), name='teacher-analytics-overview'),
    path('teacher/analytics/courses/', views.TeacherAnalyticsCoursesAPIView.as_view(), name='teacher-analytics-courses'),
    path('teacher/analytics/engagement/', views.TeacherAnalyticsEngagementAPIView.as_view(), name='teacher-analytics-engagement'),
    # TEACHER COURSE AND VIDEOS APIS
    path('teacher/<slug:channel_slug>/courses/', views.TeacherChannelCoursesAPIView.as_view(), name='teacher-channel-courses'),
    path('teacher/<slug:channel_slug>/courses/<slug:course_slug>/videos/', views.TeacherCourseVideosAPIView.as_view(), name='teacher-course-videos'),
    path('teacher/<slug:channel_slug>/courses/<slug:course_slug>/videos/type/<slug:course_type_slug>/', views.TeacherCourseVideosAPIView.as_view(), name='teacher-course-videos-by-type'),
    # TEACHER VIDEO TESTS AND ASSIGNMENTS APIS
    path('teacher/<slug:channel_slug>/courses/<slug:course_slug>/videos/<int:video_id>/tests/', views.TeacherVideoTestsAPIView.as_view(), name='teacher-video-tests'),
    path('teacher/<slug:channel_slug>/courses/<slug:course_slug>/videos/<int:video_id>/assignments/', views.TeacherVideoAssignmentsAPIView.as_view(), name='teacher-video-assignments'),
    path('teacher/<slug:channel_slug>/courses/<slug:course_slug>/videos/<int:video_id>/summary/', views.TeacherVideoSummaryAPIView.as_view(), name='teacher-video-summary'),
    path('teacher/<slug:channel_slug>/courses/<slug:course_slug>/course-types/<slug:course_type_slug>/ct-tests/', views.TeacherVideoCTTestsAPIView.as_view(), name='teacher-video-ct-tests'),
    # TEACHER REELS APIS
    path('teacher/<slug:channel_slug>/reels/', views.TeacherChannelReelsAPIView.as_view(), name='teacher-channel-reels'),
    path('teacher/<slug:channel_slug>/reels/<int:reel_id>/summary/', views.TeacherReelSummaryAPIView.as_view(), name='teacher-reel-summary'),
    
    # TEACHER TESTS LIST & STATS
    path('teacher/<slug:channel_slug>/tests/', views.TeacherTestsListAPIView.as_view(), name='teacher-tests-list'),
    path('teacher/<slug:channel_slug>/tests/stats/', views.TeacherTestsStatsAPIView.as_view(), name='teacher-tests-stats'),
    path('teacher/<slug:channel_slug>/tests/<int:test_id>/attempts/', views.TeacherTestAttemptsAPIView.as_view(), name='teacher-test-attempts'),
    
    # TEACHER ASSIGNMENTS LIST & STATS & SUBMISSIONS
    path('teacher/<slug:channel_slug>/assignments/', views.TeacherAssignmentsListAPIView.as_view(), name='teacher-assignments-list'),
    path('teacher/<slug:channel_slug>/assignments/stats/', views.TeacherAssignmentsStatsAPIView.as_view(), name='teacher-assignments-stats'),
    path('teacher/<slug:channel_slug>/assignments/<int:assignment_id>/submissions/', views.TeacherAssignmentSubmissionsListAPIView.as_view(), name='teacher-assignment-submissions-list'),

    # TEACHER ASSIGNMENT SUBMISSION APIS
    path('teacher/assignments/submissions/', assignment_views.TeacherAssignmentSubmissionsAPIView.as_view(), name='teacher-assignment-submissions'),
    path('teacher/assignments/submissions/<int:submission_id>/', assignment_views.TeacherAssignmentSubmissionDetailAPIView.as_view(), name='teacher-assignment-submission-detail'),
    path('teacher/<slug:channel_slug>/assignments/submissions/<int:submission_id>/grade/', assignment_views.GradeAssignmentSubmissionAPIView.as_view(), name='grade-assignment-submission'),
    path('teacher/assignments/submissions/stats/', assignment_views.AssignmentSubmissionStatsAPIView.as_view(), name='assignment-submission-stats'),
    path('teacher/assignments/by-video/<int:video_id>/', assignment_views.TeacherAssignmentsByVideoAPIView.as_view(), name='teacher-assignments-by-video'),
    path('teacher/assignments/submissions/<int:submission_id>/delete/', assignment_views.delete_assignment_submission, name='delete-assignment-submission'),

    # TEACHER STUDENTS (BUYERS) APIS
    path('teacher/<slug:channel_slug>/courses/<slug:course_slug>/students/',
         views.TeacherCourseStudentsAPIView.as_view(), name='teacher-course-students'),
    path('teacher/<slug:channel_slug>/courses/<slug:course_slug>/students/stats/',
         views.TeacherCourseStudentsStatsAPIView.as_view(), name='teacher-course-students-stats'),
    path('teacher/<slug:channel_slug>/courses/<slug:course_slug>/students/<int:user_id>/activity/',
         views.TeacherCourseStudentActivityAPIView.as_view(), name='teacher-course-student-activity'),
]
