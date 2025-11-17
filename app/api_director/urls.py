from rest_framework.routers import DefaultRouter
from django.urls import path, include, re_path
from . import views

router = DefaultRouter()
router.register(r'moderation/courses', views.CourseModerationViewSet, basename='director-course')
router.register(r'moderation/course-types', views.CourseTypeModerationViewSet, basename='director-course-type')
router.register(r'moderation/course-videos', views.CourseVideoModerationViewSet, basename='director-course-video')
router.register(r'channels', views.ChannelAdminViewSet, basename='director-channel')
router.register(r'banners', views.BannerAdminViewSet, basename='director-banner')
router.register(r'promo-codes', views.PromoCodeViewSet, basename='director-promo-code')
router.register(r'transactions', views.WalletTransactionAdminViewSet, basename='director-transactions')
router.register(r'course-categories', views.CourseCategoryAdminViewSet, basename='director-course-category')
router.register(r'movie-categories', views.CategoryAdminViewSet, basename='director-movie-category')
router.register(r'movies', views.MovieAdminViewSet, basename='director-movie')

urlpatterns = [
    path('', include(router.urls)),
    re_path(r'^users/(?P<role>[^/]+)/$', views.RoleUsersViewSet.as_view({'get': 'list'}), name='director-users-by-role'),
    path('reports/overview/', views.ReportsOverviewViewSet.as_view({'get': 'list'}), name='director-reports-overview'),
]

