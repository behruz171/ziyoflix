"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from app.api import views as api_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('app.api.urls')),
    path('api/', include('app.api_teacher.urls')),
    path('api/', include('app.api_user.urls')),
    # Intercept direct media HLS requests for CourseVideo with secure checks
    # path('media/hls_reels/<int:video_id>/playlist.m3u8',api_views.ReelHLSProxyView.as_view(), name='reel_m3u8'),
    path('media/hls_reels/<int:video_id>/playlist.m3u8', api_views.ReelHLSProxyView.as_view(), name='reel_hls_proxy'),
    # path('media/hls_courses/<int:video_id>/<str:segment>', api_views.SecureCourseVideoSegmentAPIView.as_view(), name='secure_course_video_segment_media'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)