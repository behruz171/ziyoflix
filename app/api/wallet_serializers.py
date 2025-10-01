from rest_framework import serializers
from app import models
from decimal import Decimal


class WalletSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = models.Wallet
        fields = ('id', 'username', 'balance', 'created_at', 'updated_at')
        read_only_fields = ('id', 'username', 'balance', 'created_at', 'updated_at')


class WalletTransactionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='wallet.user.username', read_only=True)
    from_username = serializers.CharField(source='from_user.username', read_only=True)
    to_username = serializers.CharField(source='to_user.username', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_type_name = serializers.CharField(source='course_type.name', read_only=True)
    course_type_id = serializers.IntegerField(source='course_type.id', read_only=True)
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    
    class Meta:
        model = models.WalletTransaction
        fields = (
            'id', 'username', 'transaction_type', 'transaction_type_display', 
            'amount', 'balance_after', 'description', 'course_title',
            'course_type_id', 'course_type_name',
            'from_username', 'to_username', 'created_at'
        )
        read_only_fields = ('id', 'username', 'balance_after', 'created_at')


class DepositSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'))
    description = serializers.CharField(max_length=500, required=False, default='Hamyonga pul toldirish')
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive")
        if value > Decimal('100000'):  # maksimal limit
            raise serializers.ValidationError("Amount too large (max: 100,000 FixCoin)")
        return value


class WithdrawalSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'))
    description = serializers.CharField(max_length=500, required=False, default='Hamyondan pul yechish')
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive")
        return value


class CoursePurchaseSerializer(serializers.Serializer):
    """Serializer for purchasing a full course."""
    course_id = serializers.IntegerField()
    
    def validate_course_id(self, value):
        try:
            course = models.Course.objects.get(id=value)
            if course.is_free:
                raise serializers.ValidationError("This course is free")
            if not course.price or course.price <= 0:
                raise serializers.ValidationError("Course price not set")
            # Respect purchase scope
            if getattr(course, 'purchase_scope', 'course') == 'course_type':
                raise serializers.ValidationError("Bu kursda to'lov CourseType darajasida amalga oshiriladi")
            return value
        except models.Course.DoesNotExist:
            raise serializers.ValidationError("Course not found")


class CourseTypePurchaseSerializer(serializers.Serializer):
    """Serializer for purchasing a specific course type within a course."""
    course_type_id = serializers.IntegerField()
    
    def validate_course_type_id(self, value):
        try:
            course_type = models.CourseType.objects.select_related('course').get(id=value)
            # If course type has no price, check the parent course price
            if course_type.price is None and (not course_type.course.price or course_type.course.price <= 0):
                raise serializers.ValidationError("Price is not set for this course type or its parent course")
            if course_type.course.is_free:
                raise serializers.ValidationError("This course is free")
            # Respect purchase scope
            if getattr(course_type.course, 'purchase_scope', 'course') == 'course':
                raise serializers.ValidationError("Bu kurs faqat butun kurs sifatida sotib olinadi")
            return value
        except models.CourseType.DoesNotExist:
            raise serializers.ValidationError("Course type not found")


class WalletStatsSerializer(serializers.Serializer):
    """Hamyon statistikasi uchun."""
    balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_income = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_expense = serializers.DecimalField(max_digits=15, decimal_places=2)
    transactions_count = serializers.IntegerField()
    courses_purchased = serializers.IntegerField()
    courses_sold = serializers.IntegerField()
    last_transaction_date = serializers.DateTimeField(allow_null=True)
