from django.urls import path
from . import views

urlpatterns = [
    path('overview/', views.UserOverviewAPIView.as_view(), name='user-overview'),
    path('video-lessons/', views.UserVideoLessonsAPIView.as_view(), name='user-video-lessons'),
    path('saved/', views.UserSavedPlaylistsAPIView.as_view(), name='user-saved'),
    path('saved-reels/', views.UserSavedReelsAPIView.as_view(), name='user-saved-reels'),
    path('likes-comments/', views.UserLikesCommentsAPIView.as_view(), name='user-likes-comments'),
    path('submitted-assignments/', views.UserSubmittedAssignmentsAPIView.as_view(), name='user-submitted-assignments'),
    path('submitted-assignments/<int:id>/', views.UserSubmittedAssignmentDetailAPIView.as_view(), name='user-submitted-assignment-detail'),
    path('purchases/', views.UserPurchasesAPIView.as_view(), name='user-purchases'),
    path('test-results/', views.UserTestResultsAPIView.as_view(), name='user-test-results'),
    path('test-result/<int:id>/', views.UserTestResultDetailAPIView.as_view(), name='user-test-result-detail'),
    path('certificates/', views.UserCertificatesAPIView.as_view(), name='user-certificates'),
    path('settings/', views.UserSettingsAPIView.as_view(), name='user-settings'),
]
