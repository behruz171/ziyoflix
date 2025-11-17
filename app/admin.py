from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django import forms
from django.urls import path
from django.http import JsonResponse
from django.contrib.contenttypes.models import ContentType as DContentType
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
# from genericadmin.admin import GenericAdminModelAdmin
# from gfk.fields import GfkField

from . import models

User = get_user_model()


class MovieFileInline(admin.TabularInline):
	model = models.MovieFile
	extra = 1
	readonly_fields = ('created_at',)


class MovieAdmin(admin.ModelAdmin):
	list_display = ('id', 'title', 'release_date', 'is_published', 'created_at')
	search_fields = ('title', 'description')
	list_filter = ('is_published', 'categories')
	prepopulated_fields = {'slug': ('title',)}
	inlines = (MovieFileInline,)


class CourseVideoInline(admin.TabularInline):
	model = models.CourseVideo
	extra = 1
	fields = ('title', 'order', 'duration')


class CourseAdmin(admin.ModelAdmin):
    list_display = ("id",'title', 'channel', 'is_free', 'created_at')
    search_fields = ('title', 'description')
    list_filter = ('is_free', 'categories')
    prepopulated_fields = {'slug': ('title',)}
    inlines = (CourseVideoInline,)


class SubscriptionInline(admin.TabularInline):
    model = models.Subscription
    extra = 0
    fk_name = 'channel'
    autocomplete_fields = ['user']
    readonly_fields = ('created_at',)


class ChannelAdmin(admin.ModelAdmin):
    list_display = ("id", 'title', 'user', 'verified', 'subscriber_count')
    search_fields = ('title', 'user__username', 'user__email')
    readonly_fields = ('created_at',)
    inlines = (SubscriptionInline,)

    def subscriber_count(self, obj):
        return obj.subscribers.count()

    subscriber_count.short_description = 'Subscribers'


class ReelAdmin(admin.ModelAdmin):
	list_display = ("id", '__str__', 'channel', 'created_by', 'likes', 'views', 'created_at')
	search_fields = ('title', 'caption', 'channel__title', 'created_by__username')




class CommentAdmin(admin.ModelAdmin):
	list_display = ('user', 'short_text', 'created_at')
	search_fields = ('user__username', 'text')
	readonly_fields = ('created_at', 'updated_at')


	def short_text(self, obj):
		return (obj.text[:75] + '...') if len(obj.text) > 75 else obj.text

	short_text.short_description = 'Comment'


# class RatingAdmin(admin.ModelAdmin):
# 	list_display = ('user', 'value', 'created_at')
# 	list_filter = ('value',)


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
	list_display = ('username', 'email', 'avatar', 'role', 'is_staff', 'is_superuser')
	search_fields = ('username', 'email')
	list_filter = ('role', 'is_staff')

	fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'avatar')}),  # ✅ avatar qo‘shildi
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Role info', {'fields': ('role',)}),  # qo‘shimcha role maydoni
    )


# Register models
admin.site.register(models.Channel, ChannelAdmin)
admin.site.register(models.Category)
admin.site.register(models.CourseCategory)
admin.site.register(models.Language)
admin.site.register(models.Movie, MovieAdmin)
admin.site.register(models.Course, CourseAdmin)
admin.site.register(models.Playlist)
admin.site.register(models.Reel, ReelAdmin)
admin.site.register(models.Subscription)
admin.site.register(models.ReelComment, CommentAdmin)
admin.site.register(models.MovieComment, CommentAdmin)
admin.site.register(models.ChannelComment, CommentAdmin)
class CourseTypeAdmin(admin.ModelAdmin):
	list_display = ("id", 'name', 'course', 'price')
	search_fields = ('name', 'slug', 'course__title')
	autocomplete_fields = ('course',)

admin.site.register(models.CourseType, CourseTypeAdmin)
admin.site.register(models.CourseVideo)
admin.site.register(models.CourseVideoComment, CommentAdmin)
admin.site.register(models.MovieFile)
admin.site.register(models.LikeReels)

# TEST
admin.site.register(models.VideoTest)
admin.site.register(models.TestQuestion)
admin.site.register(models.TestOption)
admin.site.register(models.TestAnswer)
admin.site.register(models.TestResult)
admin.site.register(models.VideoAssignment)
admin.site.register(models.AssignmentSubmission)
admin.site.register(models.CourseVideoProgress)
admin.site.register(models.CourseTypeAssignment)
admin.site.register(models.CourseTypeTest)
admin.site.register(models.CourseTypeTestQuestion)
admin.site.register(models.CourseTypeTestOption)
admin.site.register(models.CourseTypeTestResult)
admin.site.register(models.CourseTypeAssignmentSubmission)
admin.site.register(models.CourseTypeTestAnswer)
admin.site.register(models.PromoCode)
admin.site.register(models.ReelView)

# Wallet models
class WalletTransactionInline(admin.TabularInline):
    model = models.WalletTransaction
    extra = 0
    readonly_fields = ('created_at', 'balance_after')
    fields = ('transaction_type', 'amount', 'description', 'course', 'course_type', 'from_user', 'to_user', 'created_at')
    autocomplete_fields = ('course', 'course_type', 'from_user', 'to_user')

@admin.register(models.Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'created_at', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    inlines = (WalletTransactionInline,)

@admin.register(models.WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet_user', 'transaction_type', 'amount', 'balance_after', 'course', 'course_type', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('wallet__user__username', 'description', 'course__title', 'course_type__name')
    readonly_fields = ('created_at', 'balance_after')
    autocomplete_fields = ('wallet', 'course', 'course_type', 'from_user', 'to_user', 'related_transaction')
    
    def wallet_user(self, obj):
        return obj.wallet.user.username
    wallet_user.short_description = 'Foydalanuvchi'

# admin.site.register(models.MovieComment, RatingAdmin)
@admin.register(models.Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ("title", "position", "is_active")

