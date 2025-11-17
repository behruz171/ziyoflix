from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Q
from decimal import Decimal

from app import models
from .wallet_serializers import (
    WalletSerializer, WalletTransactionSerializer, DepositSerializer,
    WithdrawalSerializer, CoursePurchaseSerializer, WalletStatsSerializer
)


class WalletDetailAPIView(APIView):
    """Foydalanuvchining hamyon ma'lumotlari."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        wallet, created = models.Wallet.objects.get_or_create(user=request.user)
        serializer = WalletSerializer(wallet)
        return Response(serializer.data)


class WalletTransactionsAPIView(APIView):
    """Foydalanuvchining tranzaksiyalar tarixi."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        wallet, created = models.Wallet.objects.get_or_create(user=request.user)
        transactions = models.WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')
        
        # Filtrlash
        transaction_type = request.query_params.get('type')
        if transaction_type:
            transactions = transactions.filter(transaction_type=transaction_type)
        
        # Pagination (oddiy)
        limit = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))
        transactions = transactions[offset:offset + limit]
        
        serializer = WalletTransactionSerializer(transactions, many=True)
        return Response({
            'transactions': serializer.data,
            'count': len(serializer.data)
        })


class WalletDepositAPIView(APIView):
    """Hamyonga pul toldirish."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = DepositSerializer(data=request.data)
        if serializer.is_valid():
            wallet, created = models.Wallet.objects.get_or_create(user=request.user)
            
            try:
                wallet.add_balance(
                    amount=serializer.validated_data['amount'],
                    transaction_type='deposit',
                    description=serializer.validated_data['description']
                )
                
                return Response({
                    'success': True,
                    'message': 'Pul muvaffaqiyatli qo\'shildi',
                    'new_balance': wallet.balance
                }, status=status.HTTP_200_OK)
                
            except ValueError as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WalletWithdrawalAPIView(APIView):
    """Hamyondan pul yechish."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = WithdrawalSerializer(data=request.data)
        if serializer.is_valid():
            wallet, created = models.Wallet.objects.get_or_create(user=request.user)
            
            try:
                wallet.subtract_balance(
                    amount=serializer.validated_data['amount'],
                    transaction_type='withdrawal',
                    description=serializer.validated_data['description']
                )
                
                return Response({
                    'success': True,
                    'message': 'Pul muvaffaqiyatli yechildi',
                    'new_balance': wallet.balance
                }, status=status.HTTP_200_OK)
                
            except ValueError as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CoursePurchaseAPIView(APIView):
    """Butun kursni sotib olish."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = CoursePurchaseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        course_id = serializer.validated_data['course_id']
        promo = serializer.validated_data.get('__promo')
        course = get_object_or_404(models.Course, id=course_id)
        
        # Scope check: this course only allows CourseType purchases
        if getattr(course, 'purchase_scope', 'course') == 'course_type':
            return Response({
                'success': False,
                'error': 'Bu kursda to\'lov CourseType darajasida amalga oshiriladi. Iltimos, CourseType orqali xarid qiling.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if already purchased
        existing_purchase = models.WalletTransaction.objects.filter(
            wallet__user=request.user,
            course=course,
            transaction_type='course_purchase'
        ).exists()
        
        if existing_purchase:
            return Response({
                'success': False,
                'error': 'Siz bu kursni allaqachon sotib olgansiz'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            seller_user = course.channel.user
            # Pricing with promo
            original_amount = course.price
            discount_amount = 0
            if promo:
                if promo.discount_type == 'percent':
                    discount_amount = (original_amount * promo.value) / Decimal('100')
                else:  # coins
                    discount_amount = promo.value
                if discount_amount < 0:
                    discount_amount = Decimal('0')
                if discount_amount > original_amount:
                    discount_amount = original_amount
            final_amount = original_amount - discount_amount
            # Process payment
            buyer_transaction, seller_transaction = models.Wallet.transfer_for_course_purchase(
                buyer_user=request.user,
                seller_user=seller_user,
                course=course,
                amount=final_amount,
                platform_commission_rate=0.05,  # 5% commission
                original_amount=original_amount,
                discount_amount=discount_amount,
                promo_code=promo,
            )
            
            return Response({
                'success': True,
                'message': f'Kurs "{course.title}" muvaffaqiyatli sotib olindi',
                'purchase_type': 'full_course',
                'course': {
                    'id': course.id,
                    'title': course.title,
                    'price': str(original_amount),
                    'discount': str(discount_amount),
                    'paid_amount': str(final_amount),
                    'promo_code': promo.code if promo else None,
                },
                'transaction_id': buyer_transaction.id
            }, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class CourseTypePurchaseAPIView(APIView):
    """Kursning ma'lum bir turini sotib olish."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        from .wallet_serializers import CourseTypePurchaseSerializer
        
        serializer = CourseTypePurchaseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        course_type_id = serializer.validated_data['course_type_id']
        promo = serializer.validated_data.get('__promo')
        course_type = get_object_or_404(
            models.CourseType.objects.select_related('course', 'course__channel'), 
            id=course_type_id
        )
        
        # Scope check: this course only allows full course purchases
        if getattr(course_type.course, 'purchase_scope', 'course') == 'course':
            return Response({
                'success': False,
                'error': 'Bu kurs faqat butun kurs sifatida sotib olinadi. Iltimos, Full Course xarididan foydalaning.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if already purchased this course type
        existing_purchase = models.WalletTransaction.objects.filter(
            wallet__user=request.user,
            course_type=course_type,
            transaction_type='course_type_purchase'
        ).exists()
        
        if existing_purchase:
            return Response({
                'success': False,
                'error': 'Siz bu kurs turini allaqachon sotib olgansiz'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Determine the price (course type price or fallback to course price)
        price = course_type.price if course_type.price is not None else course_type.course.price
        
        try:
            seller_user = course_type.course.channel.user
            
            # Process payment
            original_amount = price
            discount_amount = 0
            if promo:
                if promo.discount_type == 'percent':
                    discount_amount = (original_amount * promo.value) / Decimal('100')
                else:
                    discount_amount = promo.value
                if discount_amount < 0:
                    discount_amount = Decimal('0')
                if discount_amount > original_amount:
                    discount_amount = original_amount
            final_amount = original_amount - discount_amount
            buyer_transaction, seller_transaction = models.Wallet.transfer_for_course_purchase(
                buyer_user=request.user,
                seller_user=seller_user,
                course=course_type.course,
                course_type=course_type,
                amount=final_amount,
                platform_commission_rate=0.05,  # 5% commission
                transaction_type='course_type_purchase',
                original_amount=original_amount,
                discount_amount=discount_amount,
                promo_code=promo,
            )
            
            return Response({
                'success': True,
                'message': f'Kurs turi "{course_type.name}" muvaffaqiyatli sotib olindi',
                'purchase_type': 'course_type',
                'course': {
                    'id': course_type.course.id,
                    'title': course_type.course.title,
                    'course_type_id': course_type.id,
                    'course_type_name': course_type.name,
                    'price': str(original_amount),
                    'discount': str(discount_amount),
                    'paid_amount': str(final_amount),
                    'promo_code': promo.code if promo else None,
                },
                'transaction_id': buyer_transaction.id
            }, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class WalletStatsAPIView(APIView):
    """Hamyon statistikasi."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        wallet, created = models.Wallet.objects.get_or_create(user=request.user)
        transactions = models.WalletTransaction.objects.filter(wallet=wallet)
        
        # Statistikalar
        total_income = transactions.filter(amount__gt=0).aggregate(
            total=Sum('amount'))['total'] or Decimal('0.00')
        total_expense = abs(transactions.filter(amount__lt=0).aggregate(
            total=Sum('amount'))['total'] or Decimal('0.00'))
        
        courses_purchased = transactions.filter(transaction_type='course_purchase').count()
        courses_sold = transactions.filter(transaction_type='course_earning').count()
        
        last_transaction = transactions.first()
        last_transaction_date = last_transaction.created_at if last_transaction else None
        
        stats_data = {
            'balance': wallet.balance,
            'total_income': total_income,
            'total_expense': total_expense,
            'transactions_count': transactions.count(),
            'courses_purchased': courses_purchased,
            'courses_sold': courses_sold,
            'last_transaction_date': last_transaction_date
        }
        
        serializer = WalletStatsSerializer(stats_data)
        return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_balance(request):
    """Faqat balansni qaytarish (tez API)."""
    wallet, created = models.Wallet.objects.get_or_create(user=request.user)
    
    # Debug uchun
    calculated_balance = wallet.recalculate_balance()
    
    return Response({
        'balance': wallet.balance,
        'calculated_balance': calculated_balance,
        'currency': 'FixCoin',
        'debug': {
            'wallet_id': wallet.id,
            'user': wallet.user.username,
            'transactions_count': wallet.transactions.count()
        }
    })
